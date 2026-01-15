# Phase 39: The Harvester Loop (Self-Evolving Feedback Loop)

**Status**: Implemented
**Type**: Architecture Enhancement
**Owner**: Harvester (The Distiller)
**Vision**: Learning from experience - the system improves its routing decisions over time

## 1. Problem Statement

**The Pain: Stateless Routing**

```
User: "commit code" → Router selects git skill (0.60 confidence)
User: "commit code" → Router selects git skill (0.60 confidence)
User: "commit code" → Router selects git skill (0.60 confidence)
...
```

**What's Missing:**

- No memory of successful routing decisions
- Each query is treated as completely new
- System doesn't learn from user behavior
- "commit code" always starts from baseline, never improves

**Root Cause:**

The semantic router has no feedback mechanism. It optimizes for first-match accuracy but ignores the user's implicit validation of routing decisions.

## 2. The Solution: Self-Evolving Feedback Loop

The Harvester captures successful routing outcomes and uses them to boost future confidence:

```
User Query
     ↓
  Semantic Router (Select skill with base confidence)
     ↓
  Skill Execution
     ↓
  User Accepts / Reviewer Approves
     ↓
  Harvester Records (query, skill_id, success=True)
     ↓
  Future queries → Vector scoring includes feedback boost (+0.1 per success)
```

## 3. Architecture Specification

### 3.1 FeedbackStore Data Structure

```python
class FeedbackStore:
    """Lightweight store for routing reinforcement learning.

    Maps (normalized_query, skill_id) -> score (weight adjustment).
    Positive scores boost future routing, negative scores penalize.
    """
    MIN_SCORE = -0.3   # Maximum penalty
    MAX_SCORE = 0.3    # Maximum boost
    DECAY_FACTOR = 0.1  # How much each feedback affects score
    TIME_DECAY_RATE = 0.99  # [Phase 40] Decay multiplier per read (1% decay)

    def record_feedback(self, query: str, skill_id: str, success: bool) -> float:
        """Record user feedback for a routing decision."""

    def get_boost(self, query: str, skill_id: str) -> float:
        """Get the learned boost/penalty for a skill given a query."""
```

### 3.2 Storage Format

**Location**: `.memory/routing_feedback.json`

```json
{
  "commit code": {
    "git": 0.2,
    "terminal": -0.1
  },
  "write documentation": {
    "documentation": 0.3
  }
}
```

### 3.3 Vector Scoring Integration

```python
def hybrid_search(query: str, limit: int = 5) -> list[dict]:
    """Phase 37/38: Hybrid search with feedback boost."""
    # ... base vector + keyword search ...

    # Phase 39: Add feedback boost
    for skill in results:
        feedback_bonus = get_feedback_boost(query, skill["id"])
        skill["score"] += feedback_bonus
        skill["feedback_bonus"] = feedback_bonus

    return sorted(results, key=lambda x: x["score"], reverse=True)
```

### 3.4 Scoring Formula

```
Final Score = Base Vector Score
            + Keyword Bonus (+0.1-0.3)
            + Verb Priority Boost (+0.2 for CORE_ACTION_VERBS)
            + Feedback Boost (+0.1 per successful routing, max +0.3)
            - Sigmoid Calibration (stretch 0.3-0.95 range)
```

## 4. File Changes

### 4.1 New Files

| File                                                                 | Purpose                                   |
| -------------------------------------------------------------------- | ----------------------------------------- |
| `packages/python/agent/src/agent/capabilities/learning/harvester.py` | FeedbackStore class + harvester functions |

### 4.2 Modified Files

| File                                                             | Change                                      |
| ---------------------------------------------------------------- | ------------------------------------------- |
| `packages/python/agent/src/agent/core/skill_discovery/vector.py` | Integrate feedback_boost into hybrid search |
| `packages/python/agent/src/agent/core/router/semantic_router.py` | Show feedback reasoning in output           |

## 5. Implementation Plan

### Step 1: FeedbackStore Foundation

- [x] Create FeedbackStore class with lazy loading
- [x] Implement JSON persistence to `.memory/routing_feedback.json`
- [x] Implement `record_feedback()` with score clamping
- [x] Implement `get_boost()` for score retrieval

### Step 2: Vector Scoring Integration

- [x] Add `_get_feedback_boost_safe()` wrapper for safe imports
- [x] Integrate feedback_bonus into final score calculation
- [x] Update skill search results to show feedback influence

### Step 3: Router Reasoning

- [x] Update semantic_router to show "(Reinforced by past success +0.10)"
- [x] Add feedback boost to scoring breakdown display

### Step 4: Testing

- [x] Test FeedbackStore record/get operations
- [x] Test score clamping (MIN/MAX bounds)
- [x] Test decay mechanism (Phase 40)
- [x] Test vector scoring with feedback boost

## 6. Success Criteria

1. **Learning**: Successful routing increases future confidence by +0.1
2. **Bounds**: Feedback boost never exceeds +0.3 or drops below -0.3
3. **Persistence**: Feedback survives restart (JSON file)
4. **Transparency**: Router shows feedback influence in reasoning

## 7. Before vs After Comparison

### Before (Phase 38)

```
Query: "commit code"
  Vector: 0.65
  Keyword: +0.10 (commit)
  Verb: +0.15 (git push, git commit)
  --------------------------------
  Final: 0.90 (stateless, no memory)
```

### After (Phase 39)

```
Query: "commit code"
  Vector: 0.65
  Keyword: +0.10 (commit)
  Verb: +0.15 (git push, git commit)
  Feedback: +0.10 (3 successful commits before)
  --------------------------------
  Final: 1.00 (self-improving)
```

## 8. Performance Impact

| Metric              | Before   | After                         |
| ------------------- | -------- | ----------------------------- |
| First query         | Baseline | Baseline                      |
| 5th identical query | Baseline | +0.50 boost                   |
| Storage             | N/A      | ~1KB per 100 feedback entries |
| Lookup overhead     | N/A      | ~0.1ms                        |

## 9. Related Documentation

- `docs/explanation/trinity-architecture.md` - Trinity architecture overview
- `packages/python/agent/src/agent/capabilities/learning/harvester.py` - Implementation
- `packages/python/agent/src/agent/core/skill_discovery/vector.py` - Hybrid search
- `packages/python/agent/src/agent/core/router/semantic_router.py` - Router integration
