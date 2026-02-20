# Knowledge Recall Memory Analysis

> Root-cause analysis for "why is memory usage high for a single client query?"

---

## 1. Call Chain Overview

```
Client (Cursor/omniAgent)
  → MCP process (knowledge.recall)
    → Embedding (HTTP or local)
    → VectorStore.search / search_hybrid
    → Dual-Core Boost (LinkGraph + KG)
    → Return results
```

**Key point**: Memory is consumed primarily by the **MCP process**, not the client.

---

## 2. Memory Breakdown

### 2.1 Baseline (before first recall)

| Component             | Description                                                                 | Est. usage          |
| --------------------- | --------------------------------------------------------------------------- | ------------------- |
| Python runtime        | Interpreter + loaded modules                                                | ~100–200 MB         |
| Embedding service     | If MCP embeds HTTP server (same-process thread): loads Qwen3-Embedding-0.6B | **~500 MB–1 GB**    |
| Embedding client mode | `provider: client` with external service running                            | ~0 (no local model) |

**Conclusion**: If MCP runs its own embedding service, baseline is already ~0.5–1 GB.

### 2.2 Loaded on first recall

| Component             | Description                                                               | Est. usage              |
| --------------------- | ------------------------------------------------------------------------- | ----------------------- |
| VectorStore (LanceDB) | `index_cache_size_bytes`: 128 MiB (from settings)                         | **128 MB**              |
| Table cache           | `max_cached_tables`: 4, LRU eviction                                      | Depends on table size   |
| KnowledgeGraph        | `_load_kg()` loads `kg_entities` + `kg_relations` from Lance (now cached) | Cached after first load |
| LinkGraph backend     | `link_graph_proximity_boost` fetches neighbors/tags from graph index      | Small                   |

### 2.3 Per-query increment

| Component                   | Description                              | Est. usage        |
| --------------------------- | ---------------------------------------- | ----------------- |
| Query vector                | 1 × 256-dim float (truncate_dim)         | ~1 KB             |
| Search results              | limit=15, ~0.5–2 KB content each         | ~30 KB            |
| SearchCache                 | 200 entries × ~30 KB                     | ~6 MB (when full) |
| Embedding single-slot cache | Only caches the most recent query vector | ~1 KB             |

---

## 3. Main Issues

### 3.1 KnowledgeGraph cache (implemented)

- `_load_kg()` is now cached with `@lru_cache(maxsize=2)` in `dual_core/_config.py`.
- Cache is cleared on `_save_kg()` so ingest updates are visible on next recall.
- Avoids repeated disk reads on subsequent recalls.

### 3.2 Embedding model resident (non-client mode)

- If MCP starts the embedding HTTP server (same-process thread), the model stays resident.
- Qwen3-Embedding-0.6B: ~500 MB with float16, ~1 GB with float32.

### 3.3 LanceDB index and table cache

- `index_cache_size_bytes: 128 MiB` limits index cache.
- `max_cached_tables: 4` limits table cache count.
- Large knowledge tables can cause a noticeable memory spike on first open/scan.

### 3.4 Dual-Core extra loading

- `compute_fusion_weights`: calls `extract_query_intent`, lightweight.
- `link_graph_proximity_boost`: graph-neighbor and tag fetch, typically small.
- `apply_kg_recall_boost`: loads KG (now cached after first call).

---

## 4. Optimization Recommendations

### 4.1 Short-term (configuration)

1. **Use embedding client mode** (if you have a separate embedding service):

   ```yaml
   # settings.yaml
   embedding:
     provider: "client"
     client_url: "http://127.0.0.1:18501"
   ```

   Avoids loading the model in the MCP process, saving ~0.5–1 GB.

2. **Tighten vector cache** (when memory is constrained):
   ```yaml
   vector:
     index_cache_size_bytes: 67108864 # 64 MiB
     max_cached_tables: 2
   ```

### 4.2 Diagnostic commands

```bash
# View current vector config
grep -A5 "^vector:" packages/conf/settings.yaml

# View embedding mode
grep -A3 "provider:" packages/conf/settings.yaml
```

---

## 5. Summary

| Scenario                 | Main memory sources            | Est. total                          |
| ------------------------ | ------------------------------ | ----------------------------------- |
| MCP + embedded embedding | Model + vector cache + KG load | **1–2 GB**                          |
| MCP + client mode        | Vector cache + KG load         | **~200–500 MB**                     |
| Per-recall increment     | KG load (cached) + result set  | **~50–200 MB** (depends on KG size) |

**Conclusion**: Even for a single client query, the MCP process loads embedding (unless client mode), vector index/table cache, and KG (now cached after first load). Using embedding client mode and the KG cache are the main optimizations.
