# Router Architecture - Omni-Dev-Fusion

> Semantic Routing System (The Cortex)
> Last Updated: 2026-01-27

---

## Table of Contents

1. [Overview](#overview)
2. [OmniRouter](#omnirouter)
3. [HybridSearch (Rust-Native)](#hybridsearch-rust-native)
4. [HiveRouter](#hiverouter)
5. [SemanticRouter](#semanticrouter)
6. [IntentSniffer](#intentsniffer)
7. [SkillIndexer](#skillindexer)
8. [Routing Flow](#routing-flow)

---

## Overview

The **Router System** (The Cortex) provides intent-to-action mapping:

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│         OmniRouter (Facade)          │
└─────────────────────────────────────┘
    │           │           │
    ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│  Hive   │ │ Hybrid  │ │ Sniffer │
│ (Logic) │ │  (Rust) │ │(Context)│
└─────────┘ └─────────┘ └─────────┘
```

### Components

| Component        | Purpose                   | Location                   |
| ---------------- | ------------------------- | -------------------------- |
| `OmniRouter`     | Unified entry point       | `omni.core.router.main`    |
| `HybridSearch`   | Rust-native hybrid search | `omni.core.router.hybrid`  |
| `HiveRouter`     | Decision logic            | `omni.core.router.hive`    |
| `SemanticRouter` | Vector-based matching     | `omni.core.router.router`  |
| `IntentSniffer`  | Context detection         | `omni.core.router.sniffer` |
| `SkillIndexer`   | Index building            | `omni.core.router.indexer` |

### Rust-Native Hybrid Search

The `HybridSearch` component is now **100% Rust-native** using `omni-vector`:

```
┌─────────────────────────────────────────────────────────────┐
│                    Rust: omni-vector                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  Vector Search  │    │  Keyword Rescue │                 │
│  │   (LanceDB)     │    │   (Tantivy)     │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ▼                                      │
│           ┌─────────────────────┐                           │
│           │  Score Fusion       │                           │
│           │  (0.4*vec + 0.6*kw) │                           │
│           └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    Python: HybridSearch
                    (thin wrapper)
```

**Benefits:**

- Zero serialization overhead (no Python↔Rust data copying)
- Atomic scoring (vector + keyword in single operation)
- 10-100x faster than Python-based hybrid search
- Consistent behavior between CLI and MCP server

---

## OmniRouter

**Location**: `packages/python/core/src/omni/core/router/main.py`

The unified entry point for all routing operations.

### Architecture

```
OmniRouter
    │
    ├── _indexer  → SkillIndexer (Memory)
    ├── _hybrid   → HybridSearch (Rust-Native)
    ├── _hive     → HiveRouter (Decision Logic)
    └── _sniffer  → IntentSniffer (Context)
```

### Key Methods

```python
from omni.core.router import get_router

router = get_router()

# Initialize with skills
await router.initialize(skills)

# Route a query
result = await router.route("commit git changes")

# Hybrid search (Rust-native)
results = await router.route_hybrid("git commit", limit=5, threshold=0.4)

# Suggest skills based on context
skills = await router.suggest_skills("/project/path")
```

### Properties

| Property  | Type            | Description               |
| --------- | --------------- | ------------------------- |
| `indexer` | `SkillIndexer`  | Vector index manager      |
| `hybrid`  | `HybridSearch`  | Rust-native hybrid search |
| `hive`    | `HiveRouter`    | Decision logic            |
| `sniffer` | `IntentSniffer` | Context detection         |

### Runtime Configuration

`OmniRouter` reads routing search/profile settings from merged `settings.yaml`.
The user-facing override mechanism is `--conf <dir>`, which changes where `settings.yaml` is loaded from.

```yaml
router:
  search:
    active_profile: "balanced"
    auto_profile_select: true
    profiles:
      balanced:
        high_threshold: 0.75
        medium_threshold: 0.5
        high_base: 0.90
        high_scale: 0.05
        high_cap: 0.99
        medium_base: 0.60
        medium_scale: 0.30
        medium_cap: 0.89
        low_floor: 0.10
    adaptive_threshold_step: 0.15
    adaptive_max_attempts: 3
    schema_file: "schemas/router.search.schema.json"
```

- `active_profile`: selected confidence profile name.
- `auto_profile_select`: allows runtime auto-selection when no explicit profile is provided.
- `profiles.<name>`: confidence calibration parameters for each profile.
- `adaptive_threshold_step`: retry-time threshold decay for adaptive search.
- `adaptive_max_attempts`: max adaptive retries before returning best-available matches.

Important:

- Confidence and final-score calibration is owned by Rust binding/runtime.
- Python forwards configured profile values to Rust and consumes canonical fields
  (`confidence`, `final_score`) without local recalibration.

The schema is available programmatically:

```python
from omni.core.router import router_search_json_schema

schema = router_search_json_schema()
```

Write schema to the active config directory (resolved from `--conf`):

```python
from omni.core.router import write_router_search_json_schema

path = write_router_search_json_schema()
```

---

## HybridSearch (Rust-Native)

**Location**: `packages/python/core/src/omni/core/router/hybrid_search.py`

The **Rust-native hybrid search engine** that delegates all heavy computation to `omni-vector`:

### Architecture

```python
class HybridSearch:
    """Rust-native hybrid search (thin Python shell).

    All ranking and confidence logic is in Rust:
    - Vector similarity (LanceDB)
    - Keyword rescue (Tantivy BM25)
    - Weighted RRF score fusion
    - Confidence/final-score calibration
    """

    def __init__(self):
        self._store = get_vector_store()  # Rust omni-vector

    async def search(self, query: str, limit: int = 5, min_score: float = 0.0):
        # 1. Generate embedding (Python)
        # 2. Call Rust search_tools (vector + keyword rescue)
        # 3. Return formatted results (Python)
```

### Rust API

The actual search is performed by `omni-vector`'s `search_tools`:

```rust
// Rust: omni-vector/src/skill.rs
pub async fn search_tools(
    &self,
    table_name: &str,
    query_vector: &[f32],
    query_text: Option<&str>,  // Triggers keyword rescue
    limit: usize,
    threshold: f32,
) -> Result<Vec<ToolSearchResult>>
```

### Usage

```python
search = HybridSearch()

# Simple search
results = await search.search("git commit", limit=5)

# Results are dicts with:
# {
#     "id": "git.commit",
#     "content": "Commit changes to repository",
#     "score": 0.85,
#     "skill_name": "git",
#     "command": "commit",
#     "file_path": "git/scripts/commit.py",
#     "keywords": ["commit", "git", "vcs"],
# }
```

### Weights (Fixed)

| Component | Weight | Description                 |
| --------- | ------ | --------------------------- |
| Semantic  | 0.4    | Vector similarity score     |
| Keyword   | 0.6    | BM25 keyword match + rescue |

Weights are **fixed** in the Rust implementation for performance.

### Router Registry

Multiple router instances can be managed:

```python
# Get default router
router = get_router()

# Get named router
router = get_router("session-1")

# Set default router
RouterRegistry.set_default("session-1")

# Reset router
RouterRegistry.reset("session-1")
RouterRegistry.reset_all()
```

---

## HiveRouter

**Location**: `packages/python/core/src/omni/core/router/hive.py`

The **Decision Logic** layer that orchestrates routing:

```python
class HiveRouter:
    """Multi-hive routing strategy.

    Routes through:
    1. Direct match (command name)
    2. Semantic search (vector similarity)
    3. Fallback (LLM or error)
    """
```

### Routing Strategy

```
Query: "commit the changes"
        │
        ▼
┌─────────────────────────┐
│ 1. Direct Match?        │ ──No──►
│ (command: commit)       │        │
└─────────────────────────┘        │
         │ Yes                     │
         ▼                         ▼
┌─────────────────────────┐ ┌─────────────────────────┐
│ 2. Semantic Match?      │ │ 3. Fallback             │
│ (vector similarity)     │ │ (LLM or error)          │
└─────────────────────────┘ └─────────────────────────┘
         │ Yes                     │
         ▼                         │
┌─────────────────────────┐        │
│ Return RouteResult      │◄───────┘
└─────────────────────────┘
```

---

## SemanticRouter

**Location**: `packages/python/core/src/omni/core/router/router.py`

The **Vector Search** layer using embeddings:

```python
class SemanticRouter:
    """Semantic routing using vector similarity.

    Uses:
    - omni-vector (Rust) for vector storage
    - omni-embedding (Python) for query encoding
    """

    def __init__(self, indexer: SkillIndexer):
        self._indexer = indexer
        self._threshold = 0.7
        self._limit = 5
```

### Search Parameters

| Parameter   | Default | Description               |
| ----------- | ------- | ------------------------- |
| `threshold` | 0.7     | Minimum similarity score  |
| `limit`     | 5       | Maximum results to return |

### Usage

```python
router = get_router()
results = await router.semantic.search("git commit", limit=3)
```

---

## IntentSniffer

**Location**: `packages/python/core/src/omni/core/router/sniffer.py`

The **Context Detection** layer (The Nose):

```python
class IntentSniffer:
    """Context detector using file system patterns.

    Uses skill_index.json (generated by Rust scanner) to:
    - Detect project type from directory structure
    - Suggest relevant skills
    - Auto-activate context-aware routing
    """
```

### Sniffing Rules

Rules are loaded from `skill_index.json`:

```json
{
  "rules": [
    {
      "pattern": ".git/**",
      "skill": "git"
    },
    {
      "pattern": "**/*.py",
      "skill": "python_engineering"
    },
    {
      "pattern": "**/*.rs",
      "skill": "rust_engineering"
    }
  ]
}
```

### Usage

```python
router = get_router()

# Get context-based suggestions
suggestions = router.sniffer.sniff("/project/path")
# Returns: ["git", "python_engineering"]

# Load rules from index
count = router.sniffer.load_from_index()
```

---

## SkillIndexer

**Location**: `packages/python/core/src/omni/core/router/indexer.py`

The **Index Building** component:

```python
class SkillIndexer:
    """Builds and manages the skill index.

    Uses:
    - RustVectorStore for vector storage
    - Embedding service for query encoding
    """

    def __init__(self, storage_path: str = ":memory:", dimension: int = 1536):
        self._storage_path = storage_path
        self._dimension = dimension
```

### Key Methods

```python
indexer = SkillIndexer()

# Index skills
await indexer.index_skills(skills)

# Search
results = await indexer.search("git commit", limit=5, threshold=0.7)

# Get stats
stats = indexer.get_stats()
```

### Indexed Entries

Each skill creates multiple entries:

| Entry Type      | Description                |
| --------------- | -------------------------- |
| Skill entry     | Overall skill description  |
| Command entries | Each command's description |

---

## Routing Flow

### Complete Flow

```
1. User Input
   @omni("git.commit", message="Fix bug")

2. Query Parsing
   - Extract skill: "git"
   - Extract command: "commit"
   - Extract params: {message: "Fix bug"}

3. HiveRouter Decision
   ├─ Direct Match: "git.commit" → Found!
   └─ Return RouteResult(skill, command, params)

4. Execution
   └─ skill.execute(command, params)

5. Response
   └─ Return result to user
```

### Fallback Flow (No Direct Match)

```
1. User Input
   @omni("commit the changes")

2. Query Parsing
   - No direct match found

3. HiveRouter Fallback
   ├─ Semantic Search
   │  └─ "commit" → 85% match with git.commit
   │
   └─ Return RouteResult(git, commit, {})

4. Execution & Response
```

---

## Integration with Kernel

```python
from omni.core.kernel.engine import get_kernel

kernel = get_kernel()

# Router is available via kernel
router = kernel.router

# Build cortex (index all skills)
await kernel.build_cortex()

# Sniffer loads rules
kernel.load_sniffer_rules()
```

---

## Performance

| Operation       | Performance             |
| --------------- | ----------------------- |
| Direct match    | O(1)                    |
| Semantic search | ~1ms for 10K entries    |
| Sniffing        | ~5ms for directory scan |

---

## Related Documentation

- [Kernel Architecture](kernel.md)
- [Skills System](skills.md)
- [Rust Crates](rust-crates.md)
- [RAG/Representation Protocol](../reference/odf-rep-protocol.md)
