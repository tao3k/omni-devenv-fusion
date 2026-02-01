# Skill Evolution System

> Self-Improvement System for Omni-Copilot
> **Status**: Implemented | **Version**: v1.0.0 | **Date**: 2026-01-30

## Overview

The Skill Evolution system implements the **Self-Improvement Loop** from OS-Copilot/Voyager. It observes successful OmniCell execution traces and converts them into reusable Expert Skills, enabling the system to evolve from Generalist to Expert over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Skill Evolution Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌────────────────────┐     ┌─────────────────┐    │
│  │   OmniCell      │────▶│  UniversalSolver   │────▶│ TraceCollector  │    │
│  │   (Generalist)  │     │  (Integration)     │     │  (Recorder)     │    │
│  └─────────────────┘     └────────────────────┘     └────────┬────────┘    │
│                                                               │              │
│                                                               ▼              │
│  ┌─────────────────┐     ┌────────────────────┐     ┌─────────────────┐    │
│  │   Router        │◀────│  EvolutionManager  │◀────│  Harvester      │    │
│  │   (Dispatcher)  │     │  (Orchestrator)    │     │  (Analyzer)     │    │
│  └────────┬────────┘     └────────────────────┘     └────────┬────────┘    │
│           │                                                    │             │
│           ▼                                                    ▼             │
│  ┌─────────────────┐     ┌────────────────────┐     ┌─────────────────┐    │
│  │ Skill Registry  │◀────│  SkillFactory      │◀────│  ImmuneSystem   │    │
│  │  (Expert)       │     │  (Generator)       │     │  (Validator)    │    │
│  └─────────────────┘     └────────────────────┘     └─────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
packages/python/agent/src/omni/agent/core/evolution/
├── __init__.py              # Exports all evolution components
├── tracer.py                # Execution trace collection
├── universal_solver.py      # Core → Evolution integration bridge
├── manager.py               # Orchestration layer
├── harvester.py             # Session analysis & skill extraction
├── factory.py               # Automated skill synthesis
└── immune/                  # Security defense (Rust integration)
```

## Key Components

### 1. TraceCollector (`tracer.py`)

Records execution traces from OmniCell.

```python
from omni.agent.core.evolution.tracer import TraceCollector, ExecutionTrace

# Record an execution trace
trace_id = await collector.record(
    task_id="task_123",
    task_description="Rename files",
    commands=["ls *.txt", "for f in *.txt; do mv $f ${f%.txt}.md; done"],
    outputs=["file1.txt", "2 files renamed"],
    success=True,
    duration_ms=150.5,
)

# Retrieve traces
trace = await collector.get_trace(trace_id)
traces = await collector.get_traces_by_task("rename")
recent = await collector.get_recent_traces(limit=10)
```

### 2. UniversalSolver (`universal_solver.py`)

Integration bridge between Core OmniCell and Evolution system.

```python
from omni.agent.core.evolution.universal_solver import UniversalSolver, SolverResult

solver = UniversalSolver(trace_collector=tracer)

# Execute task and record trace
result = await solver.solve(
    task="list all files",
    context={"working_dir": "/project"},
    record_trace=True,
)

print(result.status)  # SolverStatus.SUCCESS
print(result.trace_id)  # "trace_id_for_harvester"
```

### 3. EvolutionManager (`manager.py`)

Orchestrates the complete crystallization workflow.

```python
from omni.agent.core.evolution.manager import EvolutionManager, EvolutionConfig

config = EvolutionConfig(
    min_trace_frequency=3,      # Min executions before harvesting
    min_success_rate=0.8,       # Min success rate for crystallization
    auto_crystallize=False,     # Require approval
    dry_run=True,               # Simulate without creating skills
)

manager = EvolutionManager(config=config)

# Check for crystallization candidates
candidates = await manager.check_crystallization()

# Run complete evolution cycle
results = await manager.run_evolution_cycle()

# Get system status
status = await manager.get_evolution_status()
```

## Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Complete Evolution Workflow                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. OmniCell Executes                                                        │
│     ↓                                                                        │
│  2. UniversalSolver records trace to TraceCollector                         │
│     ↓                                                                        │
│  3. EvolutionManager.check_crystallization()                                │
│     ↓                                                                        │
│  4. If candidate meets thresholds:                                          │
│     ├── Harvester.analyze_task() → Extract skill requirements              │
│     ├── SkillFactory.create_skill() → Generate skill code                  │
│     ├── ImmuneSystem.validate_static() → Security check                    │
│     └── Register new skill (or await approval)                             │
│     ↓                                                                        │
│  5. Router now routes to Expert instead of Generalist                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration

```yaml
evolution:
  enabled: true
  trace_dir: "{PRJ_DATA}/evolution/traces"

  # Thresholds
  min_trace_frequency: 3 # Min executions before crystallization
  min_success_rate: 0.8 # Min success rate threshold
  max_trace_age_hours: 24 # Only consider recent traces

  # Scheduling
  check_interval_seconds: 300 # How often to check for crystallization
  batch_size: 10 # Traces to process per batch

  # Feature flags
  auto_crystallize: false # Require human approval
  dry_run: false # Simulate mode
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
    """
    result = await nu.run(f"for f in (glob '{pattern}') {{ mv $f ($f | str replace -r '\\.{old_ext}$' '.{new_ext}') }}")
    return {"renamed": len(result), "files": result}
```

### Router Behavior

```
Before: User: "rename txt to md" → OmniCell (Generalist)
After:  User: "rename txt to md" → batch_rename (Expert)
```

## Testing

```bash
# Run all evolution module tests
uv run pytest packages/python/agent/tests/units/test_evolution_*.py -v

# Test summary
# - test_evolution_tracer.py: 13 tests (TraceCollector)
# - test_evolution_solver.py: 19 tests (UniversalSolver)
# - test_evolution_manager.py: 19 tests (EvolutionManager)
# Total: 51 tests
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
- [ ] Integration with Knowledge Base for context-aware crystallization

## Related Documentation

- [OmniCell](omni-cell.md) - Generalist execution engine
- [Skill Standard](../../reference/skill-standard.md) - Skill interface definition
- [Router](../router.md) - Skill routing system
- [Memory Mesh](memory-mesh.md) - Episodic memory integration
