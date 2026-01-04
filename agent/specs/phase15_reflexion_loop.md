# Phase 15: The Reflexion Loop (Virtuous Cycle)

**Status**: Implemented
**Type**: Architecture Enhancement
**Owner**: ReviewerAgent (The Gatekeeper)
**Vision**: Self-correcting agents through feedback loops

## 1. Problem Statement

**The Pain: No Quality Gate**

```
Coder: (Produces output)
Orchestrator: "Looks good, returning to user."
User: "This code has bugs and no tests!"
```

**What's Missing:**

- No automated quality verification before returning to user
- Coder output goes directly to user without review
- No mechanism for self-correction when quality is poor
- Blind trust in agent output

**Root Cause:**
Phase 14's Telepathic Link only connects Router → Worker, not Worker → Quality Gate.

## 2. The Solution: Virtuous Cycle

The ReviewerAgent acts as a quality gate in a feedback loop:

```
User Request
     ↓
  Router → CoderAgent (First attempt)
     ↓
  ReviewerAgent.audit() (Quality Check)
     ↓
  ┌──────────┐
  │ Pass?    │─── No ──→ CoderAgent (Retry with feedback)
  └────┬─────┘
       │ Yes
       ↓
  Return to User
```

## 3. Architecture Specification

### 3.1 AuditResult Data Structure

```python
@dataclass
class AuditResult:
    approved: bool              # Pass/fail decision
    feedback: str               # Constructive feedback
    confidence: float           # 0.0-1.0
    issues_found: List[str]    # Specific issues detected
    suggestions: List[str]     # Improvement recommendations
```

### 3.2 ReviewerAgent Audit Flow

```python
class ReviewerAgent(BaseAgent):
    """Quality Gatekeeper Agent."""

    async def audit(
        self,
        task: str,
        agent_output: str,
        context: Dict[str, Any] = None
    ) -> AuditResult:
        """
        Audit another agent's output (Feedback Loop).

        This is the core of the Virtuous Cycle.
        """
        # Build audit prompt with task context
        audit_prompt = self._build_audit_prompt(task, agent_output, context)

        # LLM evaluates quality (placeholder for actual LLM call)
        # result = await self.inference.chat(query=agent_output, system_prompt=audit_prompt)

        # Return structured audit result
        return AuditResult(
            approved=approved,
            feedback=feedback,
            confidence=confidence,
            issues_found=issues,
            suggestions=suggestions
        )
```

### 3.3 Audit Criteria

| Criterion        | Description                                |
| ---------------- | ------------------------------------------ |
| **Completeness** | Does it solve the user's request?          |
| **Correctness**  | Is the solution logically sound?           |
| **Safety**       | Are there obvious bugs or security issues? |
| **Quality**      | Is the code idiomatic and well-structured? |

### 3.4 Narrow Context for Reviewer

Reviewer only sees quality-related skills:

```python
default_skills = [
    "git",              # View diffs, check status, create commits
    "testing",          # Run pytest and analyze results
    "documentation",    # Verify docs are updated
    "linter",           # Run code quality checks
    "terminal",         # Run verification commands
]
```

**Reviewer does NOT have:**

- File modification skills (use CoderAgent)
- Broad read access (limited scope)

## 4. File Changes

### 4.1 New Files

| File                                                                   | Purpose                    |
| ---------------------------------------------------------------------- | -------------------------- |
| `packages/python/agent/src/agent/core/agents/reviewer.py`              | ReviewerAgent with audit() |
| `packages/python/agent/src/agent/tests/test_phase15_reflexion_loop.py` | Reflexion loop tests       |

### 4.2 Modified Files

| File                                                   | Change                              |
| ------------------------------------------------------ | ----------------------------------- |
| `packages/python/agent/src/agent/core/agents/base.py`  | Add AuditResult, update AgentResult |
| `packages/python/agent/src/agent/core/agents/coder.py` | Integrate with feedback loop        |

## 5. Implementation Plan

### Step 1: Data Foundation

- [x] Add `AuditResult` dataclass to base.py
- [x] Add `audit_result` and `needs_review` fields to AgentResult
- [x] Define audit criteria in ReviewerAgent

### Step 2: ReviewerAgent Implementation

- [x] Create ReviewerAgent class with narrow context
- [x] Implement `audit()` method for quality verification
- [x] Implement `_build_audit_prompt()` for audit prompt generation
- [x] Implement `should_commit()` for commit recommendations

### Step 3: Integration with Feedback Loop

- [x] CoderAgent returns output with audit metadata
- [x] Orchestrator calls ReviewerAgent.audit() before returning to user
- [x] Retry logic when audit fails

### Step 4: Testing

- [x] Create test_phase15_reflexion_loop.py
- [x] Test audit approval/rejection logic
- [x] Test feedback quality
- [x] Test retry mechanism

## 6. Success Criteria

1. **Audit Coverage**: All agent output passes through ReviewerAgent
2. **Quality Improvement**: Audit catches obvious issues before user sees them
3. **Self-Correction**: Failed audits trigger retry with feedback
4. **Test Coverage**: 100% pass rate on reflexion loop tests

## 7. Before vs After Comparison

### ❌ Before (Phase 14)

```
Coder → Output → User
                (No quality gate)
```

### ✅ After (Phase 15)

```
Coder → Output → Reviewer.audit() → Pass? → User
                ↓                    │
                └──── Fail ─────────┘
                     ↓
                   Retry with feedback
```

## 8. Extension: Human-in-the-loop

For low-confidence audits:

```python
class ReviewerAgent(BaseAgent):
    async def audit(self, task, agent_output, context=None):
        confidence = await self._assess_confidence(agent_output)
        if confidence < 0.7:
            return await self._request_human_review()
        return await self._auto_approve()
```

## 9. Performance Impact

| Metric           | Before     | After              |
| ---------------- | ---------- | ------------------ |
| User sees output | Immediate  | +100-500ms (audit) |
| Bug detection    | User finds | Automated          |
| Code quality     | Variable   | Enforced           |

## 10. Related Documentation

- `docs/explanation/agent-vs-skill.md` - Why Reviewer is an Agent
- `packages/python/agent/src/agent/core/agents/reviewer.py` - Implementation
- `packages/python/agent/src/agent/core/agents/base.py` - BaseAgent, AuditResult
- `packages/python/agent/src/agent/tests/test_phase15_reflexion_loop.py` - Test suite
