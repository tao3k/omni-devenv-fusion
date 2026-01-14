# Phase 59: The Meta-Agent

> **Status**: Implemented
> **Date**: 2026-01-13
> **Related**: Phase 39 (Self-Evolving Feedback Loop), Phase 40 (Automated Reinforcement), Phase 44 (Experiential Agent)

## Overview

Phase 59 introduces **The Meta-Agent** - an autonomous "Build-Test-Improve" loop that implements a self-directed TDD (Test-Driven Development) cycle. This transforms the agent from a passive tool into an active engineer that can:

1. **Test**: Run tests and capture failures
2. **Analyze**: Understand what's broken using LLM
3. **Fix**: Generate and apply code fixes
4. **Verify**: Re-run tests to confirm修复
5. **Reflect**: Log the experience for future learning

This completes the vision of **Autonomous Engineering (自主工程)** - a system that can continuously improve itself without human intervention.

## The Problem

**Before Phase 59**: Agent is reactive, not proactive

- Agent waits for human instructions to fix issues
- No autonomous debugging capability
- Lessons from failures are logged but not acted upon
- Each fix requires human in the loop

```
Human: "The tests are failing in test_math.py"
Agent: "I see the failures. What should I fix?"
Human: "Fix the add function - it's using subtraction"
Agent: [Fixes it manually]
```

## The Solution: Autonomous TDD Loop

Phase 59 implements a closed-loop improvement system:

```
+-----------------------------------------------------------------------------+
|                         Phase 59: The Meta-Agent                           |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +---------------------------------------------------------------------+   |
|  |                    TDD Cycle (5 iterations max)                     |   |
|  |                                                                       |   |
|  |   +------------+    +------------+    +------------+                |   |
|  |   |   TEST     | -> |  ANALYZE   | -> |    FIX     |                |   |
|  |   | Run tests  |    | LLM analysis|    | Apply code |                |   |
|  |   +------------+    +------------+    +------------+                |   |
|  |         |                                    |                       |   |
|  |         v                                    v                       |   |
|  |   +------------+    +------------+                                |   |
|  |   | All pass?  | <- |  VERIFY    |                                |   |
|  |   |            |    | Re-run tests|                                |   |
|  |   +------------+    +------------+                                |   |
|  |         |                                                         |   |
|  |         v                                                         |   |
|  |   +------------+                                                  |   |
|  |   |  REFLECT   | -> Vector Store (learn from mission)             |   |
|  |   +------------+                                                  |   |
|  +---------------------------------------------------------------------+   |
|                                                                             |
+-----------------------------------------------------------------------------+
```

## Core Components

### 1. MissionContext

```python
@dataclass
class MissionContext:
    mission_id: str           # Unique identifier
    target_path: Path         # Code under test
    test_command: str         # Command to run tests
    created_at: datetime      # When mission started
    iterations: int           # TDD iterations used
    test_results: List[TestResult]  # All test outcomes
```

### 2. TestResult

```python
@dataclass
class TestResult:
    name: str              # e.g., "test_math.py::test_add"
    status: TestStatus     # PASS, FAIL, ERROR, SKIP
    output: str            # Test output
    error_message: Optional[str]
    duration_ms: float
```

### 3. MetaAgent Class

```python
class MetaAgent:
    """Autonomous Build-Test-Improve Loop."""

    async def run_mission(
        self,
        mission_description: str,
        test_command: str,
        target_path: Optional[str] = None,
    ) -> MissionContext:
        """
        Run a single mission: test -> analyze -> fix -> verify -> reflect.

        This is the main entry point for autonomous improvement.
        """

    async def run_continuous_improvement(
        self,
        max_iterations: int = 3,
        mission_description: str = "Continuous code improvement",
    ) -> List[MissionContext]:
        """
        Run multiple improvement missions until tests pass or max reached.
        """
```

## The TDD Cycle (Implementation)

### Phase 59.1: The Test Loop

```python
async def _run_tests(self, context: MissionContext) -> bool:
    """Run the test command and parse results."""
    result = subprocess.run(
        context.test_command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(self.project_root),
        timeout=120,
    )

    # Parse pytest output
    output = result.stdout + result.stderr
    context.test_results = self._parse_pytest_output(output, duration_ms)

    # Return True if all tests passed
    return result.returncode == 0
```

### Phase 59.2: The Analyzer

```python
async def _analyze_failures(self, context: MissionContext) -> Dict[str, Any]:
    """
    Phase 59.2: The Analyzer - Understand failures using LLM.

    Returns analysis with:
    - Root cause identification
    - Fix suggestions
    - Affected code locations
    """
    if self._llm_provider:
        # Use LLM for intelligent analysis
        analysis = await self._llm_provider.analyze_failure(failure_summary)
        return {"status": "analyzed", "analysis": analysis, ...}
    else:
        # Fallback: Simple pattern matching
        return self._simple_analyze(failures)
```

### Phase 59.3: The Fixer

```python
async def _apply_fix(
    self,
    context: MissionContext,
    analysis: Dict[str, Any]
) -> bool:
    """
    Phase 59.3: The Fixer - Generate and apply code fixes.

    Uses LLM to generate fix plan, then applies changes:
    - File path identification
    - Old code pattern
    - New code replacement
    """
    fix_plan = await self._llm_provider.generate_fix(
        analysis["analysis"],
        context.target_path
    )

    for file_change in fix_plan.get("changes", []):
        await self._apply_file_change(file_path, file_change)

    return True
```

### Phase 59.4: The Verifier

```python
async def _verify_fix(self, context: MissionContext) -> bool:
    """Re-run tests to verify the fix worked."""
    return await self._run_tests(context)
```

### Phase 59.5: The Reflector

```python
async def _reflect(self, context: MissionContext) -> None:
    """
    Phase 59.5: The Reflector - Log learnings for future improvement.

    Stores mission experience in vector store for:
    - Future mission context
    - Pattern recognition
    - Learning from failures
    """
    reflection = {
        "mission_id": context.mission_id,
        "target": str(context.target_path),
        "iterations": context.iterations,
        "passed": all_tests_passed,
        "failures": [f.name for f in failed_tests],
        "timestamp": datetime.now().isoformat(),
    }

    await vm.add(
        documents=[str(reflection)],
        ids=[f"mission-{context.mission_id}"],
        metadatas=[{"type": "meta_agent_reflection", "success": passed}],
    )
```

## Test Scenario: broken_math.py

The Meta-Agent is tested with a deliberately broken math library:

```python
# broken_math.py (intentionally buggy)
def add(a: int, b: int) -> int:
    return a - b  # BUG: Should be a + b

def is_even(n: int) -> bool:
    return n % 2 == 1  # BUG: Should be == 0
```

### Test Results

```
Initial state: 2 failed, 2 passed
Meta-Agent:    2 iterations, 4 passed

Bugs Fixed:
1. add():    a - b -> a + b
2. is_even(): n % 2 == 1 -> n % 2 == 0
```

## Data Flow

```
1. User calls: await meta.run_mission("Fix broken math", ...)
   |
   v
2. TDD Cycle starts (max 5 iterations)
   |
   +---> _run_tests(): Execute pytest, capture results
   |     |
   |     v
   |     Parse output -> List[TestResult]
   |     |
   |     v
   |     All passed? -> YES: Go to Reflect
   |     |
   |     NO (first 4 iterations)
   |     |
   |     +---> _analyze_failures(): Identify root cause
   |     |     |
   |     |     v
   |     |     _apply_fix(): Generate and apply code changes
   |     |     |
   |     |     v
   |     +---- Go to next iteration (verify fix)
   |
   v
3. _reflect(): Store learnings in omni-vector
   |
   v
4. Return MissionContext with all details
```

## Benefits

| Benefit                    | Description                                       |
| -------------------------- | ------------------------------------------------- |
| **Autonomous Debugging**   | Agent can fix issues without human intervention   |
| **Self-Healing**           | Code automatically repairs itself when tests fail |
| **Continuous Improvement** | System gets better over time through reflection   |
| **Cost Reduction**         | Fewer human hours needed for routine fixes        |
| **Pattern Learning**       | Same bugs don't repeat (stored in vector store)   |

## Files Modified

| File                         | Change                                                     |
| ---------------------------- | ---------------------------------------------------------- |
| `agent/core/meta_agent.py`   | New: MetaAgent class with TDD loop                         |
| `scripts/test_meta_agent.py` | New: Self-healing test script with broken_math.py scenario |

## Integration Points

### With Phase 44 (Experiential Agent)

```
Mission Reflection -> Vector Store
        |
        v
Phase 44: get_skill_lessons() -> Future missions
```

### With omni-vector (Phase 57)

```
Meta-Agent Reflections stored in: omni-vector (LanceDB)
Queryable by: future Meta-Agent missions
```

## Future Enhancements

- **Auto-Harvesting**: Automatically trigger Meta-Agent on CI failures
- **Multi-Language Fixes**: Support more than Python (Rust, TypeScript, etc.)
- **Context-Aware Fixing**: Use project context for better fix suggestions
- **Confidence Scoring**: Only apply fixes above certain confidence threshold
- **Human Escalation**: Fall back to human when fix confidence is low
- **Git Integration**: Create branches, PRs for suggested fixes
- **Cost Tracking**: Monitor API usage for LLM-based fixes
