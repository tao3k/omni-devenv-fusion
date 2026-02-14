# Arrow Ecosystem Deep Optimization (LanceDB / omni-vector)

> Priorities and implementation order follow the Arrow Ecosystem Deep Optimization report; this document records the roadmap and completed items.

---

## 1. Priority Overview

### P0 (Immediate)

| Direction                             | Benefit                | Complexity | Scope                             | Status   |
| ------------------------------------- | ---------------------- | ---------- | --------------------------------- | -------- |
| ListArray instead of delimiters       | High (storage + query) | Medium     | writer_impl, search_impl, parsing | Pending  |
| **Dictionary encoding for tool_name** | **Medium (storage)**   | **Low**    | **writer_impl, core.rs schema**   | **Done** |

### P1 (Next)

| Direction                    | Benefit           | Complexity | Status              |
| ---------------------------- | ----------------- | ---------- | ------------------- |
| RecordBatch zero-copy return | Medium (transfer) | Medium     | Done                |
| Rust compute kernels         | Medium (compute)  | Medium     | Partial (see below) |

### P2 (Long-term)

| Direction                       | Benefit | Complexity | Status  |
| ------------------------------- | ------- | ---------- | ------- |
| Struct instead of metadata JSON | High    | High       | Pending |
| FixedSizeBinary compression     | Medium  | Low        | Pending |

---

## 2. Recommended Implementation Order

1. **Dictionary encoding for tool_name** (simplest, clear benefit) — **Done**
2. ListArray for routing_keywords / intents (larger change, high benefit)
3. RecordBatch zero-copy return for search results
4. Rust compute kernels to replace hand-written loops

---

## 3. Done: P0 Dictionary Encoding for tool_name

**Goal:** Change the `TOOL_NAME` column from `Utf8` to `Dictionary(Int32, Utf8)`, aligned with `SKILL_NAME` and `CATEGORY`, to reduce storage and scalar index cost.

### 3.1 Change Summary

| Area   | File                                        | Content                                                                                                       |
| ------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Schema | `omni-vector/src/ops/core.rs`               | `TOOL_NAME` uses `Field::new_dictionary(Int32, Utf8)`; metadata adds `index_hint: bitmap`, `cardinality: low` |
| Write  | `omni-vector/src/ops/writer_impl.rs`        | New `build_string_dictionary(values)`; `build_document_batch` encodes tool_name as Dictionary                 |
| Read   | `omni-vector/src/search/search_impl.rs`     | FTS result build: `opt_str` → `opt_utf8` (uses `get_utf8_at`), compatible with Utf8 and Dictionary            |
| Read   | `omni-vector/src/skill/ops_impl.rs`         | Two places reading tn/fp/rk/in from batch use `str_at_col(col, i)` (`get_utf8_at`), no StringArray downcast   |
| Tests  | `omni-vector/tests/test_schema_encoding.rs` | Assert `TOOL_NAME` is Dictionary; roundtrip comment covers skill_name / category / tool_name                  |

### 3.2 Compatibility

- **New tables:** `create_schema()` returns a schema where `TOOL_NAME` is Dictionary; writes use `build_document_batch` to produce Dictionary columns.
- **Existing tables:** If `TOOL_NAME` is still Utf8, the read path uses `get_utf8_at` (column_read.rs supports both StringArray and Dictionary); behavior unchanged.
- **Migration:** No automatic migration from Utf8 to Dictionary for existing tables; schema evolution or table rewrite can be added later if needed.

### 3.3 Verification

- `cargo test -p omni-vector --test test_schema_encoding` and `--test test_rust_cortex` pass.
- Related docs: [Omni-Vector Audit & Next Steps](omni-vector-audit-and-next-steps.md), [2026-02 Omni-Vector Optimization](../milestones/2026-02-omni-vector-optimization-and-arrow-native.md).

---

## 4. Pending Items (Summary)

- **ListArray instead of delimiters:** Store `routing_keywords` and `intents` as `List<Utf8>` instead of space/pipe-joined Utf8; update write and parse paths to use list read/write.
- **RecordBatch zero-copy return:** Return search results as Arrow RecordBatch / IPC stream for Python (pyarrow) to consume, reducing serialization/deserialization.
- **Rust compute kernels (partial):** `keyword/fusion/kernels.rs` provides scalar `rrf_term`, batch `rrf_term_batch`, and `distance_to_score`; all RRF fusion paths use `rrf_term`. `lowercase_string_array` in match_util is the swap-in for an Arrow string kernel when available. Arrow `compute::filter` for search batches is deferred (lance vs workspace arrow type alignment).
- **Struct instead of metadata JSON:** Replace part or all of the metadata column with Arrow Struct for columnar filtering and zero-copy.
- **FixedSizeBinary compression:** Use FixedSizeBinary for fixed-length binary fields to save storage.

---

## 5. Related Documents

| Document                                                                                               | Description                                                 |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| [LanceDB Version and Roadmap](lancedb-version-and-roadmap.md)                                          | Lance 2.x and Phase 1–5                                     |
| [Omni-Vector Status](omni-vector-status.md)                                                            | Feature matrix and Python API                               |
| [Omni-Vector Audit & Next Steps](omni-vector-audit-and-next-steps.md)                                  | P0–P3 and LanceDB 2.x alignment                             |
| [2026-02 Omni-Vector Optimization](../milestones/2026-02-omni-vector-optimization-and-arrow-native.md) | Arrow-native 10-column schema and performance optimizations |
