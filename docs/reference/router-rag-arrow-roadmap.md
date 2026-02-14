# Router & RAG Arrow Roadmap

> Current state and next steps for Arrow (IPC / zero-copy) in router and RAG modules.

See also: [Python Arrow Integration Plan](python-arrow-integration-plan.md), [Vector Store API](vector-store-api.md).

---

## 1. Current state

### 1.1 Router (hybrid_search, indexer)

| Component               | Data path                                                                                                                               | Arrow support                                                       |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **hybrid_search.py**    | Rust `search_tools` / `search_hybrid` → list of JSON strings or dicts → `parse_tool_search_payload(dict)` / `parse_hybrid_payload(raw)` | **No**. All results are dict/JSON; no IPC path for tool search yet. |
| **indexer.py**          | Reads from store; builds payloads; uses `parse_tool_search_payload(dict)` when parsing Rust output                                      | **No** Arrow path.                                                  |
| **Router route_hybrid** | Calls hybrid search → list of dicts → `build_tool_router_result` / RouteResult                                                          | Depends on hybrid_search; no Arrow.                                 |

**Conclusion:** Router remains JSON/dict until Rust exposes a tool-search IPC API (e.g. `search_tools_ipc` returning a RecordBatch). Then we can wire `ToolSearchPayload.from_arrow_table` / `from_arrow_columns` in hybrid_search and indexer.

### 1.2 RAG (librarian, dual_core, zk)

| Component                               | Data path                                                                                                                                                                             | Arrow support                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **librarian.py**                        | `vector_search` uses `VectorStoreService.search()` which **prefers `search_optimized_ipc`**; builds list of dicts via `VectorPayload.from_arrow_table`; fallback JSON path on failure | **Yes**. Vector path is already Arrow when store has IPC.         |
| **dual_core** (fusion, kg_recall, etc.) | Consumes search results (list of dicts or payloads); no direct Arrow input                                                                                                            | **Partial**. Input is still list-based; could accept Table later. |
| **zk_search, zk_enhancer**              | Use librarian or vector store; benefit from IPC where vector search is used                                                                                                           | Same as librarian.                                                |

**Conclusion:** RAG vector search is already on the Arrow path where the store supports IPC. Dual-core and other RAG layers can be refactored to accept `pa.Table` or Arrow columns when we want to avoid building intermediate lists.

---

## 2. Recommended next steps

### 2.1 Router

1. **Rust:** Add `search_tools_ipc` (and optionally `search_hybrid_ipc`) returning Arrow IPC stream bytes (RecordBatch with tool_name, file_path, routing_keywords, intents, score, etc.).
2. **Python:** In `hybrid_search.py`, when the store has `search_tools_ipc`, call it, decode to Table, and build results via `ToolSearchPayload.from_arrow_table`; fallback to current JSON path.
3. **indexer:** If the store exposes a tool-list IPC (e.g. `list_all_tools_ipc`), use it and `ToolSearchPayload.from_arrow_table` for bulk load.

### 2.2 RAG (optional)

- **Dual-core:** Add overloads or helpers that accept `pa.Table` (e.g. for fusion input) and build in-memory structures from columns instead of list-of-dicts.
- **Knowledge graph / ZK:** Already benefit from librarian’s vector IPC path; no change required for current behavior.

---

## 3. Implementation locations

| Item                  | File(s)                                                                                                                                            |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rust tool-search IPC  | `packages/rust/crates/omni-vector` (search), `packages/rust/bindings/python` (expose to Python)                                                    |
| Hybrid search use IPC | `packages/python/core/src/omni/core/router/hybrid_search.py`                                                                                       |
| Indexer use IPC       | `packages/python/core/src/omni/core/router/indexer.py`                                                                                             |
| Payload from Table    | Already in `packages/python/foundation/src/omni/foundation/services/vector_schema.py` (`ToolSearchPayload.from_arrow_table`, `from_arrow_columns`) |

---

## 4. Summary

| Module                          | Arrow status                   | Blocker / next step                    |
| ------------------------------- | ------------------------------ | -------------------------------------- |
| **Vector search**               | Done (IPC + from_arrow_table)  | —                                      |
| **Librarian vector_search**     | Done (uses IPC when available) | —                                      |
| **Router hybrid / tool search** | Not started                    | Rust `search_tools_ipc` (and bindings) |
| **RAG dual_core**               | Optional (Table input)         | Product need; refactor when useful     |
