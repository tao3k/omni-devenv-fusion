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

### Search at scale: data + mechanisms (no per-skill hardcoding)

With many skills (hundreds or 10k+), relevance is achieved by **data quality** and a **fixed pipeline**, not by hardcoding rules per skill.

**Pipeline (order):**

1. **Query normalization** (optional) — `router.normalize.typos` in settings; URL → short token. Extend typos in config, not in code.
2. **Agentic hybrid search** — Rust: vector (LanceDB) + keyword (Tantivy) RRF fusion, intent (exact / hybrid), optional category_filter.
3. **Intent-overlap boost** — Query terms in `router.search.intent_vocab` (or built-in) are matched against each result’s `routing_keywords` / `intents`; higher overlap → score boost. Fully data-driven (no skill names in code).
4. **Relationship rerank** — Graph built at index time from `routing_keywords` overlap (Jaccard); tools related to top results get a small boost. Graph is in `skill_relationships.json`; no hand-curated links.
5. **Confidence calibration** — Profile-based thresholds and attribute overlap for medium→high.

**How to get the best effect:**

- **Data:** In each skill’s `SKILL.md`, use rich `routing_keywords` and `intents` so hybrid search and intent-overlap can match. Optional: `router.enrichment.enabled` to expand keywords at index time.
- **Config:** Use `router.normalize.typos` and `router.search.intent_vocab` to add domain terms or typos without code changes.
- **No per-skill code:** Ranking is driven only by indexed fields and the mechanisms above; scaling to 10k skills does not require new logic per skill.

### Skill index structure and relationships

The router index reflects a **two-level hierarchy** plus references:

| Layer                 | Relationship                                               | Where it lives                                                         |
| --------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Skill → tools**     | One skill has many tools (commands)                        | Each row has `skill_name`; tool id is `skill_name.command_name`.       |
| **Tool → references** | A tool can reference one or more docs in `references/*.md` | `skill_tools_refers` on each tool row (from front matter `for_tools`). |

- **Parsing:** Rust scanner (`omni-scanner`) reads `SKILL.md` and `references/*.md`. In each reference file, front matter `for_tools: [skill.command_a, ...]` defines which tools that reference applies to. The scanner fills `skill_tools_refers` on each `ToolRecord`.
- **Index:** When skills are reindexed (Rust `index_skill_tools_dual`), each row in the skills table has `skill_name`, `tool_name`, `routing_keywords`, `intents`, and `skill_tools_refers`. So the same-skill and tool–reference structure is stored in the table.
- **Relationship graph:** After reindex, the relationship graph (`skill_relationships.json`) is built from the table and uses:
  - **Keyword overlap** (Jaccard on `routing_keywords`) — similar intents.
  - **Same-skill** — tools under the same `skill_name` get an edge (siblings).
  - **Shared references** — tools that share an entry in `skill_tools_refers` get an edge.

So routing can boost not only by semantic/keyword match but by “same skill” and “shares a reference” without hardcoding skill names.

---

For **why** a given query ranks one tool above another (and how to fix it with data), see [Routing quality analysis](../testing/routing-quality-analysis.md).

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

`OmniRouter` reads routing search/profile settings from merged `settings.yaml` (system default: `packages/conf/settings.yaml`; user override: `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml`).
The user-facing override mechanism is `--conf <dir>`, which sets the user config directory.

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

## Search pipeline: overall logic

**When to use hybrid vs keyword-only**

| Entry point                        | Retrieval                     | Reason                                                                                                       |
| ---------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **`omni route test <query>`**      | **Hybrid** (vector + keyword) | User query is natural language; we need both semantic (description) and exact trigger (routing_keywords).    |
| **Skill discovery / tool routing** | **Hybrid**                    | Same: natural language intent → match tools by description and keywords.                                     |
| **Keyword-only**                   | Not used for route test       | Would apply only to a hypothetical “search by exact tokens only” API; today all routing goes through hybrid. |

**End-to-end flow for `omni route test "帮我研究一下 https://..."`**

1. **Query** → optional **LLM translation** (non-English → English). Result is the **effective query** used for both branches.
2. **Vector branch**: embed effective query → search **skills** table by vector similarity (description semantics).
3. **Keyword branch**: effective query → Tantivy BM25 on fields `tool_name`, `routing_keywords`, `intents`, `description` (boosts favor keywords/intents).
4. **Fusion**: RRF combines vector and keyword results; confidence/rerank applied.
5. **Table**: Routing reads from the **skills** table in `skills.lance` (`.cache/omni-vector/skills.lance`). This table **must be populated** by `omni sync` (or `omni reindex`) from `assets/skills`. If the skills table is empty or stale, skills like `researcher` will not appear in results. The separate `router.lance` store is reserved for score-only data (no tool replication); see [Skills and Router Databases](../reference/skills-and-router-databases.md).

**Why a skill might be missing from top results**

- **Skills table not built or stale**: Run `omni sync` so that `skills.lance` is indexed from the current `assets/skills` (including researcher).
- **Translation failed or skipped**: If the effective query stays non-English, the keyword index (English-only) won’t match. Check logs for “Using translated query” / “Effective query”; ensure LLM is configured for translation.
- **Keyword match weak**: After translation, the effective query must contain terms that appear in the skill’s `routing_keywords` (e.g. “research”, “analyze”) so the keyword branch can rank it.

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

### Per-field search algorithm

Each indexed value has a single, well-defined search algorithm. This avoids ambiguity and improves routing (e.g. description for semantic intent, routing_keywords for exact trigger phrases).

| Field                | Search algorithm                      | Purpose                                                                                                                                  |
| -------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **description**      | **Vector (embedding)**                | Semantic match: "help me analyze this repo" → tools that describe repository analysis. Used for LLM-facing "what this tool does."        |
| **routing_keywords** | **Keyword (BM25)**                    | Exact/phrase match (English): "git commit", "research", "analyze_repo". Index is English-only; non-English queries are translated first. |
| **intents**          | **Keyword (BM25)** with higher boost  | Intent phrases and one-liners; same token match as keywords but weighted more in Tantivy.                                                |
| **tool_name**        | **Keyword (BM25)** with highest boost | Exact tool identity (e.g. `researcher.run_research_graph`).                                                                              |

#### routing_keywords vs intents (and why intents can be longer)

|             | **routing_keywords**                                                                       | **intents**                                                                                                                            |
| ----------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Shape**   | Short tokens: single words or 2–3 word phrases ("research", "analyze_repo", "github url"). | **Longer phrases**: one-liners or full sentences that describe how users express the intent.                                           |
| **Purpose** | Trigger-style terms for BM25; dense, easy to match.                                        | Natural-language intent descriptions; more surface for query terms to match, with **higher boost** (4× in Tantivy vs 3× for keywords). |
| **Example** | `"research"`, `"analyze"`, `"url"`, `"github url"`                                         | `"Help me research or analyze a repository from a GitHub URL"`, `"I want to do deep research on a codebase"`                           |
| **Match**   | Query terms matched against keyword list (substring/token overlap).                        | Same: query terms matched against intent text. Longer intents = more tokens = more chances to match user phrasing.                     |

So: **routing_keywords** = compact trigger set; **intents** = longer, user-phrasing-style sentences. Both go into keyword search; intents get a higher field boost. Prefer **longer intents** so that natural user queries (e.g. "help me to analyze/research this github repo") match intent text well.

So: **description → vector search**; **routing_keywords / intents / tool_name → keyword search**. Fusion (RRF) combines the two streams. **All SKILL.md content (description, routing_keywords, intents) must be in English.** Non-English user queries are translated to English by the router translation layer before hybrid search so that keyword matching works; see [Query translation (non-English → English)](#query-translation-non-english--english).

### Field split: keyword vs vector

Hybrid search splits responsibilities by field so that both exact trigger terms and semantic description are matched:

| Branch                 | Primary fields                             | Notes                                                                                                                                                             |
| ---------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Keyword (Tantivy)**  | `routing_keywords`, `intents`, `tool_name` | BM25 retrieval; QueryParser field boosts: tool_name 5×, intents 4×, **keywords 3×**, description 1×. Prioritizes routing keywords and intent phrases.             |
| **Vector (embedding)** | **description** (and intents)              | Only "COMMAND + DESCRIPTION + INTENTS" are used to generate embeddings; KEYWORDS are not vectorized, so the vector side matches description and intent semantics. |

Resulting behavior:

- Queries like **"git commit"**, **"search regex"** → matched mainly by the **keyword branch** on `routing_keywords`.
- Queries like **"save my changes to the repo"**, **"find text in code"** → matched mainly by the **vector branch** on description semantics.
- Both streams are fused with RRF, preserving keyword precision and description semantics for more accurate hybrid results.

Implementation notes:

- **Indexing**: Python builds the text used for embedding as `COMMAND` + `DESCRIPTION` + `INTENTS` (no `KEYWORDS`). Rust Tantivy still indexes description, keywords, intents, etc.; the keywords field is filled from metadata `routing_keywords`.
- **Retrieval**: The same query is used for query embedding (vector branch) and Tantivy parsing (keyword branch); fusion is done inside Rust.

### Query translation (non-English → English)

SKILL.md and all indexed fields are **English-only**. We do not know what language the user will use, so the pipeline uses a **common language (English)** for routing. This translation layer is **on by default**: when the query is not already English, it is translated via the LLM before hybrid search so that the keyword branch matches English `routing_keywords`.

**Translation is done only via the LLM (large model).** The same layer also strengthens search (e.g. catalog enrichment); it is not an optional add-on but part of the default pipeline.

- **Default**: Translation is **enabled by default** (`router.translation.enabled: true`). Set to `false` only if all queries are known to be English.
- **Config**: `router.translation.model` (optional; else uses `inference.model`), `router.translation.fallback_to_original` (default `true`).
- **Model**: Any LLM usable via LiteLLM (e.g. Pangu, MiniMax, or the default inference model). Set `router.translation.model` to a dedicated translation model if desired.
- **Flow**: In `HybridSearch.search()`, if translation is enabled and the query is not already likely English, the query is sent to the LLM for translation; the English result is used for both embedding and keyword search.
- **Implementation**: `omni.core.router.translate.translate_query_to_english()`; uses the LLM provider from `omni.foundation.services.llm.provider`; heuristic skips the call when the query is already mostly ASCII/English.
- **Speed (fast path)**: Before calling the LLM, a **rule-based fallback** is tried. If the query matches a known pattern (e.g. “研究” or “分析” + URL), the effective English phrase is built immediately (e.g. “Help me research &lt;url&gt;”) and the LLM is **skipped**, saving roughly 10+ seconds per request. LLM is used only when no pattern matches.

### Confidence calibration

Confidence levels (`high` / `medium` / `low`) are computed in Rust from the fused score and the active **confidence profile** (e.g. `balanced`: high_threshold=0.75, medium_threshold=0.50). In addition, **clear-winner promotion**: when the top result’s score is at least 0.15 above the second and above the medium threshold, the top result is promoted to `high` so that the single best-matching skill is clearly signaled (e.g. “help me research this repo” → researcher with high confidence). Implemented in `packages/rust/bindings/python/src/vector/search_ops.rs` (`calibrate_confidence_with_clear_winner`). **Attribute-based stratification**: Confidence also uses the skill-command attributes stored in the vector DB (and exposed on each result payload). In Rust, `keyword_score` and `vector_score` are used so that strong keyword (routing_keywords/intents/category) matches can be promoted to high when score ≥ medium. In Python, after results are returned, query terms are matched against each result's `routing_keywords`, `intents`, and `category`; medium results with overlap strength ≥ 2 are promoted to high, so high/medium/low are explicit and data-driven.

### Catalog enrichment (diversify attribute values)

Besides translating the **query**, the LLM layer can diversify **attribute values** at index time so that search is more precise. For example, `routing_keywords` from SKILL.md are expanded with synonyms and related terms suggested by the LLM; the merged list is what gets indexed, so the keyword branch matches more user phrasings.

- **Config**: `router.enrichment.enabled` (default `false`), `router.enrichment.expand_keywords` (default `true`), optional `router.enrichment.model`.
- **Flow**: When indexing skills, for each command the indexer calls `enrich_routing_keywords(description, routing_keywords)`; the LLM returns additional English keywords/phrases; they are merged (deduped) with the original and written into the index. No change to SKILL.md on disk; enrichment is applied only at index build.
- **Use case**: Makes the **value** of fields like `routing_keywords` more diverse (e.g. “research” plus “investigate”, “analyze repo”, “deep dive”) so that both the original terms and related phrasings match.

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
