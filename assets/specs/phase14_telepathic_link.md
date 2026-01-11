# Phase 14: The Telepathic Link (Mission Brief Protocol)

**Status**: Draft
**Type**: Architecture Enhancement
**Owner**: Orchestrator (The Brain)
**Vision**: Eliminate context distillation loss between Router and Worker

## 1. Problem Statement

**The Pain: Context Distillation Loss**

```
User: "Fix this bug, it's an IndexError."

Router (LLM): (Thinks: Python issue, needs filesystem and git) → Activates Skills.

Worker (Main LLM): (Wakes up, sees tools) "Hello, what do you want?
                    Oh, fix a bug. Let me re-analyze this IndexError..."
```

**What's Wasted:**

- Router spends 2 seconds understanding: "IndexError in src/main.py, need read_file + write_file + git_commit"
- Worker receives: `["filesystem", "git"]` (tool list only)
- Worker must re-analyze: "User wants me to fix a bug... What bug? Which file?"

**Root Cause:**
Router returns ONLY skill names, losing all the semantic understanding it generated.

## 2. The Solution: Mission Brief Protocol

Router not only selects skills but generates a **tactical mission brief** that is injected into Worker's System Prompt.

```
User: "commit my changes with message 'feat(api): add auth'"

Router → Worker:
  skills: ["git"]
  mission_brief: "Commit the staged changes with message
                  'feat(api): add auth'. BEFORE committing,
                  show commit analysis for user confirmation.
                  Then execute git_commit."

Worker: (Immediately understands what to do, no re-thinking needed)
```

## 3. Architecture Specification

### 3.1 RoutingResult Data Structure

```python
@dataclass
class RoutingResult:
    selected_skills: List[str]   # Skills to activate
    mission_brief: str            # 🚀 Actionable directive for Worker
    reasoning: str                # Audit trail
    confidence: float             # 0.0-1.0
    from_cache: bool              # Cache hit flag
    timestamp: float              # Decision timestamp
```

### 3.2 Hive Mind Cache

LRU cache for zero-latency routing on repeated queries:

```python
class HiveMindCache:
    """Zero-latency routing for high-frequency queries."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, RoutingResult] = {}

    async def route(self, query: str) -> RoutingResult:
        # Check cache first (O(1))
        if query_hash in self.cache:
            return self.cache[query_hash].with_flag(from_cache=True)

        # LLM call only on cache miss
        result = await self._llm_route(query)
        self.cache[query_hash] = result
        return result
```

### 3.3 Context Injection Format

```python
def build_mission_injection(routing_result: RoutingResult) -> str:
    return f"""
╔═══════════════════════════════════════════════════════════════╗
║ 🚀 MISSION BRIEF (from Orchestrator)                          ║
╠═══════════════════════════════════════════════════════════════╣
║ 🟢 HIGH CONFIDENCE | Skills: {routing_result.selected_skills} ║
╠═══════════════════════════════════════════════════════════════╣
║ 📋 YOUR OBJECTIVE:                                            ║
║ {routing_result.mission_brief}                                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
```

## 4. File Changes

### 4.1 New Files

| File                                                      | Purpose                            |
| --------------------------------------------------------- | ---------------------------------- |
| `packages/python/agent/src/agent/core/context_builder.py` | Mission injection utilities        |
| `scripts/test_router.py`                                  | Routing test suite (23 test cases) |

### 4.2 Modified Files

| File                                             | Change                                                     |
| ------------------------------------------------ | ---------------------------------------------------------- |
| `packages/python/agent/src/agent/core/router.py` | Add RoutingResult, HiveMindCache, mission_brief generation |
| `packages/python/agent/src/agent/core/schema.py` | Add `routing_keywords` field to SkillManifest              |
| `agent/skills/*/manifest.json`                   | Add `routing_keywords` array                               |

### 4.3 Manifest Enhancement

```json
{
  "name": "git",
  "routing_keywords": [
    "git",
    "commit",
    "push",
    "pull",
    "branch",
    "merge",
    "version control",
    "repo",
    "history"
  ],
  "description": "Git integration with Ops, Smart Commit V2..."
}
```

## 5. Implementation Plan

### Step 1: Data Foundation

- [x] Add `routing_keywords` to SkillManifest schema
- [x] Update all skill manifests with routing keywords

### Step 2: Router Enhancement

- [x] Create RoutingResult dataclass
- [x] Implement HiveMindCache (LRU, TTL)
- [x] Update SemanticRouter.route() to generate mission_brief

### Step 3: Context Injection

- [x] Create context_builder.py
- [x] Implement build_mission_injection()
- [x] Implement route_and_build_context()

### Step 4: Testing

- [x] Create test_router.py with 23 test cases
- [x] Test cache behavior (0ms hits)
- [x] Test mission brief quality

## 6. Success Criteria

1. **Mission Brief Generation**: Router returns actionable mission_brief for all queries
2. **Cache Hit**: Repeated queries return in < 1ms
3. **Test Coverage**: 100% pass rate on routing test suite
4. **Zero Regression**: All existing unit tests pass (145/145)

## 7. Before vs After Comparison

### ❌ Before (Phase 13.9)

```
Router output: {"skills": ["git"]}
Worker: "What tools do I have? Which one to use? What was the user's intent?"
```

### ✅ After (Phase 14.0)

```
Router output: {
  "skills": ["git"],
  "mission_brief": "Commit with message X. Show analysis first.",
  "confidence": 1.0
}
Worker: "Clear! Show analysis, wait for confirmation, commit."
```

## 8. When to Use Mission Brief

| Scenario                 | Use Mission Brief? |
| ------------------------ | ------------------ |
| Simple file read         | ❌ Not needed      |
| Commit with confirmation | ✅ Essential       |
| Complex bug fix          | ✅ Essential       |
| Testing workflow         | ✅ Essential       |
| General conversation     | ❌ Overkill        |

## 9. Performance Impact

| Metric             | Before         | After          |
| ------------------ | -------------- | -------------- |
| First "run tests"  | ~2s (LLM call) | ~2s (LLM call) |
| Second "run tests" | ~2s (LLM call) | ~0ms (cache)   |
| Worker re-analysis | Required       | Eliminated     |

## 10. Related Documentation

- `docs/explanation/mcp-architecture-roadmap.md` - Phase 14 section
- `scripts/test_router.py` - Test suite with examples
- `packages/python/agent/src/agent/core/router.py` - Implementation
- `packages/python/agent/src/agent/core/context_builder.py` - Injection utilities
