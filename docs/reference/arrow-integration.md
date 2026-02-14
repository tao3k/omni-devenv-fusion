# Arrow Integration (Rust ↔ Python)

> Zero-copy and batch paths for vector/tool search and knowledge analytics.

See also: [Search Result Batch Contract](search-result-batch-contract.md), [Vector Search Options Contract](vector-search-options-contract.md), [Python Arrow Integration Plan](python-arrow-integration-plan.md).

---

## 1. Overview

| Layer      | Capability                                                                                               | Status |
| ---------- | -------------------------------------------------------------------------------------------------------- | ------ |
| **Rust**   | Dictionary encoding (skill_name, category, tool_name)                                                    | ✅     |
| **Rust**   | ListArray (routing_keywords, intents)                                                                    | ✅     |
| **Rust**   | RecordBatch IPC: `search_optimized_ipc`                                                                  | ✅     |
| **Rust**   | RecordBatch IPC: `search_tools_ipc`                                                                      | ✅     |
| **Rust**   | Analytics IPC (e.g. table health)                                                                        | ✅     |
| **Python** | `list_all_tools_arrow()`, `list_all_arrow()`, `get_skill_index_arrow()`                                  | ✅     |
| **Python** | `search_tools()` prefers IPC → `ToolSearchPayload.from_arrow_table`                                      | ✅     |
| **Python** | `VectorPayload.from_arrow_table`, `HybridPayload.from_arrow_table`, `ToolSearchPayload.from_arrow_table` | ✅     |
| **Python** | Knowledge: `get_knowledge_dataframe()` uses `list_all_arrow()`                                           | ✅     |

---

## 2. When to use which path

- **Vector search**: Prefer `search_optimized_ipc` when available; decode to `pyarrow.Table` and use `VectorPayload.from_arrow_table(table)` for batch parsing. Fallback: `search_optimized` (JSON).
- **Tool search**: `search_tools()` already prefers IPC when the binding has `search_tools_ipc`; it returns `list[dict]` built from `ToolSearchPayload.from_arrow_table`, so downstream `parse_tool_search_payload(d)` is cheap (no JSON).
- **List all tools / knowledge**: Use `list_all_tools_arrow()` or `list_all_arrow(table_name)` to get a `pyarrow.Table` directly instead of list-of-dicts + `from_pylist`.
- **Knowledge analytics**: `get_knowledge_dataframe(collection)` returns a Table via `store.list_all_arrow(collection)` (Arrow-native, no dict list → Table conversion).

---

## 3. Usage examples

### 3.1 Vector search (IPC)

```python
import io
import pyarrow.ipc
from omni.foundation.bridge.rust_vector import RustVectorStore
from omni.foundation.services.vector_schema import VectorPayload

store = RustVectorStore(index_path="path/to/db.lance")
ipc_bytes = store.search_optimized_ipc("knowledge", query_vector, limit=10)
table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
payloads = VectorPayload.from_arrow_table(table)
```

### 3.2 Tool search (Arrow path inside bridge)

`search_tools()` uses IPC when available and returns the same `list[dict]` shape; each dict is parseable with `parse_tool_search_payload`:

```python
from omni.foundation.bridge.rust_vector import RustVectorStore
from omni.foundation.services.vector_schema import parse_tool_search_payload

store = RustVectorStore(index_path="path/to/skills.lance")
results = await store.search_tools("skills", query_vector, limit=5, threshold=0.0)
for d in results:
    payload = parse_tool_search_payload(d)  # no JSON; dict from Arrow batch
```

### 3.3 List all as Table

```python
store = RustVectorStore(index_path="path/to/db.lance")
tools_table = store.list_all_tools_arrow()
entries_table = store.list_all_arrow("knowledge")
```

### 3.4 Knowledge analytics (Arrow-native)

```python
from omni.core.knowledge.analyzer import get_knowledge_dataframe

table = get_knowledge_dataframe("knowledge")
if table is not None:
    # table is pyarrow.Table (id, content, ...)
    n = table.num_rows
```

### 3.5 Payload from Table (batch parse)

```python
from omni.foundation.services.vector_schema import ToolSearchPayload

# table has columns: name, description, score, skill_name, tool_name, ...
payloads = ToolSearchPayload.from_arrow_table(table)
```

---

## 4. Implementation locations

| Item                                                  | Location                                                                   |
| ----------------------------------------------------- | -------------------------------------------------------------------------- |
| Rust `search_optimized_ipc`, `search_results_to_ipc`  | `packages/rust/crates/omni-vector/src/search/search_impl.rs`               |
| Rust `search_tools_ipc`, `tool_search_results_to_ipc` | `packages/rust/crates/omni-vector/src/search/search_impl.rs`               |
| Binding `search_tools_ipc`                            | `packages/rust/bindings/python/src/vector/search_ops.rs`, `mod.rs`         |
| Python `search_tools()` IPC path                      | `packages/python/foundation/src/omni/foundation/bridge/rust_vector.py`     |
| `*Payload.from_arrow_table`                           | `packages/python/foundation/src/omni/foundation/services/vector_schema.py` |
| `get_knowledge_dataframe` Arrow path                  | `packages/python/core/src/omni/core/knowledge/analyzer/__init__.py`        |
