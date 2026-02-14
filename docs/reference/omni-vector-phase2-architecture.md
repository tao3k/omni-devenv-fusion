# Omni-Vector Phase 2: Connection Pool, Async Index Build, Compression

Design scope for architectural follow-ups from [milestone 2026-02](milestones/2026-02-omni-vector-optimization-and-arrow-native.md). See [backlog](../backlog.md) for task status.

---

## 1. Current State

| Area               | Current behavior                                                                                                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dataset access** | `VectorStore` holds `datasets: Arc<Mutex<DashMap<String, Dataset>>>`. `get_or_create_dataset` opens once per table and caches; no max size or eviction.                                         |
| **Index building** | `create_index`, `create_hnsw_index`, `create_btree_index`, `create_fts_index` are all `async` and **block the caller** until the index is built. `auto_index_if_needed` runs them sequentially. |
| **Serialization**  | Arrow RecordBatch for Lance; metadata as JSON strings (single-pass + simd-json in writer). No extra compression on vector or metadata columns.                                                  |

---

## 2. Connection Pool (连接池)

**Goal:** Control memory and reuse when many tables or many concurrent operations are used.

**Current:** In-process cache keyed by table name; one `Dataset` per table, kept for store lifetime.

**Options:**

- **A. Bounded cache with eviction:** Cap `datasets` size (e.g. max N tables); evict least-recently-used when full. Requires refcounting or TTL so evicted tables can be reopened.
- **B. Remote LanceDB:** If we add a client for remote LanceDB, a connection pool (e.g. connection-per-URI or HTTP client pool) would live there; out of scope for current embedded-only setup.

**Delivered:** `DatasetCache` in `ops/cache.rs` with optional `max_cached_tables`; LRU eviction when at capacity. Use `VectorStore::new_with_cache_options(path, dimension, DatasetCacheConfig { max_cached_tables: Some(n) })`. Default `new()` remains unbounded.

---

## 3. Async Index Building (异步建索引)

**Goal:** Avoid blocking the caller for the full duration of index build (HNSW/IVF/FTS/BTree can be slow on large tables).

**Options:**

- **A. Fire-and-forget API:** `create_index_background(table_name)` spawns a tokio task that runs `create_index` (and optionally FTS/scalar); returns immediately. Caller gets no completion signal unless we add a way to query “index build in progress” or store a `JoinHandle`.
- **B. Return a future / handle:** Same spawn, but return something awaitable (e.g. `JoinHandle`) so the caller can `await` when they need the index.
- **C. Lance-native async:** If Lance later exposes a non-blocking index build API, we could adopt it instead of spawning.

**Recommendation:** Implement (A) or (B) as a thin wrapper: spawn `create_index` (and optionally other indices) in a task; document that “index may not be available until the task completes.” Optional: store pending tasks in the store and expose `await_pending_index_builds()` or a callback when build finishes.

**Delivered:** `create_index_background(table_name)` in Rust (spawns index build, returns immediately; errors logged). Python binding optional.

---

## 4. Compressed Serialization (压缩序列化)

**Goal:** Reduce disk and, if applicable, network usage for vectors and/or metadata.

**Options:**

- **A. Arrow compression:** Use Lance/Arrow column compression (e.g. for vector or metadata columns) if supported and enabled in write params.
- **B. Smaller metadata encoding:** Replace raw JSON strings with a more compact format (e.g. MessagePack, or fixed schema binary) for the metadata column; requires read-path support.
- **C. Vector quantization:** Already partially in scope via IVF; further compression (e.g. PQ) is an index choice rather than “serialization” per se.

**Delivered:** (A) Lance V2_1 storage via `WriteParams { data_storage_version: Some(LanceFileVersion::V2_1), .. }`. New tables and appends use `default_write_params()` in `writer_impl.rs` (create and both append paths). Dependency `lance-file = "2.0"` added for `LanceFileVersion`. Snapshot tests updated for V2_1 version counts.

---

## 5. Backlog Mapping

| Backlog item | Design section | Implementation note                                  |
| ------------ | -------------- | ---------------------------------------------------- |
| 连接池       | §2             | Bounded cache + LRU when needed                      |
| 异步建索引   | §3             | `create_index_background` + optional handle/callback |
| 压缩序列化   | §4             | V2_1 WriteParams for create + append (done)          |

---

## 6. References

- [LanceDB Version and Roadmap](lancedb-version-and-roadmap.md)
- [Omni-Vector Status](omni-vector-status.md)
- [Milestone 2026-02](milestones/2026-02-omni-vector-optimization-and-arrow-native.md)
- [Backlog](../backlog.md)
