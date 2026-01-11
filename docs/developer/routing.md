# Routing Architecture

> **Phase 36.2: Vector-Enhanced Discovery** | **Phase 36.5: Hot Reload Integration**

## Overview

The Routing System is responsible for translating user requests into the right skill commands. It uses a multi-stage cascade for optimal performance and accuracy.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Routing Architecture                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Request                                                               │
│         │                                                                   │
│         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 1️⃣ Semantic Cortex (Fuzzy Cache)                                       │  │
│  │    "Fix bug" ≈ "Fix the bug" (Levenshtein distance)                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│         │                                                                   │
│         ├── Hit ──→ Return Cached Result (O(1), ~1μs)                      │
│         │                                                                   │
│         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 2️⃣ Exact Match Cache                                                   │  │
│  │    "git commit" → exact string match                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│         │                                                                   │
│         ├── Hit ──→ Return Cached Result (O(1), ~1μs)                      │
│         │                                                                   │
│         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 3️⃣ LLM Routing (Hot Path)                                              │  │
│  │    Analyze request → Select skills → Generate Mission Brief            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│         │                                                                   │
│         ├── High Confidence (≥0.5) ──→ Return Result                       │
│         │                                                                   │
│         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 4️⃣ Vector Fallback (Cold Path) [Phase 36.2]                            │  │
│  │    ChromaDB semantic search → suggested_skills                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Routing Components

### Semantic Cortex (Fuzzy Cache)

**Purpose**: Fast fuzzy matching for common request patterns.

**Implementation**: Levenshtein-based similarity with configurable threshold.

```python
from agent.core.router import SemanticCortex

cortex = SemanticCortex(
    similarity_threshold=0.75,  # 75% similarity required
    ttl_seconds=7 * 24 * 60 * 60  # 7-day cache
)

# Recall returns cached RoutingResult if similar request exists
result = await cortex.recall("fix the bug")

# Learn stores new routing decisions
await cortex.learn("fix the bug", routing_result)
```

**Performance**: ~1μs for cache hits (microsecond level).

### Exact Match Cache

**Purpose**: O(1) lookup for exact string matches.

**Implementation**: In-memory dictionary with TTL.

```python
from agent.core.router import HiveMindCache

cache = HiveMindCache()

# Exact string matching
result = cache.get("git status")  # Returns RoutingResult or None
cache.set("git status", result)
```

### LLM Routing (Hot Path)

**Purpose**: Primary routing via LLM inference.

**Implementation**: SemanticRouter with skill registry integration.

```python
from agent.core.router import SemanticRouter

router = SemanticRouter(use_semantic_cache=True)

result = await router.route(
    request="Show me the git status",
    available_skills=["git", "filesystem", "terminal"]
)

# Result fields:
# - selected_skills: ["git"]
# - mission_brief: "Show git working tree status"
# - reasoning: "Matched 'git status' keywords"
# - confidence: 0.95
```

### Vector Fallback (Cold Path) [Phase 36.2]

**Purpose**: Semantic search when LLM routing is weak.

**Trigger Conditions**:

```python
is_weak_route = (
    not valid_skills or                    # No valid skills found
    confidence < 0.5 or                    # Low confidence
    (len(valid_skills) == 1 and            # Only 1 skill
     valid_skills[0] in ["writer", "knowledge"])  # Generic fallback
)
```

**Flow**:

```
LLM Confidence < 0.5
        ↓
Vector Fallback Triggered
        ↓
ChromaDB Query (skill_registry collection)
        ↓
Filter: installed_only=True (local skills only)
        ↓
Return suggested_skills in RoutingResult
        ↓
Boost confidence by 0.15
```

## Routing Scenario Test Graph

### Test Coverage Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Routing Scenario Test Coverage                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CATEGORY 1: Cache Operations                                               │
│  ├─ test_cortex_initialization          ✅ SemanticCortex init              │
│  ├─ test_similarity_conversion          ✅ Distance→Score conversion        │
│  ├─ test_recall_returns_none            ✅ No results handling              │
│  ├─ test_recall_returns_cached          ✅ Cache hit processing             │
│  ├─ test_learn_stores_result            ✅ Learning from routing            │
│  └─ test_recall_skips_expired           ✅ TTL expiration                   │
│                                                                             │
│  CATEGORY 2: Exact Match Cache                                              │
│  ├─ test_exact_match_cache_hit          ✅ String matching                  │
│  ├─ test_exact_match_cache_miss         ✅ Cache miss fallthrough           │
│  └─ test_cache_invalidation             ✅ Manual cache clear               │
│                                                                             │
│  CATEGORY 3: LLM Routing (Hot Path)                                         │
│  ├─ test_route_with_high_confidence     ✅ Direct routing                   │
│  ├─ test_route_with_low_confidence      ✅ Fallback trigger                 │
│  ├─ test_route_with_generic_skills      ✅ Generic skill detection          │
│  ├─ test_generate_mission_brief         ✅ Brief generation                 │
│  └─ test_no_valid_skills                ✅ Empty skill handling             │
│                                                                             │
│  CATEGORY 4: Vector Fallback (Cold Path) [Phase 36.2]                       │
│  ├─ test_scenario2_cold_path_virtual_loading     ✅ Vector fallback         │
│  ├─ test_scenario5_vector_filtering              ✅ installed_only filter   │
│  ├─ test_scenario6_cache_hit                     ✅ Cache + Vector combo    │
│  └─ test_scenario7_discovery_search_interface     ✅ Discovery API           │
│                                                                             │
│  CATEGORY 5: Edge Cases                                                     │
│  ├─ test_hot_path_performance_guardrail  ✅ No unnecessary vector search    │
│  ├─ test_ambiguous_graceful_fail         ✅ Nonsense request handling       │
│  ├─ test_explicit_tool_discover          ✅ Discovery tool rendering        │
│  └─ test_scenario4_ambiguous_graceful_fail        ✅ Graceful degradation   │
│                                                                             │
│  CATEGORY 6: Hot Reload Integration [Phase 36.5]                            │
│  ├─ test_reload_orchestration            ✅ Skill reload flow               │
│  ├─ test_manager_reload_method           ✅ Manager reload implementation   │
│  ├─ test_observer_pattern_basic          ✅ Observer registration           │
│  └─ test_full_reload_cycle               ✅ 3-cycle reload validation       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Test Execution Flow

```
Test Suite Initialization
         │
         ▼
┌─────────────────┐
│ Conftest Setup  │
│ - Mock skills   │
│ - Mock LLM      │
│ - Mock ChromaDB │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Test Execution Pipeline                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Test Scenario Started                                                │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────┐                                                 │
│  │ Setup Phase     │ → Create fixtures, mocks                        │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │ Execute Test    │ → Run assertion logic                           │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │ Assert Result   │ → Verify expected behavior                      │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │ Cleanup Phase   │ → Reset mocks, clear caches                     │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  Test Completed ✓/✗                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Routing Decision Flowchart

```
                          User Request
                              │
                              ▼
                    ┌─────────────────┐
                    │ Semantic Cortex │──Hit──→ Return Cached
                    │  (Fuzzy Match)  │
                    └────────┬────────┘
                             │ Miss
                             ▼
                    ┌─────────────────┐
                    │ Exact Match     │──Hit──→ Return Cached
                    │     Cache       │
                    └────────┬────────┘
                             │ Miss
                             ▼
                    ┌─────────────────┐
                    │  LLM Inference  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │ High                         │ Low / Generic
              │ Confidence                   │ Skills
              │ (≥0.5)                       │ (<0.5)
              ▼                              ▼
    ┌─────────────────┐      ┌─────────────────────────┐
    │ Return Result   │      │ Vector Fallback         │
    │ + Learn         │      │ (ChromaDB Search)       │
    └─────────────────┘      └───────────┬─────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │ Filter: installed_only │
                              │ Return: suggested_     │
                              │ skills + boosted       │
                              │ confidence             │
                              └───────────────────────┘
```

## Routing Configuration

### Default Thresholds

```python
# Semantic Cortex
SIMILARITY_THRESHOLD = 0.75  # Minimum similarity for cache hit
TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Vector Fallback
VECTOR_CONFIDENCE_THRESHOLD = 0.5  # LLM confidence threshold
CONFIDENCE_BOOST = 0.15  # Boost when Vector Fallback triggers

# Cache Settings
EXACT_CACHE_SIZE = 1000  # Max entries in exact match cache
SEMANTIC_CACHE_SIZE = 500  # Max entries in semantic cache
```

### Skills Registry Integration

```python
from agent.core.registry import get_skill_registry

registry = get_skill_registry()

# List all available skills
skills = registry.list_available_skills()

# Get skill manifest for routing
manifest = registry.get_skill_manifest("git")
# Returns:
# {
#     "name": "git",
#     "routing_keywords": ["git", "commit", "branch", "version control"],
#     "description": "Git version control operations",
#     "intents": ["commit", "push", "pull", "branch management"]
# }
```

## Hot Reload Integration [Phase 36.5]

When a skill is reloaded, the routing system is updated automatically:

```
Skill Modified
        ↓
SkillManager.reload(skill_name)
        ↓
Debounced Notification (200ms)
        ↓
Observers Notified:
├─ MCP Observer → send_tool_list_changed()
└─ Index Sync Observer → ChromaDB Upsert
        ↓
Router detects tool list change
        ↓
Next request uses updated skill list
```

**Testing**: See `test_hot_reload.py` for 13 comprehensive tests.

## Performance Characteristics

| Operation                  | Time       | Cache State |
| -------------------------- | ---------- | ----------- |
| Semantic Cortex Hit        | ~1μs       | Warm        |
| Exact Cache Hit            | ~1μs       | Warm        |
| LLM Routing                | ~100-500ms | Cold        |
| Vector Fallback            | ~50-100ms  | Cold        |
| Cache Miss (Full Pipeline) | ~200-600ms | Cold        |

## Running Tests

```bash
# Run all routing tests
uv run pytest packages/python/agent/src/agent/tests/test_semantic_cortex.py -v

# Run discovery flow tests (includes Vector Fallback)
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_discovery_flow.py -v

# Run hot reload integration tests
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_hot_reload.py -v

# Run all routing-related tests
uv run pytest packages/python/agent/src/agent/tests/ -k "routing or cortex or router" -v
```

## Related Files

| File                                           | Purpose                            |
| ---------------------------------------------- | ---------------------------------- |
| `agent/core/router/semantic_router.py`         | Main router implementation         |
| `agent/core/router/semantic_cortex.py`         | Fuzzy cache implementation         |
| `agent/core/router/models.py`                  | RoutingResult, HiveMindCache       |
| `agent/core/skill_manager.py`                  | SkillManager with observer pattern |
| `agent/core/skill_discovery.py`                | VectorSkillDiscovery (Phase 36.2)  |
| `agent/tests/test_semantic_cortex.py`          | Cortex tests                       |
| `agent/tests/scenarios/test_discovery_flow.py` | Discovery flow tests               |
| `agent/tests/scenarios/test_hot_reload.py`     | Hot reload tests                   |

## See Also

- [Skill Discovery](../developer/discover.md) - Phase 36.2 Vector-Enhanced Discovery
- [Trinity Architecture](../explanation/trinity-architecture.md) - System architecture
- [Skills Overview](../skills.md) - Skill implementation guide
