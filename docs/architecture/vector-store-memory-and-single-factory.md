# Vector Store Memory: Root Cause and Single-Factory Design

> Analysis from implementation and code essence: why 6–7G RSS occurred, why two creation paths existed, and how the single-factory design fixes it.

---

## 1. Root cause

### 1.1 Symptom

- MCP long-lived process still used 6–7G RSS after restart; with the smallest embedding model, expected usage is about 1–2G.
- Reducing `index_cache_size_bytes` / `max_cached_tables` helped, but did not fix the design: some code path could still create unbounded caches.

### 1.2 Root cause: two creation paths, only one applied resource limits

Vector store creation had **two separate code paths**:

| Path           | Location                                            | Behavior                                                                                                                                             | Cache limits applied? |
| -------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| **Bridge**     | `omni.foundation.bridge.rust_vector`                | `get_vector_store(path)` → builds `RustVectorStore`, resolving settings and passing `index_cache_size_bytes`, `max_cached_tables` in the constructor | Yes                   |
| **Foundation** | `omni.foundation.services.vector.VectorStoreClient` | Called `omni_core_rs.create_vector_store(path, dim, True)` directly with only 3 arguments                                                            | No                    |

Rust binding signature:

```text
create_vector_store(path, dimension, enable_keyword_index, index_cache_size_bytes=None, max_cached_tables=None)
```

- Bridge resolves settings / defaults in `RustVectorStore.__init__` and passes them to the underlying creator, so **all stores created via the bridge are bounded**.
- Foundation passed only `(path, dim, True)`; the last two arguments were `None` → Rust treated them as unbounded index cache and no limit on cached tables → **with multiple DBs/tables in one process, memory could grow to several GB**.

So: **“who creates the store” was implemented twice, and the resource policy was applied on only one path.** The issue was duplicated responsibility and inconsistent policy, not just missing parameters.

### 1.3 Why two paths existed

- **Bridge**: Built for router/skills/indexer; caches `RustVectorStore` by path and exposes `search_tools`, `search_optimized`, ingest, etc.; cache limits were added in the constructor later.
- **Foundation**: Built for RAG/knowledge (collection abstraction), needing a default store and a knowledge store; it called Rust’s `create_vector_store` directly, never went through the bridge, and never applied cache limits from settings.

Result: **the same process had bounded stores from the bridge and unbounded stores from Foundation**; the latter were a major source of memory in long-lived MCP.

---

## 2. Correct design: single factory

### 2.1 Principles

- **Single creation point**: All vector store instances must be created by **one factory**, where config (path, dimension, **index_cache_size_bytes**, **max_cached_tables**) is applied consistently.
- **Single policy**: Resource limits (cache size, max cached tables) are resolved in one place from config/defaults; no other code path may call the underlying API with different or missing parameters.

In the codebase, **the only place that already centralizes path + dimension + cache limits is the bridge’s `get_vector_store()`**. So:

- Foundation must not call `omni_core_rs.create_vector_store` directly.
- Foundation must obtain stores via the **bridge’s `get_vector_store(path)`**, reusing the same creation logic and resource policy.

### 2.2 Architecture goal

```
                     ┌─────────────────────────────────────┐
                     │  get_vector_store(path, dimension?)  │
                     │  (bridge; only place that applies    │
                     │   cache limits)                       │
                     └─────────────────┬─────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
  Router / Skills / Indexer    VectorStoreClient         Other consumers
  (existing)                   (default + knowledge)     (future)
           │                           │
           └───────────────────────────┴── all get RustVectorStore, same resource policy
```

### 2.3 Interface requirements for Foundation

`VectorStoreClient` in Foundation relies on the store having:

- `search_optimized(collection, vector, limit, options_json)`
- `search_optimized_ipc(collection, vector, limit, options_json, projection=...)`
- `add_documents(collection, ids, vectors, contents, metadatas)` (Foundation calls it; bridge exposes it as async)
- `delete(collection, id)` (by collection + id)
- `count(collection)`
- `add_columns` / `alter_columns` / `drop_columns` (collection + payload/columns)
- `create_index(collection)`

Bridge’s `RustVectorStore` provides:

- `search_optimized(table_name, ...)`, `search_optimized_ipc(table_name, ...)` — map to collection.
- `add_documents(table_name, ...)` — async; Foundation’s `add`/`add_batch` are async and can `await` it.
- `delete(document_id)` was originally fixed to the `"skills"` table; it was generalized to **delete by table name + id(s)** as `delete_by_ids(table_name, ids)`.
- `count` was only used internally in `health_check` via `_inner.count("skills")`; it is now exposed as **`count(table_name)`**.

Implementation therefore:

1. **Bridge**: Expose `count(table_name)` and `delete_by_ids(table_name, ids)` on `RustVectorStore`, matching the Rust API.
2. **Foundation**:
   - Stop holding stores created with `create_vector_store`;
   - Obtain `RustVectorStore` via `get_vector_store(default_path)` and `get_vector_store(knowledge_path)`;
   - Use the bridge API for all store calls (including `await` for async methods and `delete_by_ids` instead of `delete(collection, id)`).

Then **memory limits are applied only in the single factory (bridge)**, and unbounded caches do not reappear from Foundation or other callers opening a second creation path.

---

## 3. Implementation summary

| Item                                                    | Description                                                                                                                                                            |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Remove direct `create_vector_store` usage in Foundation | Both default store and knowledge store; no 3- or 5-argument direct calls.                                                                                              |
| Foundation obtains stores only via bridge               | `_get_store_for_collection` / `store` only resolve path, then call `get_vector_store(resolved_path)`.                                                                  |
| Bridge exposes APIs required by Foundation              | `count(table_name)`, `delete_by_ids(table_name, ids)`; the rest already existed or were mappable.                                                                      |
| Foundation call-site adaptation                         | Use `await` for bridge async methods (`add_documents`, `add_columns`, `create_index`); use `delete_by_ids(collection, [id])` for delete.                               |
| Tests and regression                                    | Cover VectorStoreClient search/add/delete/count, etc.; confirm MCP creates stores only via bridge and that memory stays in the expected range (e.g. 1–2G with config). |

---

## 4. Regression tests (prevent abnormal memory/CPU)

These tests prevent the single-factory and bounded-cache design from being broken, or defaults from being raised so far that memory/CPU become abnormal:

- **Location**: `packages/python/foundation/tests/unit/services/test_vector_memory_guard.py`
- **Single factory**: `TestSingleFactoryGuard` — Foundation source must not reference `create_vector_store`; `VectorStoreClient.store` / `_get_store_for_collection` must obtain the store only via the bridge’s `get_vector_store`.
- **Bounded cache**: `TestBoundedCacheGuard` — `RustVectorStore`’s `_index_cache_size_bytes` and `_max_cached_tables` must not be None; when settings are null, module default constants are used; those constants must not exceed safe caps (e.g. 512 MiB, 16 tables).
- **Factory bounded**: `TestGetVectorStoreUsesBoundedParams` — Stores created by `get_vector_store()` must have non-None cache parameters.
- **Search cache**: `TestSearchCacheBounded` — Foundation’s `SearchCache` `max_size` must not exceed the agreed cap (e.g. 500), to avoid unbounded growth in long-lived processes.

If bridge defaults are changed or Foundation again creates stores directly, these tests fail; the change must be explicitly justified in review and the doc/tests updated.

---

## 5. References

- Rust bindings: `packages/rust/bindings/python/src/vector/mod.rs` (`create_vector_store` signature, `add_documents`/`delete`/`count`).
- Bridge factory and defaults: `packages/python/foundation/src/omni/foundation/bridge/rust_vector.py` (`RustVectorStore.__init__`, `get_vector_store`).
- Foundation store usage: `packages/python/foundation/src/omni/foundation/services/vector.py` (`_get_store_for_collection`, `store`, search/add/delete/count/columns/create_index).
