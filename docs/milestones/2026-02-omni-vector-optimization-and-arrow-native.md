# Milestone: Omni-Vector Depth Optimization & Arrow-Native Schema (Feb 2026)

**Status:** Completed  
**Scope:** Performance optimizations from the Omni-Vector analysis report and full migration to Arrow-native columns (no backward compatibility with 6-column tables).

---

## Summary

This milestone implemented the high- and medium-priority optimizations from the Omni-Vector depth analysis: parallel hybrid search, fusion path optimizations, single-pass metadata extraction, thin FTS metadata parsing, and a full Arrow-native schema (tool_name, file_path, routing_keywords, intents as columns). All new tables use the 10-column schema; legacy 6-column compatibility was removed.

---

## Delivered

### 1. Search and fusion performance

- **Parallel hybrid_search** (`search/search_impl.rs`): Vector and keyword queries run concurrently via `tokio::join!` instead of sequential await; `query_vector` is moved into the first future (no extra clone). **Expected:** ~50% latency reduction on hybrid path.
- **Fusion path** (`keyword/fusion.rs`): Precompute `name_lower_map` for field boosting to avoid repeated `to_lowercase()`; `keyword_context` uses `HashMap<&str, &ToolSearchResult>` and keyword stream uses `keyword_results.iter().enumerate()` so we avoid cloning full `ToolSearchResult` lists. **Expected:** fewer allocations and ~20% CPU reduction in fusion.

### 2. Write and read path (no full JSON tree)

- **writer_impl**
  - **Single-pass metadata:** One `serde_json::from_str::<MetadataExtract>` per row for scalar + Arrow-native columns (skill_name, category, tool_name, command, file_path, routing_keywords, intents). No full `Value` tree.
  - **Arrow-native columns:** Schema and `build_document_batch` extended with `tool_name`, `file_path`, `routing_keywords` (space-joined), `intents` (" | "-joined). `SkillCategoryExtract` replaced by `MetadataExtract`; all 10 columns filled in one pass.

- **search_impl (FTS)**
  - **Thin metadata struct:** `FtsMetadataRow` with only the fields needed for `ToolSearchResult`; one parse per row instead of full `Value` + many `.get()`.
  - **Arrow-first read:** FTS projects and reads `id`, `content`, `metadata`, `skill_name`, `category`, `tool_name`, `file_path`, `routing_keywords`, `intents` from Arrow when present; only `input_schema` (and fallbacks) come from metadata JSON.
  - **Fixed project list:** Always project the 9 columns above (no conditional schema check); tables are expected to be 10-column.

### 3. Schema and table lifecycle (new API only)

- **Constants** (`omni-lance`): `TOOL_NAME_COLUMN`, `FILE_PATH_COLUMN`, `ROUTING_KEYWORDS_COLUMN`, `INTENTS_COLUMN` added and re-exported from omni-vector.
- **create_schema():** Adds the four new Utf8 fields so all new tables have 10 columns.
- **get_or_create_dataset(..., initial):** Accepts `Option<(Schema, RecordBatch)>`. When creating a new table, if `initial` is `Some`, that batch is written (full 10-column schema); returns `(Dataset, created)` so callers skip appending when `created` is true.
- **add_documents:** Builds batch, calls `get_or_create_dataset(table_name, false, Some((schema, batch)))`; appends only when `!created`.
- **Backward compatibility removed:** No 6-column legacy fallback, no SchemaMismatch retry with projected batch. Old 6-column tables are no longer supported; FTS assumes 9-column project.

### 4. Reserved columns and docs

- **admin_impl:** `is_reserved_column` includes the four new column names.
- **Tests:** test_path_handling (incl. memory-mode twice add_documents), test_hybrid_search, test_lance_fts, test_rust_cortex, test_scalar_index, test_fusion all passing.

---

## Files touched (main)

| Area            | Path                                                         |
| --------------- | ------------------------------------------------------------ |
| Search          | `packages/rust/crates/omni-vector/src/search/search_impl.rs` |
| Fusion          | `packages/rust/crates/omni-vector/src/keyword/fusion.rs`     |
| Writer          | `packages/rust/crates/omni-vector/src/ops/writer_impl.rs`    |
| Schema / core   | `packages/rust/crates/omni-vector/src/ops/core.rs`           |
| Lance constants | `packages/rust/crates/omni-lance/src/lib.rs`                 |
| Exports         | `packages/rust/crates/omni-vector/src/lib.rs`                |
| Admin           | `packages/rust/crates/omni-vector/src/ops/admin_impl.rs`     |

---

## Out of scope (deferred) → Phase 2

- **Tantivy Writer reuse** — **Done (Phase 2).** `KeywordIndex` now caches a single `IndexWriter` in `RefCell<Option<IndexWriter>>` and reuses it across `bulk_upsert`, `upsert_document`, and `index_batch`; no per-call writer create/teardown. See [backlog](../backlog.md) Omni-Vector Phase 2.
- **simd-json** — **Done (Phase 2).** writer_impl uses `simd_json::serde::from_slice` for `MetadataExtract` and `serde_json::Value` in build_document_batch and keyword_docs paths; fallback to serde_json on parse error.
- **ListArray for routing_keywords/intents:** stored as single Utf8 (joined); split on read.

---

## References

| Topic                | Document                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| LanceDB roadmap      | [LanceDB Version and Roadmap](../reference/lancedb-version-and-roadmap.md)                                                      |
| Omni-Vector status   | [Omni-Vector Status](../reference/omni-vector-status.md)                                                                        |
| Phase 2 architecture | [Omni-Vector Phase 2 Architecture](../reference/omni-vector-phase2-architecture.md) (connection pool, async index, compression) |
| Backlog              | [Backlog](../backlog.md)                                                                                                        |
