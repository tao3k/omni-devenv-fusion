# LanceDB Version and Implementation Roadmap

## Current Version (Rust)

| Crate        | Workspace | Resolved (Cargo.lock) |
| ------------ | --------- | --------------------- |
| lance        | 2.0       | 2.0.0                 |
| lance-arrow  | 2.0       | 2.0.0                 |
| lance-index  | 2.0       | 2.0.0                 |
| lance-linalg | 2.0       | 2.0.0                 |

- **Source:** [crates.io lance](https://crates.io/crates/lance/versions), [crates.io lance-index](https://crates.io/crates/lance-index/versions). **lance 2.0.0** was released ~7 days before this doc (Lance Community).
- **Python:** `lancedb>=0.17.0` in `packages/python/foundation/pyproject.toml` (separate versioning).

## Upgrade 1.0 → 2.0 (Done)

The project **upgraded to lance 2.0** before implementing Phase 1 (Scalar Indices). All roadmap phases below are implemented on the 2.x stack.

- **2.0 breaking changes** we rely on or absorb: v2 manifest default, `create_index` returns `IndexMetadata`, storage options accessor, metric compatibility check for vector index.
- **Recommendation:** All new work uses **lance 2.x**.

## Implementation Roadmap (Lance 2.x)

| Phase       | Description                                                                                                                                                                                                            | Status   |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| **Phase 1** | Scalar indices (BTree, Bitmap) for `skill_name` / `category`; `create_btree_index`, `create_bitmap_index`, `create_optimal_scalar_index`; skill index writes trigger best-effort scalar index creation                 | **Done** |
| **Phase 2** | Auto-indexing and maintenance: `has_vector_index`, `has_fts_index`, `has_scalar_index`; `auto_index_if_needed` / `auto_index_if_needed_with_thresholds`; `compact(table)` (cleanup + compact_files), `CompactionStats` | **Done** |
| **Phase 3** | Vector index optimization: `create_hnsw_index` (IVF+HNSW), `create_optimal_vector_index` (HNSW &lt; 10k rows, IVF_FLAT ≥ 10k); min row thresholds                                                                      | **Done** |
| **Phase 4** | Partitioning: `suggest_partition_column(table)` — suggests `skill_name` or `category` when table has ≥ 10k rows; wired into `analyze_table_health` as `Recommendation::Partition { column }`                           | **Done** |
| **Phase 5** | Observability: `analyze_table_health(table)` → `TableHealthReport`; `get_query_metrics(table)` → `QueryMetrics` (in-process from agentic_search; can wire to Lance tracing when available)                             | **Done** |

### Phase 1 – Scalar indices

- **Location:** `packages/rust/crates/omni-vector/src/ops/scalar.rs`, `ops/types.rs` (`IndexStats`, `IndexThresholds`).
- **APIs:** `create_btree_index`, `create_bitmap_index`, `estimate_cardinality`, `create_optimal_scalar_index` (cardinality &lt; 100 → Bitmap, else BTree). Skill index write path calls `create_scalar_index` for `skill_name` (BTree) and `category` (Bitmap).
- **Tests:** `tests/test_scalar_index.rs`, snapshot `scalar_index_stats_contract_v1`.

### Phase 2 – Auto-indexing and maintenance

- **Location:** `packages/rust/crates/omni-vector/src/ops/maintenance.rs`, `ops/types.rs` (`CompactionStats`).
- **APIs:** `has_vector_index`, `has_fts_index`, `has_scalar_index` (via `describe_indices`), `auto_index_if_needed` / `auto_index_if_needed_with_thresholds`, `compact(table_name)`.
- **Tests:** `tests/test_maintenance.rs`, snapshot `maintenance_contract_v1`.

### Phase 3 – Vector index optimization

- **Location:** `packages/rust/crates/omni-vector/src/ops/vector_index.rs`.
- **APIs:** `create_hnsw_index` (IVF+HNSW, min 50 rows), `create_optimal_vector_index` (&lt; 10k → HNSW, ≥ 10k → IVF_FLAT; min 100 rows).
- **Tests:** `tests/test_vector_index.rs`, snapshot `vector_index_contract_v1`.

### Phase 4 – Partitioning

- **Location:** `packages/rust/crates/omni-vector/src/ops/partitioning.rs`.
- **APIs:** `suggest_partition_column(table_name)` → `Option<String>` (suggests `skill_name` or `category` when row count ≥ 10_000 and schema has the column). Used by `analyze_table_health` to add `Recommendation::Partition { column }`.
- **Tests:** `tests/test_partitioning.rs`, snapshot `partition_suggestion_contract_v1`.

### Phase 5 – Observability

- **Location:** `packages/rust/crates/omni-vector/src/ops/observability.rs`, `ops/types.rs` (`IndexStatus`, `Recommendation`, `TableHealthReport`, `QueryMetrics`).
- **APIs:** `analyze_table_health(table_name)` → `TableHealthReport`; `get_query_metrics(table_name)` → `QueryMetrics` (in-process: `query_count` and `last_query_ms` from agentic_search; can wire to Lance tracing when available).
- **Tests:** `tests/test_observability.rs`, snapshot `observability_contract_v1`.

## Implementation status summary

**Completed**

| Phase   | Feature                                                  | Status                                    |
| ------- | -------------------------------------------------------- | ----------------------------------------- |
| Phase 1 | `create_btree_index()`                                   | Done                                      |
|         | `create_bitmap_index()`                                  | Done                                      |
|         | `create_scalar_index()`                                  | Done                                      |
|         | `create_optimal_scalar_index()`                          | Done                                      |
| Phase 2 | `auto_index_if_needed()`                                 | Done                                      |
|         | `compact()`                                              | Done                                      |
|         | `cleanup_old_versions()`                                 | Done                                      |
| Phase 3 | `create_hnsw_index()`                                    | Done                                      |
|         | `create_optimal_vector_index()`                          | Done                                      |
| Phase 4 | `suggest_partition_column()`                             | Done                                      |
| Phase 5 | `analyze_table_health()`                                 | Done                                      |
|         | `QueryMetrics` / `get_query_metrics()`                   | Done (in-process; Lance tracing optional) |
| CLI     | `omni db health` / `compact` / `stats` / `query-metrics` | Done                                      |

**Gap analysis & next steps**

| Feature                            | Priority | Notes                                                                                                                                                                                                            |
| ---------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Agentic Search (intent routing) | P0       | **Done:** `QueryIntent`, optional filters, optional **intent_override** in `HybridSearch.search`, `SkillDiscoveryService.search_tools_async`, `SkillIndexer.search` so callers (e.g. LLM flows) can pass intent. |
| 2. Partitioning write              | P1       | **Done:** `suggest_partition_column()`, `add_documents_partitioned(...)` (Rust + Python), `vector.default_partition_column` in settings; `partition_by=None` uses default.                                       |
| 3. Observability CLI               | P1       | `omni db health`, `omni db compact`, `omni db query-metrics`, `omni db index-stats` done; remaining: real-time metrics when Lance tracing is wired.                                                              |
| 4. Index cache config              | P2       | **Done:** Rust `open_dataset_at_uri()` + `index_cache_size_bytes`; `omni db index-stats`; Python `RustVectorStore(..., index_cache_size_bytes=None)` and `create_vector_store(..., index_cache_size_bytes)`.     |

**Detailed gaps**

1. **Agentic Search (P0)**
   - Done: `ops/agentic.rs` with `QueryIntent` (Exact, Category, Semantic, Hybrid), `AgenticSearchConfig`, `agentic_search()`. Strategy: **Exact** = keyword-only when query_text set (fallback to hybrid if no keyword index); **Semantic** = vector-only; **Category** / **Hybrid** = full RRF. Python: `RustVectorStore.agentic_search(table_name, query_vector, query_text=None, limit=5, threshold=0.0, intent=None, ...)`; binding returns same tool dicts with confidence.
   - Done: rule-based intent classification in Python (`omni.core.router.query_intent.classify_tool_search_intent`). Query that looks like a single tool id (e.g. `git.commit`) → `exact`; else `hybrid`. Wired in `HybridSearch`, `SkillDiscoveryService.search_tools_async`, and `SkillIndexer` so they call `agentic_search(..., intent=classified)` when the store has `agentic_search`.
   - Done: optional `skill_name_filter` and `category_filter` on `AgenticSearchConfig`; `search_tools_with_options(..., where_filter)`; Python `agentic_search(..., skill_name_filter=..., category_filter=...)`.
   - Done: optional **intent_override** in Python: `HybridSearch.search(..., intent_override=...)`, `SkillDiscoveryService.search_tools_async(..., intent_override=...)`, `SkillIndexer.search(..., intent_override=...)`. Callers (e.g. LLM-based flows) can pass a precomputed intent instead of rule-based classification.

2. **Partitioning write (P1)**
   - Done: `suggest_partition_column()`, `add_documents_partitioned(table_name, partition_by, ids, vectors, contents, metadatas)` in Rust and Python. Rows grouped by partition column value (from metadata JSON); one append per group for fragment alignment. Read path: predicate on partition column (e.g. `skill_name = 'git'`) is already pushed down.
   - Done: partition strategy config. `vector.default_partition_column` in `settings.yaml` (e.g. `"skill_name"`); `RustVectorStore.add_documents_partitioned(..., partition_by=None)` uses this default when `partition_by` is `None`.

3. **Observability CLI (P1)**
   - Done: `omni db health`, `omni db compact`, `omni db query-metrics`, `omni db index-stats`.
   - Missing: real-time performance monitoring once Lance tracing is available.

4. **Index cache (P2)**
   - Done: `omni db index-stats` (read path). VectorStore has `index_cache_size_bytes: Option<usize>`; `open_dataset_at_uri()` uses `DatasetBuilder::from_uri().with_index_cache_size_bytes(n).load().await` when set. Python: `RustVectorStore(..., index_cache_size_bytes=None)` and `create_vector_store(..., index_cache_size_bytes)`. Config: `settings.yaml` → `vector.index_cache_size_bytes` (bytes or null); used when constructing the store if not passed explicitly.

**Effort (indicative)**

| Priority | Task                 | Effort   |
| -------- | -------------------- | -------- |
| P0       | Agentic Search       | ~3 days  |
| P1       | Partitioning write   | ~2 days  |
| P1       | Observability (rest) | ~1 day   |
| P2       | Index cache config   | ~0.5 day |

## Related

- **Vector store:** `packages/rust/crates/omni-vector` (includes `ops/` for admin, writer, maintenance, scalar, vector_index, observability, partitioning).
- **Index and search:** IVF-FLAT / HNSW (vector), FTS (content), BTree/Bitmap (scalar) in `ops/admin_impl.rs`, `ops/vector_index.rs`, `ops/scalar.rs`, `ops/maintenance.rs`.
- **Contracts:** [Vector/Router Schema Contract](./vector-router-schema-contract.md), [Retrieval Namespace](./retrieval-namespace.md).
