# Python Arrow Integration Plan

> Roadmap to reduce JSON serialization/parsing and adopt Arrow (IPC / pyarrow.Table) for search and payloads.

See also: [Search Result Batch Contract](search-result-batch-contract.md), [Vector Search Options Contract](vector-search-options-contract.md).

---

## 1. Current state vs report

| Layer     | Problem area                 | JSON use                                    | Status                                                                                   |
| --------- | ---------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Bridge    | rust_vector.py               | 15+ JSON serialize/parse                    | IPC path exists for vector search (`search_optimized_ipc`); tool search still dict/JSON. |
| Search    | hybrid_search.py, indexer.py | Per-result parse_tool_search_payload        | Callers receive list of dicts; no Arrow path yet for tool search.                        |
| Payload   | vector_schema.py             | parse_raw_json → Pydantic                   | No `from_arrow_columns` / `from_arrow_table` yet.                                        |
| Knowledge | librarian.py, rag/analyzer   | \_parse_search_results (json.loads per row) | Can switch to IPC when store exposes it and payload supports Arrow.                      |

**Already done**

- **Rust**: `search_optimized_ipc` returns Arrow IPC stream bytes (RecordBatch: id, content, tool_name, file_path, routing_keywords, intents, \_distance, metadata).
- **Python**: `RustVectorStore.search_optimized_ipc()` returns `bytes`; caller can do `pyarrow.ipc.open_stream(io.BytesIO(bytes)).read_all()` to get a Table.
- No caller currently uses the IPC path; all still use `search_optimized` (JSON strings) or `search_tools` (list of dicts).

---

## 2. Recommended order

### 1) Search results Arrow direct (highest benefit)

- **Current**: Rust → list of JSON strings or list of dicts → Python parses each → Pydantic.
- **Target**: Rust RecordBatch → IPC bytes → `pyarrow.Table` → batch build Pydantic (or SearchResult) from columns.

**Sub-steps**

| Step | What                                                                                                                                                           | Where                                         |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| 1a   | Add `VectorPayload.from_arrow_table(table)` (and/or `from_arrow_columns`)                                                                                      | vector_schema.py                              |
| 1b   | In vector search path, use `search_optimized_ipc` when available; build results from Table via `VectorPayload.from_arrow_table`; fallback to current JSON path | vector.py, optionally librarian.py            |
| 1c   | (Later) Add Rust `search_tools_ipc` returning tool-search batch; Python `ToolSearchPayload.from_arrow_table` and use in hybrid_search / indexer                | Rust + vector_schema + hybrid_search, indexer |

**Benefit**: 30–50% search latency reduction on vector path by skipping JSON encode/decode (estimate; measure on real workloads).

### 2) Payload native Arrow construction

- Add `HybridPayload.from_arrow_columns(...)` and `ToolSearchPayload.from_arrow_columns(...)` so that any caller with a Table can build payloads without going through JSON.
- Reduces double parsing (JSON → dict → Pydantic) wherever we already have Arrow columns.

### 3) RustVectorStore methods Arrow-ify

- Add Arrow-returning variants where useful: e.g. `list_all_tools_arrow()` → `pa.Table`, `get_skill_index_arrow()`, and have `merge_insert_documents` (or equivalent) return Arrow metadata when applicable.
- Unifies the interface and encourages Table-based pipelines.

---

## 3. Implementation locations (after Phase 1)

| Item                            | File(s)                                                                     |
| ------------------------------- | --------------------------------------------------------------------------- |
| VectorPayload.from_arrow_table  | packages/python/foundation/src/omni/foundation/services/vector_schema.py    |
| Vector search use IPC           | packages/python/foundation/src/omni/foundation/services/vector.py           |
| Knowledge vector_search use IPC | packages/python/core/src/omni/core/knowledge/librarian.py                   |
| Tool search IPC (later)         | Rust: search_tools_ipc; Python: vector_schema, hybrid_search.py, indexer.py |

---

## 4. Phase 1 done (1a + 1b)

- **1a**: `VectorPayload.from_arrow_table(table)` in `vector_schema.py` — builds list of VectorPayload from a pyarrow Table (id, content, \_distance, metadata columns).
- **1b**: `VectorStoreService.search()` in `vector.py` prefers `search_optimized_ipc` when the store has it; builds results via `VectorPayload.from_arrow_table`; falls back to `search_optimized` + `parse_vector_payload` on failure or when IPC is unavailable.
- **Test**: `test_vector_payload_from_arrow_table` in `test_vector_schema.py`.

**Phase 1 follow-up (done)**

- **librarian.vector_search** uses `search_optimized_ipc` when the store has it; builds list of dicts via `VectorPayload.from_arrow_table`; falls back to `search_optimized` + `_parse_search_results` on failure.
- **Payload native Arrow construction**: `HybridPayload.from_arrow_columns(ids=..., contents=..., scores=..., metadata=..., vector_score=..., keyword_score=...)` and `ToolSearchPayload.from_arrow_columns(ids=..., contents=..., scores=..., tool_name=..., file_path=..., routing_keywords=..., intents=..., metadata=..., skill_name=..., category=...)` in `vector_schema.py`; callers with a Table can pass columns and get payloads without JSON.

**Phase 3 (done)**

- **RustVectorStore Arrow-ified methods** (Python-side: reuse existing JSON API, convert to Table):
  - `list_all_tools_arrow()` → `pa.Table` (same data as `list_all_tools()`).
  - `get_skill_index_arrow(base_path)` → `pa.Table` (same data as `get_skill_index_sync()`).
  - `list_all_arrow(table_name)` → `pa.Table` (same data as `list_all(table_name)`).
- Helper `_list_of_dicts_to_table(rows)` in `rust_vector.py`: builds `pa.Table` from list of dicts; nested dict/list values are JSON-encoded so schema is consistent.

**Next**: When Rust exposes tool-search IPC, wire `ToolSearchPayload.from_arrow_columns` into hybrid_search; or add Rust-side `list_all_tools_ipc` for true zero-copy Table.

---

## 5. Future optimizations

| Direction                     | Benefit                                                                               | Notes                                                                                                                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Batch search (limit 100+)** | Arrow advantage scales with row count; one RecordBatch vs N JSON strings.             | Benchmark with `--limit 100`; prefer IPC path for large result sets. See [JSON vs Arrow Performance](json-vs-arrow-performance.md) §5.1.                                                 |
| **Column projection**         | Read only needed columns; less I/O and memory when caller needs e.g. id + score only. | Rust: optional `projection` in `search_optimized_ipc`; or Python: `table.select(columns)` before `from_arrow_table`. See [JSON vs Arrow Performance](json-vs-arrow-performance.md) §5.2. |
