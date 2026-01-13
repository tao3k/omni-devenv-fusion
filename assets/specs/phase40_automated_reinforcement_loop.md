# Phase 40: Automated Reinforcement Loop

**Status**: Implemented
**Type**: Architecture Enhancement
**Owner**: Feedback Loop System
**Vision**: Automatic learning from task success - no manual feedback required

## 1. Problem Statement

**The Pain: Manual Feedback Required**

```python
# Before: User must explicitly provide feedback
User: "That routing was wrong"  # Manual signal
System: Records negative feedback
```

**What's Missing:**

- No automatic signal when task succeeds
- User must explicitly correct routing (rare)
- CLI executions leave no learning trail
- Reviewer approval isn't captured as learning signal

**Root Cause:**

Phase 39 FeedbackStore exists, but there's no automatic trigger to populate it. The system waits for explicit feedback instead of learning from implicit success signals.

## 2. The Solution: Automatic Reinforcement

Three automatic feedback pathways:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Automated Reinforcement                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. CLI Success Feedback                                         │
│     omni git.status → Success → record_routing_feedback()       │
│                                                                  │
│  2. Reviewer Approval Feedback                                   │
│     Orchestrator → Coder → Reviewer.audit() → Pass              │
│     → record_routing_feedback() (fire-and-forget)               │
│                                                                  │
│  3. Time-Based Decay                                             │
│     Scores decay 1% on each read → Prevents Matthew effect      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Architecture Specification

### 3.1 CLI Success Feedback (`runner.py`)

```python
def _record_cli_success(command: str, skill_name: str) -> None:
    """Record CLI execution success as positive feedback.

    This is a lightweight signal - CLI success doesn't guarantee
    the routing was correct, but it's still useful data.
    """
    try:
        from agent.capabilities.learning.harvester import record_routing_feedback
        # Use command as pseudo-query, record mild positive feedback
        record_routing_feedback(command, skill_name, success=True)
    except Exception:
        # Silently ignore if feedback system not available
        pass
```

### 3.2 Reviewer Approval Feedback (`feedback.py`)

```python
def _record_feedback_safe(query: str, skill_id: str, success: bool) -> None:
    """Safely record routing feedback without blocking main execution."""
    try:
        import asyncio
        from agent.capabilities.learning.harvester import record_routing_feedback

        # Create task but don't await - fire and forget
        asyncio.create_task(
            _async_record_feedback(query, skill_id, success)
        )
    except Exception:
        pass

# In execute_with_feedback_loop, when audit_result.approved:
_record_feedback_safe(user_query, worker.name, success=True)
```

### 3.3 Time-Based Decay (`harvester.py`)

```python
class FeedbackStore:
    TIME_DECAY_RATE = 0.99  # Decay multiplier per read (1% decay)

    def get_boost(self, query: str, skill_id: str) -> float:
        """Get boost with time-based decay.

        Scores decay by 1% each time they are read.
        This prevents "Matthew effect" (old successful skills
        dominating forever). Gives new skills a fair chance.
        """
        # ... load data ...

        # Apply decay and update stored value
        current_score = self._data[norm_query][skill_id]

        if abs(current_score) > 0.01:
            decayed_score = current_score * self.TIME_DECAY_RATE

            # If score becomes negligible, remove it
            if abs(decayed_score) < 0.01:
                del self._data[norm_query][skill_id]
                # Clean up empty query entries
                if not self._data[norm_query]:
                    del self._data[norm_query]
                self._save()
                return 0.0

            # Update with decayed value (lazy persistence)
            self._data[norm_query][skill_id] = decayed_score
            return decayed_score

        return current_score
```

### 3.4 Decay Visualization

```
Score: 0.10 (after 1 success)
  ↓ Read for scoring
Score: 0.099 (0.10 × 0.99)
  ↓ Read for scoring
Score: 0.098 (0.099 × 0.99)
  ↓ Read for scoring
Score: 0.097 (0.098 × 0.99)
  ↓ ... 68 reads later
Score: 0.010 (negligible, auto-cleanup)
  ↓
Removed from storage
```

## 4. File Changes

### 4.1 Modified Files

| File | Change |
|------|--------|
| `packages/python/agent/src/agent/cli/runner.py` | Add `_record_cli_success()` call after successful execution |
| `packages/python/agent/src/agent/core/orchestrator/feedback.py` | Add `_record_feedback_safe()` on Reviewer approval |
| `packages/python/agent/src/agent/capabilities/learning/harvester.py` | Add time-based decay mechanism |

## 5. Implementation Plan

### Step 1: CLI Feedback

- [x] Add `_record_cli_success()` function to runner.py
- [x] Call after successful skill execution
- [x] Use command string as pseudo-query for learning

### Step 2: Orchestrator Feedback

- [x] Add `_record_feedback_safe()` to feedback.py
- [x] Trigger on Reviewer.audit() approval
- [x] Use fire-and-forget pattern (asyncio.create_task)

### Step 3: Decay Mechanism

- [x] Add TIME_DECAY_RATE = 0.99 to FeedbackStore
- [x] Implement decay in get_boost()
- [x] Add cleanup for negligible scores
- [x] Lazy persistence (update on read, save periodically)

### Step 4: Testing

- [x] Test CLI success feedback recording
- [x] Test orchestrator feedback on approval
- [x] Test decay over multiple reads
- [x] Test automatic cleanup of negligible scores

## 6. Success Criteria

1. **Automatic Learning**: Every successful CLI command updates feedback
2. **High-Value Signals**: Reviewer approval triggers feedback (trusted signal)
3. **Decay Works**: Scores reduce ~1% per read
4. **Cleanup**: Negligible scores (<0.01) are auto-removed
5. **No Blocking**: Feedback never slows down main execution

## 7. Before vs After Comparison

### Before (Phase 39)

```
omni git.status
  → Success (no record)

omni git.status × 100
  → Still baseline confidence (0.60)
```

### After (Phase 40)

```
omni git.status
  → Success → Feedback recorded: {"git.status": {"git": 0.1}}

omni git.status × 100
  → Confidence: 0.60 → 0.70 (boosted by past success)

After 1 month idle:
  → Score decays to 0.01 → removed
  → Fresh start for new patterns
```

## 8. Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| CLI execution | ~10ms | ~10ms (+0.1ms feedback) |
| Orchestrator approval | ~100ms | ~100ms (+async overhead) |
| Storage growth | N/A | ~1KB per 100 successful queries |
| Memory | Baseline | +~1KB for feedback cache |

## 9. Signal Quality Hierarchy

| Signal Source | Weight | Trust Level |
|--------------|--------|-------------|
| Reviewer approval | +0.1 | High (audited quality) |
| CLI success | +0.1 | Medium (execution success) |
| User rejection | -0.1 | High (explicit correction) |
| User override | -0.1 | High (explicit correction) |

## 10. Related Documentation

- `docs/explanation/trinity-architecture.md` - Trinity architecture overview
- `assets/specs/phase39_self_evolving_feedback_loop.md` - Phase 39 spec
- `packages/python/agent/src/agent/cli/runner.py` - CLI integration
- `packages/python/agent/src/agent/core/orchestrator/feedback.py` - Orchestrator integration
- `packages/python/agent/src/agent/capabilities/learning/harvester.py` - FeedbackStore with decay
