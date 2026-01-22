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
# assets/settings.yaml
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

## Related Files

**Python:**

- `packages/python/foundation/src/omni/foundation/services/vector.py`

**Rust:**

- `packages/rust/crates/omni-vector/src/lib.rs`
- `packages/rust/crates/omni-vector/src/index.rs`
- `packages/rust/crates/omni-vector/src/search.rs`
- `packages/rust/crates/omni-vector/src/store.rs`

**Bindings:**

- `packages/rust/bindings/python/src/vector.rs`
