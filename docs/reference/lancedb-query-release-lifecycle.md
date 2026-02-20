# LanceDB / Lance Query and Release Lifecycle

> How we align with the lance (Rust) lifecycle so the MCP process does not retain vector store memory after queries. This **query-release** approach replaces earlier analyses of MCP server high memory footprint (e.g. 14G physical); we evict the knowledge store after every tool so the long-lived process does not hold large vector caches.

---

## 1. Lance (Rust) has no explicit “close”

We use the **Rust `lance` crate** (via `omni-vector`), not the Python `lancedb` package. In lance:

- **Open**: `Dataset::open(uri).await` or `DatasetBuilder::from_uri(uri).load().await` returns a `Dataset` handle. Opening may mmap files and load index cache.
- **Use**: Run queries (scan, vector search, etc.) on the `Dataset`.
- **Release**: There is no `dataset.close()`. You **drop** the `Dataset` (and any cache that holds it). When the last reference is dropped, Rust releases the handle and the allocator/OS can reclaim memory (best-effort; “owned unmapped” may persist until the process exits on some platforms).

So the correct lifecycle is: **open → use → drop**. We must not hold the `Dataset` (or a store that holds it) in a long-lived cache across requests.

---

## 2. Our layers

| Layer             | Where                                                                                                                                                                                            | Lifecycle                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| **Rust**          | `omni-vector`: `VectorStore` holds a `DatasetCache` (LRU of `Dataset` per table). `DatasetCache::remove(table)` drops that `Dataset`.                                                            | When the Rust `VectorStore` is dropped, the cache and all cached `Dataset`s are dropped. |
| **Python bridge** | `rust_vector.py`: `_vector_stores` dict caches `RustVectorStore` by path. `evict_vector_store_cache(path)` removes the entry so the `RustVectorStore` (and the Rust store inside it) is dropped. | Evicting from `_vector_stores` is the Python-side “close”.                               |
| **Kernel**        | After every tool execution we call `evict_knowledge_store_after_use()`: evict the knowledge store from the bridge cache, clear `VectorStoreClient` refs, and run `gc.collect()`.                 | So after every tool we effectively “close” the knowledge store.                          |

We do not keep the knowledge store open across tool calls. We open (on first use in a request), use (query), then evict (drop) so the next request opens fresh. That matches the intended open → use → drop lifecycle.

---

## 3. Why after every tool (no option)

Any tool may use the knowledge vector store (e.g. via a shared service). We release **after every tool execution** so that:

- No configuration is needed.
- Any query that opened the knowledge store is followed by a release; the long-lived MCP process does not retain it.

---

## 4. References

- Rust lance: `lance::dataset::Dataset` – no explicit close; drop to release.
- Our cache: `packages/rust/crates/omni-vector/src/ops/cache.rs` – `DatasetCache::remove` drops the `Dataset`.
- Our eviction: `omni.foundation.bridge.rust_vector.evict_vector_store_cache`, `omni.foundation.services.vector.evict_knowledge_store_after_use`.
- Kernel: `packages/python/core/src/omni/core/kernel/engine.py` – after each `execute_tool`, calls `evict_knowledge_store_after_use()`.
