# Search Systems: When to Use Which

This document distinguishes the search systems implemented in Omni-Dev-Fusion and when each should be used.

---

## Summary

| System             | What it does                          | Typical use                         | Default where                      |
| ------------------ | ------------------------------------- | ----------------------------------- | ---------------------------------- |
| **Vector search**  | Semantic-only (embedding k-NN)        | Similarity over one table           | RAG/knowledge semantic-only path   |
| **Hybrid search**  | Vector + keyword with RRF fusion      | Natural language over tools or docs | RAG `search_hybrid`; tool fallback |
| **Agentic search** | Intent-based strategy for tool search | Tool/command routing                | Router, Discovery, Indexer         |

---

## 1. Vector search (semantic-only)

**What it is**

- Pure vector similarity: query embedding vs. stored embeddings, top-k by distance/similarity.
- No keyword index, no fusion.

**Rust**

- `VectorStore::search_optimized(table_name, query_vector, limit, options)`.

**Python / usage**

- `RustVectorStore.search_optimized(table_name, query_vector, limit)`.
- Knowledge: `Librarian.vector_search(vector, limit)` → Rust `search_optimized`.

**When to use**

- You already have a query embedding and want **only** similarity search.
- No need for keyword match or intent switching (e.g. generic RAG chunks, “find similar”).
- Table is vector-only (no FTS/keyword index).

**When not to use**

- User text query without a strong reason to skip keywords → prefer hybrid or agentic (for tools).

---

## 2. Hybrid search (vector + keyword, RRF)

**What it is**

- Combines vector search and keyword (FTS/BM25) search with **weighted RRF** (Reciprocal Rank Fusion).
- Single ranking list; **rerank** (metadata-aware field boosting) is **always on** in the hybrid path.

**Rust**

- Tool table: `VectorStore::search_tools` / `search_tools_with_options` (vector + keyword, RRF, optional `where_filter`).
- Generic table: `VectorStore::search_hybrid` (vector + keyword over one table).

**Python / usage**

- Tool path: `RustVectorStore.search_tools(...)` (used when store has no `agentic_search`, or inside agentic when intent is hybrid).
- RAG/docs: `VectorStoreClient.search_hybrid(...)` → Rust `search_hybrid`; Knowledge `Librarian.text_search(query_text, query_vector, limit)`.

**When to use**

- Natural language query where **both** meaning and keywords matter (e.g. “git commit message”, “find Python files”).
- Document/knowledge retrieval with text query + embedding.
- You do **not** need intent-based switching (exact vs semantic vs hybrid); you always want vector+keyword.

**When not to use**

- Tool routing: prefer agentic so the system can choose exact/semantic/hybrid per query.
- Pure similarity with no text: use vector search.

---

## 3. Agentic search (intent-based tool search)

**What it is**

- **Strategy selector** for **tool/command** search only. Picks one of:
  - **Exact**: keyword-only (e.g. user typed `git.commit`); fallback to hybrid if no keyword index.
  - **Semantic**: vector-only (no keyword fusion).
  - **Hybrid / Category**: full RRF (vector + keyword), same as hybrid search above.
- Intent can come from rule (e.g. `classify_tool_search_intent`) or from caller (`intent_override`).

**Rust**

- `VectorStore::agentic_search(table_name, query_vector, query_text, config)` with `AgenticSearchConfig` (limit, threshold, intent, optional `skill_name_filter` / `category_filter`).
- Internally calls `search_tools_with_options` (and keyword path for exact when available).

**Python / usage**

- `RustVectorStore.agentic_search(...)` with optional `intent`, `skill_name_filter`, `category_filter`, `intent_override`.
- **Default for tool search**: when the store has `agentic_search`, these use it:
  - `HybridSearch.search(...)` (router)
  - `SkillDiscoveryService.search_tools_async(...)`
  - `SkillIndexer.search(...)`
- So “current search system” for **tool routing** is agentic (when available), which then uses vector-only, keyword-only, or hybrid inside.

**When to use**

- **Tool/command routing**: user says “commit”, “run research”, “find files” → you want the right strategy (exact match vs semantic vs hybrid). This is the intended entry point.
- When you want to **restrict by skill or category** (`skill_name_filter`, `category_filter`).
- When an upstream (e.g. LLM) provides an **intent** → pass `intent_override`.

**When not to use**

- Non-tool tables (e.g. knowledge chunks, generic docs): use vector search or hybrid search, not agentic.
- RAG pipeline over documents: use `search_hybrid` / `text_search`, not agentic.

---

## Current defaults (what the system uses)

- **Tool routing (router, discovery, indexer)**
  - If store has `agentic_search`: **agentic search** (intent from rule or `intent_override`).
  - Else: **hybrid** via `search_tools`.

- **Knowledge / RAG**
  - Semantic-only: **vector search** (`search_optimized` / `vector_search`).
  - Text query: **hybrid** (`search_hybrid` / `text_search`).

- **Pipelines / tracer**
  - Backend choice `lance` vs `hybrid` controls vector-only vs hybrid for retrieval; no agentic (tool-only).

---

## Quick decision guide

| Scenario                                | Use                                                             |
| --------------------------------------- | --------------------------------------------------------------- |
| Route user to a tool/command            | **Agentic search** (default in router/discovery/indexer)        |
| “Find similar” / embedding-only         | **Vector search**                                               |
| Natural language over tools (no intent) | **Hybrid search** (`search_tools`)                              |
| RAG over knowledge/docs, with text      | **Hybrid** (`search_hybrid` / `text_search`)                    |
| RAG over knowledge/docs, vector only    | **Vector search** (`search_optimized` / `vector_search`)        |
| Restrict tools by skill/category        | **Agentic search** with `skill_name_filter` / `category_filter` |

---

## Related

- [Retrieval namespace](./retrieval-namespace.md) – contracts and backends.
- [RAG search](./rag-search.md) – cache, weights, patterns.
- [LanceDB version and roadmap](./lancedb-version-and-roadmap.md) – agentic search and filters.
