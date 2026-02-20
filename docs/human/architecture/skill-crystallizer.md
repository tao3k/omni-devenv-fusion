# SkillCrystallizer - Skill Evolution System

> Converts successful OmniCell executions into reusable Expert Skills
> **Status**: Planning | **Version**: v1.0.0 | **Date**: 2026-01-30

## Overview

The `SkillCrystallizer` implements the **Self-Improvement** loop from OS-Copilot/Voyager. It observes successful OmniCell execution traces and converts them into reusable Expert Skills, enabling the system to evolve from Generalist to Expert over time.

## Inspiration

### OS-Copilot (FRIDAY Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│                    OS-Copilot Self-Improvement Loop             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Observe execution                                           │
│       ↓                                                         │
│  2. Detect pattern (e.g., "batch rename files" occurs 3x)      │
│       ↓                                                         │
│  3. Generate Python script for the pattern                      │
│       ↓                                                         │
│  4. Register as new Tool                                        │
│       ↓                                                         │
│  5. Router now routes to Expert instead of Generalist           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Voyager (Nvidia)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Voyager Automatic Curriculum                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Explore → Fail → Generate Code → Store Skill → Success        │
│       ↑________________________________________________|        │
│            (闭环 continuously improves)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture

```
packages/python/agent/src/omni/agent/core/evolution/
├── __init__.py
├── crystallizer.py       # Main SkillCrystallizer class
├── tracer.py             # Execution trace collector
├── analyzer.py           # Pattern detection and analysis
├── generator.py          # Code generation from traces
└── registry.py           # Skill registration and management
```

## Module Responsibilities

| Module            | Responsibility                                   |
| ----------------- | ------------------------------------------------ |
| `tracer.py`       | Collect and store execution traces from OmniCell |
| `analyzer.py`     | Detect patterns in traces (repetitive tasks)     |
| `generator.py`    | Convert trace to clean, reusable code            |
| `registry.py`     | Register new skills and update skill index       |
| `crystallizer.py` | Orchestrate the evolution loop                   |

## Workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SkillCrystallizer Workflow                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐                                                 │
│  │ OmniCell Executes │ ← sys_exec trace with timestamps             │
│  └────────┬────────┘                                                 │
│           ↓                                                          │
│  ┌─────────────────┐                                                 │
│  │ Trace Collector │ ← Store: task_id, commands, output, success    │
│  └────────┬────────┘                                                 │
│           ↓                                                          │
│  ┌─────────────────┐                                                 │
│  │ Pattern Detector │ ← Check for: frequency, complexity, success   │
│  └────────┬────────┘                                                 │
│           ↓     ↓                                                    │
│      Skip    ┌──┴────────┐                                           │
│               ↓          ↓                                           │
│        No Pattern   ┌─────────────────┐                              │
│                      │ Pattern Found! │                              │
│                      └────────┬────────┘                              │
│                               ↓                                      │
│                      ┌─────────────────┐                              │
│                      │ Code Generator  │ ← LLM converts trace        │
│                      └────────┬────────┘                              │
│                               ↓                                      │
│                      ┌─────────────────┐                              │
│                      │ Skill Registry  │ ← Save to learned_skills    │
│                      └────────┬────────┘                              │
│                               ↓                                      │
│                      ┌─────────────────┐                              │
│                      │ Reindex Router  │ ← Router now uses Expert    │
│                      └─────────────────┘                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Key Components

### TraceCollector

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class ExecutionTrace:
    """Represents a single execution trace."""
    task_id: str
    task_description: str
    commands: List[str]
    outputs: List[str]
    success: bool
    duration_ms: float
    timestamp: datetime
    metadata: dict

@dataclass
class TracePattern:
    """Detected pattern in execution traces."""
    pattern_type: str  # "repetitive", "complex", "novel"
    command_sequence: List[str]
    frequency: int
    success_rate: float
    task_category: str
```

### SkillCrystallizer

```python
class SkillCrystallizer:
    """
    Implements the Self-Improvement loop.
    Converts successful OmniCell executions into reusable Expert Skills.
    """

    def __init__(
        self,
        trace_dir: Path,
        learned_skills_dir: Path,
        min_frequency: int = 3,
        min_complexity: int = 5,
    ):
        """
        Args:
            trace_dir: Directory to store execution traces
            learned_skills_dir: Directory for crystallized skills
            min_frequency: Minimum occurrences to trigger crystallization
            min_complexity: Minimum command count for complex task
        """
        self.tracer = TraceCollector(trace_dir)
        self.analyzer = PatternAnalyzer()
        self.generator = CodeGenerator()
        self.registry = SkillRegistry(learned_skills_dir)
        self.min_frequency = min_frequency
        self.min_complexity = min_complexity

    async def record_execution(
        self,
        task_description: str,
        commands: List[str],
        outputs: List[str],
        success: bool,
        duration_ms: float,
    ) -> str:
        """
        Record an execution trace.

        Returns:
            trace_id for later reference
        """
        trace_id = await self.tracer.record(
            task_description=task_description,
            commands=commands,
            outputs=outputs,
            success=success,
            duration_ms=duration_ms,
        )

        # Check if crystallization should trigger
        if success:
            await self._maybe_crystallize(task_description)

        return trace_id

    async def _maybe_crystallize(self, task_description: str) -> Optional[dict]:
        """Check if pattern exists and crystallize if threshold met."""
        traces = await self.tracer.get_traces_by_task(task_description)

        if len(traces) < self.min_frequency:
            return None

        pattern = self.analyzer.detect_pattern(traces)
        if not pattern:
            return None

        # Check complexity threshold
        total_commands = sum(len(t.commands) for t in traces)
        avg_complexity = total_commands / len(traces)

        if avg_complexity < self.min_complexity:
            return None

        return await self.crystallize(pattern)

    async def crystallize(self, pattern: TracePattern) -> dict:
        """
        Convert pattern to a new skill.

        Returns:
            Dict with new skill metadata
        """
        # Generate code from pattern
        skill_code = await self.generator.generate(
            pattern=pattern,
            template="skill",
        )

        # Register skill
        result = await self.registry.register(
            name=pattern.task_category,
            code=skill_code,
            metadata={
                "source": "crystallized",
                "pattern_type": pattern.pattern_type,
                "frequency": pattern.frequency,
                "success_rate": pattern.success_rate,
            },
        )

        # Trigger reindex
        await self.registry.trigger_reindex()

        return result
```

### CodeGenerator

```python
class CodeGenerator:
    """Generates clean, reusable skill code from execution traces."""

    async def generate(
        self,
        pattern: TracePattern,
        template: str = "skill",
    ) -> str:
        """
        Generate skill code from pattern.

        Args:
            pattern: Detected pattern with command sequences
            template: Template type ("skill" | "command" | "tool")

        Returns:
            Generated Python code as string
        """
        prompt = f"""
        Convert the following command sequence into a clean, reusable Python skill.

        Pattern Type: {pattern.pattern_type}
        Task Category: {pattern.task_category}
        Frequency: {pattern.frequency} occurrences
        Success Rate: {pattern.success_rate:.2f}

        Commands (aggregated):
        {chr(10).join(pattern.command_sequence[:10])}

        Requirements:
        1. Use @skill_command decorator
        2. Add proper docstring
        3. Include error handling
        4. Make it idempotent
        5. Follow project conventions (snake_case, type hints)

        Output: Complete Python file content (no markdown)
        """

        response = await self.llm.complete(prompt)
        return response.content
```

## Storage Locations

| Data Type           | Location                           |
| ------------------- | ---------------------------------- |
| Execution Traces    | `PRJ_DATA/evolution/traces/`       |
| Crystallized Skills | `assets/skills/learned_skills/`    |
| Pattern Cache       | `PRJ_DATA/evolution/patterns.json` |

## Configuration

```yaml
evolution:
  enabled: true
  trace_dir: "{PRJ_DATA}/evolution/traces"
  learned_skills_dir: "{ASSETS}/skills/learned_skills"
  min_frequency: 3 # Minimum occurrences to crystallize
  min_complexity: 5 # Minimum commands for complex task
  max_traces_stored: 1000 # Prune old traces
  crystallization_interval: 3600 # Seconds between checks
```

## Integration Points

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Integration Points                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐      │
│  │   OmniCell   │────▶│  SkillCrystallizer│────▶│   Router     │      │
│  │  (Generalist)│     │   (Evolution)     │     │  (Dispatcher)│      │
│  └──────────────┘     └──────────────────┘     └──────────────┘      │
│         │                     │                      │                │
│         │  Execution Trace    │                      │                │
│         │                     │  New Skill           │                │
│         │                     │  Registered          │                │
│         │                     │                      │                │
│         ▼                     ▼                      ▼                │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐      │
│  │  Agent Core  │     │  Skill Index     │     │   Librarian  │      │
│  └──────────────┘     └──────────────────┘     └──────────────┘      │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## Example: Batch Rename Files

### Before (Generalist Mode)

```
User: Rename all .txt files to .md
OmniCell: ls *.txt → for f in *.txt; do mv "$f" "${f%.txt}.md"; done
Result: ✅ Success
Trace: ["ls *.txt", "for f in *.txt; do mv ..."] × 3
```

### After (Crystallized Expert)

```python
# assets/skills/learned_skills/batch_rename.py
@skill_command(autowire=True)
async def batch_rename(
    pattern: str = Query(..., description="File pattern (e.g., *.txt)"),
    old_ext: str = Query(..., description="Old extension"),
    new_ext: str = Query(..., description="New extension"),
):
    """
    Rename files matching pattern from old_ext to new_ext.

    Example: batch_rename("*.txt", "txt", "md")
    """
    result = await nu.run(f"for f in (glob '{pattern}') {{ mv $f ($f | str replace -r '\\.{old_ext}$' '.{new_ext}') }}")
    return {"renamed": len(result), "files": result}
```

### Router Behavior

```
Before: User: "rename txt to md" → OmniCell (Generalist)
After:  User: "rename txt to md" → batch_rename (Expert)
```

## Metrics & Observability

| Metric                       | Description                               |
| ---------------------------- | ----------------------------------------- |
| `crystallization_triggers`   | Number of times crystallization triggered |
| `patterns_detected`          | Unique patterns found                     |
| `skills_crystallized`        | New skills created                        |
| `crystallization_latency_ms` | Time to crystallize a skill               |
| `success_rate_improvement`   | Before/after task success rate            |

## Future Enhancements

- [ ] LLM-based pattern naming
- [ ] Skill versioning and rollback
- [ ] Cross-session consolidation
- [ ] User approval workflow before crystallization
- [ ] Skill quality scoring
- [ ] Automatic skill documentation generation

## Related Documentation

- [OmniCell](../omni-cell.md) - Generalist execution engine
- [Skill Standard](../../human/architecture/skill-standard.md) - Skill interface definition
- [Router](../../architecture/router.md) - Skill routing system
- [Memory Mesh](memory-mesh.md) - Episodic memory integration
