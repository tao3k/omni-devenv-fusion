# Search Result Batch Contract (IPC)

> Optional zero-copy path: vector search can return a single Arrow RecordBatch as IPC stream bytes.

See also: [Vector Search Options Contract](vector-search-options-contract.md), [Schema Migration](schema-migration.md).

---

## 1. Scope

- **Rust**: `VectorStore::search_optimized_ipc(...)` returns `Result<Vec<u8>, VectorStoreError>` (Arrow IPC stream bytes).
- **Python**: Caller can use `pyarrow.ipc.open_stream(io.BytesIO(bytes)).read_all()` to get a `pyarrow.Table` without building a list of dicts.

The existing `search_optimized` / `search_tools` continue to return list-of-dicts; the IPC path is additive.

---

## 2. Batch schema

Single RecordBatch with columns (all nullable except where noted):

| Column             | Type         | Notes                                     |
| ------------------ | ------------ | ----------------------------------------- |
| `id`               | Utf8         | Result identifier (e.g. tool name).       |
| `content`          | Utf8         | Result content.                           |
| `tool_name`        | Utf8         | Tool name (Arrow-native).                 |
| `file_path`        | Utf8         | File path.                                |
| `routing_keywords` | List\<Utf8\> | Routing keywords (list of strings).       |
| `intents`          | List\<Utf8\> | Intents (list of strings).                |
| `_distance`        | Float64      | Distance from query vector.               |
| `metadata`         | Utf8         | JSON string of extra metadata (optional). |

Row order: by ascending `_distance` (nearest first), truncated to `limit`.

---

## 3. Python consumption

- **Bridge**: `RustVectorStore.search_optimized_ipc(table_name, query_vector, limit, options_json=None)` returns `bytes`.

```python
import io
import pyarrow.ipc
from omni.foundation.bridge.rust_vector import RustVectorStore

store = RustVectorStore(index_path="...")
bytes_ = store.search_optimized_ipc("skills", query_vector, limit=10)
table = pyarrow.ipc.open_stream(io.BytesIO(bytes_)).read_all()
# table is pyarrow.Table; columns as above
```

---

## 4. Implementation locations

- **Rust**: `packages/rust/crates/omni-vector/src/search/search_impl.rs` — `search_optimized_ipc`, `search_results_to_ipc`; builds batch from results, serializes with `arrow_ipc::writer::StreamWriter`.
- **Bindings**: `packages/rust/bindings/python/src/vector/search_ops.rs` — `search_optimized_ipc_async`; `mod.rs` exposes `search_optimized_ipc` returning `PyBytes`.
- **Python**: `omni.foundation.bridge.rust_vector.RustVectorStore.search_optimized_ipc` — returns bytes for zero-copy downstream.
