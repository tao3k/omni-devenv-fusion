# Omni-Vector Project Status

> Feature matrix and gap list aligned with the codebase. Used for planning Python API exposure and CLI extension.

---

## 1. Completed Features

### 1.1 Rust Core (omni-vector)

| Module         | File                                    | Features                                                                           | Status |
| -------------- | --------------------------------------- | ---------------------------------------------------------------------------------- | ------ |
| Scalar Indices | `ops/scalar.rs`                         | `create_btree_index`, `create_bitmap_index`, `create_optimal_scalar_index`         | Done   |
| Vector Indices | `ops/vector_index.rs`                   | `create_hnsw_index`, `create_optimal_vector_index`                                 | Done   |
| Maintenance    | `ops/maintenance.rs`                    | `auto_index_if_needed`, `auto_index_if_needed_with_thresholds`                     | Done   |
| Observability  | `ops/observability.rs`                  | `analyze_table_health`, `get_query_metrics`, `get_index_cache_stats`               | Done   |
| Agentic Search | `ops/agentic.rs`                        | `agentic_search`, `QueryIntent`, `AgenticSearchConfig`                             | Done   |
| Partitioning   | `ops/partitioning.rs`                   | `suggest_partition_column`                                                         | Done   |
| Writer         | `ops/writer_impl.rs`                    | `add_documents`, `add_documents_partitioned`, `merge_insert`                       | Done   |
| Admin          | `ops/admin_impl.rs`                     | `count`, `drop_table`, `add_columns`, `alter_columns`, `create_index` (vector+FTS) | Done   |
| Checkpoint     | `checkpoint/store.rs`                   | Time-series data storage                                                           | Done   |
| Keyword        | `keyword/index.rs`, `keyword/fusion.rs` | BM25 full-text, RRF fusion, entity-aware                                           | Done   |

### 1.2 Python Bridge (RustVectorStore / PyVectorStore)

| Feature                   | Location                                          | Status |
| ------------------------- | ------------------------------------------------- | ------ |
| RustVectorStore           | `foundation/bridge/rust_vector.py`                | Done   |
| agentic_search            | PyVectorStore + RustVectorStore delegation        | Done   |
| add_documents_partitioned | PyVectorStore + RustVectorStore                   | Done   |
| analyze_table_health      | store.rs → RustVectorStore                        | Done   |
| compact                   | store.rs → RustVectorStore                        | Done   |
| get_query_metrics         | store.rs → RustVectorStore                        | Done   |
| get_index_cache_stats     | store.rs → RustVectorStore                        | Done   |
| create_index(table_name)  | search_ops.rs; creates vector + FTS default index | Done   |

### 1.3 CLI (omni db)

This project uses **`omni db`** as the vector-store operations entry (no separate `lance-cli`):

| Command                         | Description                                            | Status |
| ------------------------------- | ------------------------------------------------------ | ------ |
| `omni db health [db]`           | Table health (fragmentation, indices, recommendations) | Done   |
| `omni db compact <db>`          | Compact table                                          | Done   |
| `omni db index-stats <table>`   | Index cache stats                                      | Done   |
| `omni db query-metrics <table>` | Query metrics (in-process from agentic_search)         | Done   |
| `omni db stats`                 | Database-level stats                                   | Done   |

### 1.4 Tests

| Test                                           | Coverage                    | Status |
| ---------------------------------------------- | --------------------------- | ------ |
| test_scalar_index.rs                           | BTree/Bitmap/optimal scalar | Done   |
| test_vector_index.rs                           | HNSW/optimal vector         | Done   |
| test_maintenance.rs                            | auto_index, compact         | Done   |
| test_observability.rs                          | health                      | Done   |
| test_partitioning.rs                           | suggest_partition_column    | Done   |
| test_hybrid_search.rs                          | Hybrid search               | Done   |
| test_fusion.rs, test_entity_aware_benchmark.rs | RRF, entity-aware           | Done   |

---

## 2. Gaps / Exposure Status

### 2.1 Python Exposure (Completed)

The following APIs are now exposed on **PyVectorStore** and **RustVectorStore** (P0 done):

| Rust function                      | Rust location       | Python exposure                             |
| ---------------------------------- | ------------------- | ------------------------------------------- |
| create_btree_index(table, column)  | ops/scalar.rs       | RustVectorStore.create_btree_index          |
| create_bitmap_index(table, column) | ops/scalar.rs       | RustVectorStore.create_bitmap_index         |
| create_hnsw_index(table)           | ops/vector_index.rs | RustVectorStore.create_hnsw_index           |
| create_optimal_vector_index(table) | ops/vector_index.rs | RustVectorStore.create_optimal_vector_index |
| suggest_partition_column(table)    | ops/partitioning.rs | RustVectorStore.suggest_partition_column    |
| auto_index_if_needed(table)        | ops/maintenance.rs  | RustVectorStore.auto_index_if_needed        |

Note: Python also has `create_index(table_name)` for the admin one-shot vector + FTS creation; the above are granular index APIs.

### 2.2 CLI Extension (P1 Done)

Index creation by type under **`omni db`** is implemented:

| Feature                     | Command                                                     | Status |
| --------------------------- | ----------------------------------------------------------- | ------ |
| Create BTree index          | `omni db index create --table T --type btree --column COL`  | Done   |
| Create Bitmap index         | `omni db index create --table T --type bitmap --column COL` | Done   |
| Create HNSW index           | `omni db index create --table T --type hnsw`                | Done   |
| Create optimal-vector index | `omni db index create --table T --type optimal-vector`      | Done   |
| Partition suggestion        | `omni db partition-suggest <table>`                         | Done   |
| Table health / compact      | `omni db health` / `omni db compact`                        | Done   |

(Report “lance-cli” corresponds to **omni db** in this repo; a separate binary can be planned if needed.)

---

## 3. Suggested Next Steps

### Completed (P0): Expose Python API

- **PyO3**: `packages/rust/bindings/python/src/vector/store.rs` has the six `store_*` wrappers; PyVectorStore methods in `mod.rs`.
- **RustVectorStore**: `foundation/bridge/rust_vector.py` has the six methods delegating to `_inner` and parsing JSON/Option.
- **Tests**: `test_index_and_maintenance_api_delegate_and_parse` in `test_rust_vector_bridge_schema.py` covers them.

### Mid-term: CLI and Agentic

- **CLI**: Add `omni db index create --table T --type btree|hnsw [--column COL]` (call Python API or Rust).
- **Agentic Search**: Intent classification (e.g. LLM), configurable weights/strategy (see backlog and router docs).

---

## 4. Verification Commands

```bash
# Rust unit tests
cargo test -p omni-vector test_scalar_index
cargo test -p omni-vector test_vector_index
cargo test -p omni-vector test_maintenance
cargo test -p omni-vector test_partitioning

# Python bridge and CLI
uv run pytest packages/python/foundation/tests/ -q -k "vector or rust_vector"
uv run omni db health
uv run omni db compact skills
```

---

## 6. Future Work / Roadmap

| Item                                | Description                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RRF / distance kernels**          | **`keyword/fusion/kernels.rs`**: Scalar `rrf_term(k, rank)`, batch `rrf_term_batch(ranks, k)`, and `distance_to_score(distance)`. All fusion paths use `rrf_term`. Batch kernel is array-in/array-out for future SIMD or Arrow compute swap-in.                                                                                                                                                                                                       |
| **Arrow lowercase kernel**          | Fusion batch lowercase is centralized in `keyword/fusion/match_util.rs` → **`lowercase_string_array(&StringArray) -> StringArray`**. That function is the single swap-in point: when Arrow provides a `compute::lowercase` (or `arrow_string::lowercase`) kernel, replace its body with a call to the kernel for SIMD-accelerated batch lowercase. Current implementation uses Rust `str::to_lowercase()` per element with Arrow-native input/output. |
| **Distributed index (>100K scale)** | Single-node LanceDB is sufficient up to roughly 100K vectors. Beyond that, consider sharding (e.g. by `skill_name`/partition), LanceDB distributed mode, or external orchestration for multi-node index build and query.                                                                                                                                                                                                                              |

---

## 5. Related Docs

- [LanceDB Version and Roadmap](lancedb-version-and-roadmap.md)
- [Omni-Vector Audit and Next Steps](omni-vector-audit-and-next-steps.md) — Audit summary, priorities, LanceDB 2.x alignment
- [Search Systems](search-systems.md)
- [Backlog](../backlog.md)
