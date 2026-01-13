# Routing Architecture

> **Phase 42: State-Aware Routing** | **Phase 41: Wisdom-Aware Routing** | **Phase 40: Automated Reinforcement Loop** | **Phase 39: Self-Evolving Feedback** | **Phase 36.8: Auto-Route Discovery** | **Phase 36.5: Hot Reload Integration** | **Phase 36.2: Vector-Enhanced Discovery**

## Phase 41: Wisdom-Aware Routing

> **Phase 41**: Inject past lessons from harvested knowledge into Mission Briefs.

### Overview

The routing system now retrieves relevant lessons from `harvested/*.md` and injects them into the system prompt, enabling the LLM to generate Mission Briefs that avoid known pitfalls.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 41: Wisdom-Aware Routing                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query                                                                  │
│       ↓                                                                       │
│  SemanticRouter.route()                                                      │
│       ↓                                                                       │
│  ┌─────────────────────────────────────┐                                    │
│  │  Parallel:                          │                                    │
│  │  - Build routing menu               │                                    │
│  │  - Consult Librarian (harvested/)   │                                    │
│  └─────────────────────────────────────┘                                    │
│       ↓                                                                       │
│  System Prompt + PAST LESSONS                                                │
│       ↓                                                                       │
│  LLM generates wisdom-infused Mission Brief                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                  | Purpose                                         |
| -------------------------- | ----------------------------------------------- |
| `SemanticRouter.librarian` | Lazy-loaded Librarian function                  |
| `_format_lessons()`        | Format knowledge results for prompt             |
| `route()`                  | Parallel knowledge retrieval with menu building |

### Usage

```python
router = SemanticRouter(
    use_wisdom_routing=True,  # Enable wisdom-aware routing (default: True)
)

result = await router.route("Edit tools.py and test it")
# Mission Brief now includes lessons from past sessions
```

### Example

**User Query**: "commit my changes"

**Knowledge Retrieved**:

```markdown
### Git Commit Workflow Best Practices

- Use git_stage_all for bulk staging (more reliable than individual)
```

**Generated Mission Brief**:

```
Commit staged changes with message 'feat(router): add wisdom-aware routing'.

IMPORTANT: Use git_stage_all for bulk staging as individual staging
can be unreliable (per past session lesson).
```

### Related Files

| File                                           | Purpose                                  |
| ---------------------------------------------- | ---------------------------------------- |
| `agent/core/router/semantic_router.py`         | Librarian integration, lesson formatting |
| `agent/capabilities/knowledge/librarian.py`    | `consult_knowledge_base` function        |
| `assets/specs/phase41_wisdom_aware_routing.md` | Phase 41 spec                            |

---

## Phase 42: State-Aware Routing

> **Phase 42**: Ground routing in reality - prevent hallucinated actions by detecting environment state.

### Overview

The routing system now detects real-time environment state (Git status, active context) and injects it into the routing prompt, preventing the router from suggesting actions that conflict with current reality.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 42: State-Aware Routing                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query                                                                  │
│       ↓                                                                       │
│  SemanticRouter.route()                                                      │
│       ↓                                                                       │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Three-Way Parallel:                                │                    │
│  │  - Build routing menu (blocking, ~5ms)              │                    │
│  │  - Consult Librarian for wisdom (parallel, ~50ms)   │                    │
│  │  - ContextSniffer.get_snapshot() (parallel, ~10ms)  │                    │
│  └─────────────────────────────────────────────────────┘                    │
│       ↓                                                                       │
│  System Prompt + WISDOM + ENVIRONMENT STATE                                  │
│       ↓                                                                       │
│  LLM generates reality-grounded Mission Brief                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                    | Purpose                                |
| ---------------------------- | -------------------------------------- |
| `ContextSniffer`             | Fast, async environment state detector |
| `get_sniffer()`              | Singleton accessor for ContextSniffer  |
| `sniffer.get_snapshot()`     | Returns formatted environment state    |
| `RoutingResult.env_snapshot` | Field to store environment snapshot    |

### What ContextSniffer Detects

1. **Git Status**
   - Current branch name
   - Number of modified files
   - Up to 3 modified file names (with +N more indicator)

2. **Active Context**
   - Reads `.memory/active_context/SCRATCHPAD.md`
   - Reports line count or "Empty" state

### Usage

```python
router = SemanticRouter(
    use_wisdom_routing=True,  # Wisdom-aware routing (default: True)
    # State-aware routing is always enabled
)

result = await router.route("commit my changes")
print(result.env_snapshot)
# Output:
# [ENVIRONMENT STATE]
# - Branch: main | Modified: 5 files (M src/a.py, ...)
# - Active Context: 42 lines in SCRATCHPAD.md
```

### CLI Integration

```bash
$ omni route invoke "commit my changes" --verbose

# Output includes environment state panel:
╭──────────────────────── [Phase 42] Environment State ────────────────────────╮
│ [ENVIRONMENT STATE]                                                          │
│ - Branch: main | Modified: 51 files (M assets/references.yaml, ...)          │
│ - Active Context: Empty                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### How It Works

1. **Parallel Execution**: Menu building, wisdom retrieval, and environment sniffing happen in parallel
2. **Async I/O**: Git commands run async to avoid blocking
3. **Lazy Loading**: ContextSniffer is lazily loaded to avoid slow initialization
4. **Graceful Degradation**: If sniffing fails, continues with empty snapshot

### Related Files

| File                                   | Purpose                                |
| -------------------------------------- | -------------------------------------- |
| `agent/core/router/sniffer.py`         | ContextSniffer class                   |
| `agent/core/router/semantic_router.py` | Three-way parallel, env_snapshot field |
| `agent/core/router/models.py`          | RoutingResult.env_snapshot field       |
| `agent/cli/commands/route.py`          | Display environment snapshot in CLI    |

### Related Specs

- `assets/specs/phase42_state_aware_routing.md`
- `assets/specs/phase41_wisdom_aware_routing.md`

---

## Phase 39/40: Self-Evolving Feedback Loop

> **Phase 40**: The system now **learns from experience**. Successful routing decisions boost future confidence automatically.

### Overview

The routing system now includes a feedback loop that learns from successful routing decisions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 39/40: Self-Evolving Routing                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query → Semantic Router → Skill Execution → Feedback Recording        │
│       ↓              ↓                ↓                   ↓                  │
│  Vector Search    Hybrid Score    Success?        FeedbackStore             │
│  (ChromaDB)       (+keyword)      (Reviewer)      (.memory/routing_        │
│                                      Approval         feedback.json)        │
│       ↓              ↓                ↓                   ↓                  │
│  Confidence    Final Score    High Signal         Boost +0.1               │
│  0.60          0.95           → Future queries → Confidence 0.70           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Feedback Boost in Scoring

The final routing score now includes a feedback boost:

```
Final Score = Base Vector Score
            + Keyword Bonus (+0.1-0.3)
            + Verb Priority Boost (+0.2 for CORE_ACTION_VERBS)
            + Feedback Boost (+0.1 per success, max +0.3)
            - Sigmoid Calibration (stretch 0.3-0.95 range)
```

### Automatic Feedback Sources

| Signal Source         | Trigger                    | Boost                              |
| --------------------- | -------------------------- | ---------------------------------- |
| **CLI Success**       | `omni git.status` executes | +0.1                               |
| **Reviewer Approval** | Audit passes               | +0.1 (trusted signal)              |
| **Time Decay**        | Each read                  | 1% decay to prevent Matthew effect |

### Feedback Storage

**Location**: `.memory/routing_feedback.json`

```json
{
  "git.status": {
    "git": 0.1
  },
  "commit code": {
    "git": 0.2
  }
}
```

### Router Integration

```python
from agent.capabilities.learning.harvester import get_feedback_boost

# In SemanticRouter.route()
feedback_bonus = get_feedback_boost(query, skill_id)
final_confidence = base_confidence + feedback_bonus
```

### Viewing Learned Feedback

```bash
# View what the system has learned
cat .memory/routing_feedback.json

# Clear feedback (if needed)
echo "{}" > .memory/routing_feedback.json
```

### Related Specs

- `assets/specs/phase39_self_evolving_feedback_loop.md`
- `assets/specs/phase40_automated_reinforcement_loop.md`

---

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

## Phase 36.8: Auto-Route Skill Discovery

**Auto-Trigger Skill Discovery** - When users express intent through natural language, the system can automatically discover and prepare skills.

### Auto-Route Command

```python
@omni("skill.auto_route", {"task": "analyze pcap file"})
```

### Flow

```
User: "Analyze this pcap file"
    ↓
@omni("skill.auto_route", {"task": "analyze pcap file"})
    ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1: Search local skills (installed)                 │
│ Step 2: Check if loaded                                 │
│                                                         │
│ Case 1: Already loaded → ✅ Ready to execute!          │
│ Case 2: Local but not loaded → 🔄 Auto-load!           │
│ Case 3: No local skills → ☁️ Show remote suggestions   │
└─────────────────────────────────────────────────────────┘
```

### Output Examples

**Case 1: Already Loaded**

```markdown
# 🎯 Auto-Route: Task Preparation

**Task**: analyze pcap file

✅ **Skill is loaded and ready!**

**Skill**: network-analysis
**Confidence**: 92%

👉 **Ready to execute**: `network-analysis.help`
```

**Case 2: Auto-Loaded**

```markdown
# 🎯 Auto-Route: Task Preparation

**Task**: analyze pcap file

🔄 **Skill loaded automatically!**

**Skill**: network-analysis
**Confidence**: 92%

👉 **Ready**: `network-analysis.help`
```

**Case 3: Remote Suggestions**

```markdown
# 🎯 Auto-Route: Task Preparation

**Task**: analyze pcap file

☁️ **No matching local skills found**

**Suggested skills**:

1. **network-analysis** - Analyze network traffic... (92%)
2. **packet-capture** - Capture network packets... (85%)

**To install**:
@omni("skill.jit_install", {"skill_id": "network-analysis"})
```

### Parameters

| Parameter      | Type    | Required | Default | Description                       |
| -------------- | ------- | -------- | ------- | --------------------------------- |
| `task`         | string  | Yes      | -       | Natural language task description |
| `auto_install` | boolean | No       | false   | Auto-install remote skills        |

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
