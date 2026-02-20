# Unified Cache in Rust: Feasibility Analysis

> Can we unify the related caching mechanisms and implement them on the Rust side?

---

## 1. Current Cache Landscape

| Cache               | Location                                      | Purpose                                     | Data                                                       |
| ------------------- | --------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------- |
| **DatasetCache**    | Rust (`omni-vector/ops/cache.rs`)             | LRU for Lance Dataset handles               | `table_name → Dataset`                                     |
| **Index cache**     | Rust (Lance)                                  | HNSW/IVF index in memory                    | Passed via `index_cache_size_bytes`                        |
| **KG load**         | Python (`dual_core/_config.py`)               | Avoid reloading KG from disk on each recall | `lance_dir → PyKnowledgeGraph`                             |
| **SearchCache**     | Rust (`omni-vector/search_cache.rs`) + Python | LRU+TTL for search results                  | `(path, table, limit, options, vector_hash) → Vec<String>` |
| **Embedding cache** | Python (`EmbeddingService`)                   | Single-slot query→vector                    | `text → list[float]`                                       |

---

## 2. Feasibility by Cache

### 2.1 KG Cache → Rust ✅ Feasible

**Current flow**: Python `_load_kg()` → `PyKnowledgeGraph()` + `load_from_lance(path)` → Rust reads Lance tables.

**Rust-side approach**:

- Add a static cache in `xiuxian-wendao`: `path → Arc<KnowledgeGraph>` (or `DashMap<String, Arc<KnowledgeGraph>>`).
- Expose `PyKnowledgeGraph::from_lance_cached(path: &str) -> PyResult<PyKnowledgeGraph>` that:
  - Checks cache for `path`
  - On hit: returns a new `PyKnowledgeGraph` wrapping `Arc::clone(&cached)` (or a shared inner).
  - On miss: loads, inserts into cache, returns.
- On `save_to_lance`, invalidate cache for that path (or clear entire cache).

**Benefits**: Single source of truth, no Python `lru_cache`, KG stays in Rust memory.

**Complexity**: Medium. `KnowledgeGraph` uses `RwLock` internally; we need to decide whether to cache `Arc<KnowledgeGraph>` (shared read) or clone on cache hit. Cloning may be expensive for large graphs.

---

### 2.2 SearchCache → Rust ⚠️ Partially Feasible

**Current flow**: Python embeds query → gets vector → calls Rust `search_optimized(vector, collection, limit, options_json)` → Python caches `(query, options) → results`.

**Challenge**: The cache key in Python is `(query_text, collection, options)` because embedding is done in Python (HTTP client or local model). Rust receives the **vector**, not the query text.

**Option A – Cache by vector in Rust**:

- Key: `(hash(vector), collection, options_json)`.
- Rust checks cache before running search. On hit, return cached results.
- Pros: Cache lives where search runs; no Python round-trip for cache lookup.
- Cons: Hashing 256 floats per lookup; cache key is large; Python still does embedding before calling Rust.

**Option B – Move embedding into Rust**:

- Rust would need an embedding client (HTTP or native). Then Rust could own the full flow: `query → embed → search → cache`.
- Pros: Fully unified in Rust.
- Cons: Significant work; embedding is currently Python/HTTP-centric.

**Implemented**: Option A. `omni-vector/search_cache.rs` caches results keyed by `(path, table, limit, options_json, vector_hash)`. Default `max_size=200`, `ttl=300` (matches Python SearchCache). Used in `search_optimized_async` and `search_hybrid_async`. Python SearchCache remains as first-level (query-based) cache; Rust cache hits when Python misses and embedding has already run.

---

### 2.3 Embedding Cache → Rust ❌ Not Practical (Current Design)

**Current flow**: Python `EmbeddingService.embed(text)` → HTTP client or local model → returns vector. Python caches `text → vector` in a single slot.

**Why Rust is a poor fit**:

- Embedding is done via Python (sentence-transformers, aiohttp to embedding server). Rust has no embedding client.
- Moving embedding to Rust would require a new Rust HTTP client + possibly native model bindings.
- The single-slot cache is tiny (~1 KB); benefit of moving to Rust is negligible.

**Recommendation**: Keep in Python.

---

## 3. Summary: What to Unify in Rust

| Cache          | Move to Rust?   | Effort | Impact                                                      |
| -------------- | --------------- | ------ | ----------------------------------------------------------- |
| KG load        | ✅ Yes          | Medium | High (avoids repeated disk + Python object overhead)        |
| Search results | ✅ Optional     | Medium | Medium (reduces Python cache logic; co-located with search) |
| Embedding      | ❌ No           | High   | Low                                                         |
| Dataset/Index  | Already in Rust | —      | —                                                           |

---

## 4. Implementation Order

1. **KG cache in Rust** (highest impact)
   - Add `from_lance_cached(path)` in `xiuxian-wendao` with path-keyed cache.
   - Invalidate on `save_to_lance`.
   - Remove Python `@lru_cache` from `_load_kg`.

2. **Search result cache in Rust** (optional)
   - Add optional cache to `search_optimized` / `search_hybrid` in `omni-vector`.
   - Key: `(vector_hash, collection, options_json)`.
   - Config: `search_cache_max_size`, `search_cache_ttl` (or disabled by default).
   - Python can stop using `SearchCache` when Rust cache is enabled.

---

## 5. Architecture After Unification

```
                    Python                          Rust
                       │                              │
  knowledge.recall ────┼── embed(query) ──────────────┤  (HTTP, stays Python)
                       │                              │
                       ├── get_kg_cached(path) ──────►│  KG cache (NEW)
                       │                              │
                       ├── search_optimized(vec,...)─►│  Search + optional result cache (NEW)
                       │                              │  DatasetCache (existing)
                       │                              │  Index cache (existing)
```

---

## 6. Conclusion

**Yes, the main caches can be unified on the Rust side**, with these caveats:

- **KG cache**: Best candidate; move to Rust for single source of truth and lower memory churn.
- **Search cache**: Can be moved to Rust if we accept caching by vector hash; requires some API and config work.
- **Embedding cache**: Keep in Python; moving to Rust is not worth the effort.

A practical first step is implementing the KG cache in `xiuxian-wendao`, then evaluating whether a Rust-side search result cache provides measurable benefit before adding it.
