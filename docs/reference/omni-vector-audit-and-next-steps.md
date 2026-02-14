# Omni-Vector Audit and Next Steps (LanceDB 2.x)

> Audit of the Omni-Vector status report and prioritized optimization and improvement recommendations, aligned with the LanceDB 2.x roadmap.

---

## 1. Audit Summary

### 1.1 Report vs Codebase

| Report item                 | Audit result                                                                                                                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| **Rust core modules**       | Matches `packages/rust/crates/omni-vector`: scalar, vector_index, maintenance, observability, agentic, partitioning, writer, admin, checkpoint, keyword, fusion, entity_aware implemented with unit tests.                                              |
| **Python bridge (done)**    | RustVectorStore, agentic_search, add_documents_partitioned, analyze_table_health, compact, get_query_metrics, get_index_cache_stats exist and map to PyO3 + rust_vector.py.                                                                             |
| **Python bridge (missing)** | Confirmed: create_btree_index, create_bitmap_index, create_hnsw_index, create_optimal_vector_index, suggest_partition_column, auto_index_if_needed were in Rust but not exposed in Python (now exposed in P0).                                          |
| **CLI**                     | This repo has **no** separate `lance-cli`; it uses **`omni db`**. Report “lance-cli health / compact” is **`omni db health`** / **`omni db compact`**, which **exist**. What was missing was index-by-type CLI (e.g. `omni db index create --type btree | hnsw`). |

### 1.2 LanceDB 2.x Roadmap Alignment

- **Dependencies**: `omni-vector` uses `lance = "2.0"`, `lance-index = "2.0"` (Cargo.toml); fully on 2.x.
- **Phases 1–5**: Scalar indices, Maintenance, Vector index, Partitioning, Observability are **Done** in [lancedb-version-and-roadmap.md](lancedb-version-and-roadmap.md), matching the report.
- **Query metrics**: `get_query_metrics` returns in-process counts and last latency when `agentic_search` runs (not from Lance tracing; can be wired to Lance when available).

---

## 2. Report Corrections and Clarifications

| Report text                                | Correction / clarification                                                                                                                                                                |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| “lance-cli health / compact missing”       | In this project provided by **`omni db health`**, **`omni db compact`**; **implemented**.                                                                                                 |
| “create lance-cli index --type btree/hnsw” | Interpret as: lack of **index-by-type** capability; extend **`omni db`** with `omni db index create --table T --type btree\|hnsw [--column COL]` rather than a separate lance-cli binary. |

---

## 3. Optimization and Improvement Priorities (LanceDB 2.x)

### P0: Expose Python Index/Maintenance API (1–2 days)

**Goal**: Parity between Python and Rust for Lance 2.x; enable sync, reindex, and scripts to create indices and get partition suggestions.

| Step | Content                                                                                                                                                                                                                                              | Outcome                                                                                                                                 |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | **PyO3**: In `packages/rust/bindings/python/src/vector/` add or extend store wrappers calling omni-vector’s create_btree_index, create_bitmap_index, create_hnsw_index, create_optimal_vector_index, suggest_partition_column, auto_index_if_needed. | PyVectorStore methods                                                                                                                   |
| 2    | **RustVectorStore**: In `foundation/bridge/rust_vector.py` add matching methods delegating to PyVectorStore (same pattern as analyze_table_health, compact).                                                                                         | create_btree_index, create_bitmap_index, create_hnsw_index, create_optimal_vector_index, suggest_partition_column, auto_index_if_needed |
| 3    | **Tests**: Add unit tests for the Python APIs (reuse Rust behavior where applicable).                                                                                                                                                                | pytest passing                                                                                                                          |

**LanceDB 2.x**: All APIs use current lance 2.0 `Dataset::create_index` (BTree/Bitmap/Vector/Inverted) and existing ops; no Lance version change.

---

### P1: Extend `omni db` CLI (~0.5–1 day) — Done

**Goal**: Allow explicit index creation by type for ops and debugging, without relying only on reindex/sync.

| Step | Content                                                                                                                                         | Outcome                                                                                                                      |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1    | Add subcommands under `omni db`, e.g. `omni db index create --table T --type btree --column COL`, `omni db index create --table T --type hnsw`. | **Done**: `omni db index create` with types btree, bitmap, hnsw, optimal-vector                                              |
| 2    | Implementation calls RustVectorStore methods (or PyVectorStore) from P0.                                                                        | **Done**: `_create_index` → store.create_btree_index / create_bitmap_index / create_hnsw_index / create_optimal_vector_index |
| 3    | Document in [cli.md](cli.md) the `omni db index create` usage.                                                                                  | **Done**: Quick reference table + subsection with examples                                                                   |

**Done**: `omni db partition-suggest <table>` calls `suggest_partition_column` for pre-partition decisions; supports `-d`/`--database` and `--json`.

---

### P2: Intent Classification and Agentic Enhancement (~1 week, optional) — Done

**Goal**: Align with report “intent classification enhancement”; improve routing and retrieval quality.

| Item                  | Description                                                                                       | Status                                                                                                                                               |
| --------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Intent classification | Rule-based (exact/hybrid) → optional **LLM-driven** intent for `agentic_search` intent parameter. | **Done**: `classify_tool_search_intent_with_llm`, `router.intent.use_llm` / `router.intent.model`, HybridSearch wired; fallback to rules on failure. |
| Weights and strategy  | Adaptive RRF/weights, query strategy learning; to be refined with product needs.                  | Todo                                                                                                                                                 |

**LanceDB 2.x**: Routing/retrieval logic only; no direct Lance version dependency.

---

### P3: Lance 2.x Ecosystem (Ongoing)

| Item                       | Description                                                                                                                                                                                                                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **QueryMetrics / Tracing** | **In-process wired:** `get_query_metrics` returns real `query_count` and `last_query_ms` from [VectorStore::record_query] when [agentic_search] runs; metrics are per store instance (not persisted). When Lance provides per-table/per-query tracing API, can be wired to that instead.                                        |
| **Index build progress**   | **Hook in place:** `IndexBuildProgress` (Started / Progress / Done) and optional `index_progress_callback` on VectorStore; `create_btree_index`, `create_bitmap_index`, `create_hnsw_index` emit Started and Done. Use `with_index_progress_callback()` in Rust; when Lance 2.x exposes progress API, emit `Progress(percent)`. |
| **Version upgrades**       | Track lance / lance-index 2.x minor releases (e.g. 2.1, 2.2); adopt new index types or APIs and run regression.                                                                                                                                                                                                                 |

---

## 4. Not Recommended or Deferred

| Item                                | Recommendation                                                                                                                                  |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Standalone lance-cli binary**     | **`omni db`** as single entry is enough for ops and debugging; consider a separate CLI only if a “Python-free, Rust-only” workflow is required. |
| **Distributed index / Time Travel** | Marked medium priority in report; plan when Lance 2.x roadmap for distributed and time travel is clearer.                                       |

---

## 5. Suggested Execution Order

1. **Immediate (1–2 days)**
   - Complete **P0**: Expose the six Python APIs and add tests.
   - Optionally do **P1**: `omni db index create`.

2. **Short term**
   - Complete **P1** if not done: `omni db index create`, optional `omni db partition-suggest`.
   - Update [omni-vector-status.md](omni-vector-status.md) gap list to “exposed”.

3. **Mid term**
   - **P2**: Intent enhancement (e.g. LLM), configurable weights/strategy.
   - **P3**: In-process query metrics wired; optional: wire to Lance 2.x tracing when available; index build progress when Lance exposes API.

---

## 6. Verification Checklist (LanceDB 2.x Regression)

```bash
# Rust (Lance 2.x behavior unchanged)
cargo test -p omni-vector test_scalar_index
cargo test -p omni-vector test_vector_index
cargo test -p omni-vector test_maintenance
cargo test -p omni-vector test_partitioning
cargo test -p omni-vector test_observability

# Python bridge and CLI
uv run pytest packages/python/foundation/tests/ -q -k "vector or rust_vector"
uv run omni db health
uv run omni db compact skills
```

After P0, add pytest for the new RustVectorStore methods and keep the above commands green.

---

## 7. Related Docs

- [Omni-Vector Status](omni-vector-status.md) — Feature matrix and gaps
- [LanceDB Version and Roadmap](lancedb-version-and-roadmap.md) — Phases 1–5 and 2.x upgrade
- [Backlog](../backlog.md) — Omni-Vector Python API entry
