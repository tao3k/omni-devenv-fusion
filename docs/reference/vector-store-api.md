# Vector Store API Reference

> RustVectorStore, payload schemas, and Arrow IPC usage.

See also: [Search Result Batch Contract](search-result-batch-contract.md), [Python Arrow Integration Plan](python-arrow-integration-plan.md), [Omni-Vector Status](omni-vector-status.md).

---

## 1. RustVectorStore (Python bridge)

**Module:** `omni.foundation.bridge.rust_vector`

| Method                                                                                      | Description                                                                                                                                                    |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RustVectorStore(index_path, embedding_dim, keyword_index)`                                 | Create store; `embedding_dim` (e.g. 384), `keyword_index` for FTS.                                                                                             |
| `search_optimized(table_name, query_vector, limit, options_json=None)`                      | Vector search; returns list of JSON strings.                                                                                                                   |
| `search_optimized_ipc(table_name, query_vector, limit, options_json=None, projection=None)` | Vector search; returns **Arrow IPC stream bytes**. Optional `projection` (e.g. `["id", "content", "_distance", "metadata"]`) reduces payload for batch search. |
| `search_hybrid(table_name, query_vector, keywords, limit)`                                  | Hybrid (vector + keyword) search; returns list of JSON strings.                                                                                                |
| `search_tools(table_name, query_vector, keywords, limit)`                                   | Tool search; returns list of JSON strings.                                                                                                                     |
| `analyze_table_health(table_name)`                                                          | Table health report (dict).                                                                                                                                    |
| `analyze_table_health_ipc(table_name)`                                                      | Table health as **Arrow IPC bytes** (single-row RecordBatch).                                                                                                  |
| `compact(table_name)`                                                                       | Compact table; returns dict with fragments_before/after, duration_ms.                                                                                          |
| `get_query_metrics(table_name)`                                                             | In-process query count and latency (dict).                                                                                                                     |
| `list_all_tools()`                                                                          | All tools as list of dicts.                                                                                                                                    |
| `list_all_tools_arrow()`                                                                    | All tools as **pyarrow.Table** (same data).                                                                                                                    |
| `get_skill_index_arrow(base_path)`                                                          | Skill index as **pyarrow.Table**.                                                                                                                              |
| `list_all(table_name)`                                                                      | All rows as list of dicts.                                                                                                                                     |
| `list_all_arrow(table_name)`                                                                | All rows as **pyarrow.Table**.                                                                                                                                 |

### 1.1 Vector search (IPC path)

Prefer IPC when you want to avoid JSON encode/decode and build payloads from a Table:

```python
import io
import pyarrow.ipc
from omni.foundation.bridge.rust_vector import RustVectorStore
from omni.foundation.services.vector_schema import VectorPayload

store = RustVectorStore(index_path="/path/to/lance", embedding_dim=384, keyword_index=True)
query_vector = [0.1] * 384  # or from embedding service

ipc_bytes = store.search_optimized_ipc("skills", query_vector, limit=10)
table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
payloads = VectorPayload.from_arrow_table(table)
for p in payloads:
    print(p.id, p.content, p.distance)
```

### 1.2 Table health (IPC path)

```python
from omni.test_kit.fixtures.arrow import decode_table_health_ipc_bytes, assert_table_health_ipc_table

ipc_bytes = store.analyze_table_health_ipc("skills")
table = decode_table_health_ipc_bytes(ipc_bytes)
assert_table_health_ipc_table(table)
row_count = table.column("row_count")[0].as_py()
```

---

## 2. Payload schemas (vector_schema.py)

**Module:** `omni.foundation.services.vector_schema`

### 2.1 VectorPayload

Used for vector-only search results (id, content, distance, metadata).

| Class method                                      | Use                                                                     |
| ------------------------------------------------- | ----------------------------------------------------------------------- |
| `VectorPayload.parse_raw_json(raw: str)`          | Parse one JSON string from Rust.                                        |
| `VectorPayload.from_arrow_table(table: pa.Table)` | Build list from IPC Table (columns: id, content, \_distance, metadata). |

### 2.2 HybridPayload

Used for hybrid (vector + keyword) results; includes vector_score, keyword_score.

| Class method                                                               | Use                                                                                         |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `HybridPayload.parse_raw_json(raw: str)`                                   | Parse one JSON string.                                                                      |
| `HybridPayload.from_arrow_table(table: pa.Table)`                          | Build list from Table (id, content, score; optional metadata, vector_score, keyword_score). |
| `HybridPayload.from_arrow_columns(ids=..., contents=..., scores=..., ...)` | Build list from Arrow columns (no JSON).                                                    |

### 2.3 ToolSearchPayload

Used for tool-search results (tool_name, file_path, routing_keywords, intents, etc.).

| Class method                                                                                  | Use                                             |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `ToolSearchPayload.from_mapping(data: dict)`                                                  | Validate dict from Rust.                        |
| `parse_tool_search_payload(data: dict)`                                                       | Parse/validate dict; returns ToolSearchPayload. |
| `ToolSearchPayload.from_arrow_table(table: pa.Table)`                                         | Build list from Table.                          |
| `ToolSearchPayload.from_arrow_columns(ids=..., contents=..., scores=..., tool_name=..., ...)` | Build list from Arrow columns.                  |

### 2.4 Building results from Arrow columns (no JSON)

When you already have a pyarrow Table or columns (e.g. from a future Rust `search_tools_ipc`):

```python
from omni.foundation.services.vector_schema import ToolSearchPayload

# From Table columns:
payloads = ToolSearchPayload.from_arrow_columns(
    ids=table["id"],
    contents=table["content"],
    scores=table["score"],
    tool_name=table["tool_name"],
    file_path=table["file_path"],
)
```

---

## 3. VectorStoreClient (Foundation service)

**Module:** `omni.foundation.services.vector`

Singleton client that uses RustVectorStore when available. It **prefers the IPC path** for vector search:

- `VectorStoreClient().search(collection, query, n_results)` uses `search_optimized_ipc` when the store has it, then `VectorPayload.from_arrow_table`; falls back to `search_optimized` + `parse_vector_payload` on failure.

So callers using `VectorStoreClient` get the Arrow path automatically when the binding supports it.

---

## 4. Search options

- `build_search_options_json(options: dict)` — Build JSON string for Rust (where_filter, batch_size, fragment_readahead, etc.).
- `SearchOptionsContract` — Pydantic model for options validation.

---

## 5. Related docs

| Topic            | Document                                                          |
| ---------------- | ----------------------------------------------------------------- |
| IPC batch schema | [Search Result Batch Contract](search-result-batch-contract.md)   |
| Arrow roadmap    | [Python Arrow Integration Plan](python-arrow-integration-plan.md) |
| Router/hybrid    | [Vector/Router Schema Contract](vector-router-schema-contract.md) |
| CLI for db       | [CLI Reference](cli.md) (omni db health, compact, index create)   |
