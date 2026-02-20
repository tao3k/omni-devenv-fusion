# Vector Index Optimization

> Foundation Layer - LanceDB-based Semantic Search

## Overview

The vector index provides fast nearest-neighbor (ANN) search for semantic tool discovery and knowledge retrieval. It uses LanceDB with adaptive IVF-FLAT indexing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Python Layer (omni.foundation.vector_store)                 │
│  - VectorStoreClient singleton                              │
│  - Async search/add/delete operations                       │
│  - Collection management                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ Rust Bindings (omni-core-rs)                                │
│  - create_vector_store() factory                            │
│  - PyVectorStore wrapper                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ Rust Core (omni-vector crate)                               │
│  - VectorStore: LanceDB operations                          │
│  - SkillScanner: Tool discovery                             │
│  - ScriptScanner: @skill_command detection                  │
└─────────────────────────────────────────────────────────────┘
```

## Adaptive Index Strategy

The index uses adaptive partitioning based on dataset size:

```rust
// packages/rust/crates/omni-vector/src/index.rs

const MIN_VECTORS_FOR_INDEX: usize = 100;
const VECTORS_PER_PARTITION: usize = 256;
const MAX_PARTITIONS: usize = 512;

let num_partitions = (num_rows / VECTORS_PER_PARTITION).clamp(32, 512);
```

### Partition Table

| Dataset Size   | Partitions | Behavior                    |
| -------------- | ---------- | --------------------------- |
| < 100 vectors  | Skip       | Flat search is faster       |
| 100 - 5,000    | 32         | Small dataset optimization  |
| 5,000 - 50,000 | 20 - 196   | Balanced recall/performance |
| > 50,000       | 512        | Avoid over-sharding         |

## Search Optimization

```rust
// packages/rust/crates/omni-vector/src/search.rs

const FETCH_MULTIPLIER: usize = 2;

let fetch_count = limit.saturating_mul(2).max(limit + 10);
```

The search fetches 2× the requested limit to account for metadata filtering loss.

## Hybrid Search

Combines vector similarity with keyword boosting:

```rust
// Formula: Score = Vector_Score * 0.7 + Keyword_Match * 0.3
```

| Match Type                 | Boost |
| -------------------------- | ----- |
| Metadata keywords          | +0.1  |
| Tool name contains keyword | +0.05 |
| Content contains keyword   | +0.03 |

## API Usage

### Python (Foundation Layer)

```python
from omni.foundation.vector_store import get_vector_store

# Get singleton client
store = get_vector_store()

# Search
results = await store.search("git commit workflow", n_results=5)

# Add content
await store.add(
    content="Execute git commit with message",
    metadata={"skill": "git", "command": "commit"},
    collection="skills"
)

# Create index
await store.create_index("skills")
```

### Configuration

```yaml
# settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml)
vector:
  path: ".cache/omni-vector"
  dimension: 1536 # OpenAI Ada-002
  default_limit: 5
```

## Performance Characteristics

| Operation    | Time Complexity | Notes                   |
| ------------ | --------------- | ----------------------- |
| Search       | O(log n + k)    | ANN with IVF index      |
| Add          | O(d)            | Single vector insertion |
| Create Index | O(n log n)      | Batch index build       |

## Scalar Indices (Phase 1)

BTree and Bitmap indices on metadata columns (`skill_name`, `category`) for faster filters:

- **Location:** `packages/rust/crates/omni-vector/src/ops/scalar.rs`
- **APIs:** `create_btree_index`, `create_bitmap_index`, `create_optimal_scalar_index` (cardinality &lt; 100 → Bitmap, else BTree). Skill index write triggers best-effort scalar index creation.
- **Roadmap:** [LanceDB Version and Roadmap](../reference/lancedb-version-and-roadmap.md).

## Auto-Indexing and Maintenance (Phase 2)

- **Location:** `packages/rust/crates/omni-vector/src/ops/maintenance.rs`
- **APIs:** `has_vector_index`, `has_fts_index`, `has_scalar_index`; `auto_index_if_needed` / `auto_index_if_needed_with_thresholds`; `compact(table_name)` (cleanup + compact_files).
- **Thresholds:** Configurable via `IndexThresholds` (e.g. `auto_index_at` row count).

## Vector Index Tuning (Phase 3)

- **Location:** `packages/rust/crates/omni-vector/src/ops/vector_index.rs`
- **APIs:** `create_hnsw_index` (IVF+HNSW for smaller tables), `create_optimal_vector_index` (HNSW &lt; 10k rows, IVF_FLAT ≥ 10k).

## Partitioning Suggestions (Phase 4)

- **Location:** `packages/rust/crates/omni-vector/src/ops/partitioning.rs`
- **APIs:** `suggest_partition_column(table_name)` returns a suggested column (e.g. `skill_name`) when the table has ≥ 10k rows and a partition-friendly schema. Wired into health report as `Recommendation::Partition { column }`.

## Observability (Phase 5)

- **Location:** `packages/rust/crates/omni-vector/src/ops/observability.rs`
- **APIs:** `analyze_table_health(table_name)` → `TableHealthReport` (row_count, fragment_count, fragmentation_ratio, indices_status, recommendations); `get_query_metrics(table_name)` → `QueryMetrics` (placeholder for future Lance tracing).
- **Types:** `IndexStatus`, `Recommendation` (e.g. `RunCompaction`, `CreateIndices`, `Partition { column }`), `TableHealthReport`, `QueryMetrics`.

## Related Files

**Python:**

- `packages/python/foundation/src/omni/foundation/services/vector.py`

**Rust:**

- `packages/rust/crates/omni-vector/src/lib.rs`
- `packages/rust/crates/omni-vector/src/index.rs`
- `packages/rust/crates/omni-vector/src/search/` (search_impl, options)
- `packages/rust/crates/omni-vector/src/ops/` (admin_impl, writer_impl, maintenance, scalar, vector_index, observability, partitioning, types)

**Bindings:**

- `packages/rust/bindings/python/src/vector.rs`

**Roadmap:**

- [LanceDB Version and Roadmap](../reference/lancedb-version-and-roadmap.md)
