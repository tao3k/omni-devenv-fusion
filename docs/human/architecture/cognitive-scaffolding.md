# Cognitive Scaffolding

> Based on Confucius Code Agent (CCA) Paper Principles
> **Status**: Active | **Version**: v1.0 | **Date**: 2026-01-13

## Overview

Cognitive Scaffolding is the cognitive layer of the Trinity Architecture, providing agents with the capability to handle long-horizon tasks. It implements the Planner-Executor-Reviewer triad based on CCA paper principles.

## Core Philosophy

| Component    | CCA Concept                 | Purpose                                |
| ------------ | --------------------------- | -------------------------------------- |
| **Planner**  | Task Decomposition          | Break complex goals into ordered Tasks |
| **Executor** | Step-by-Step                | Execute Tasks, report results          |
| **Reviewer** | Reflexion Loop              | Evaluate progress, detect drift        |
| **Memory**   | Hierarchical Working Memory | Scratchpad → Episodes → Knowledge      |

## Architecture: Planner & Executor

### Workflow

```
User Input → Router → [Confidence < 0.8?]
                           ↓ Yes
                    Planner (Decompose → Task List)
                           ↓
                    Executor (Loop: Execute Task → Review → Next)
                           ↓
                    Completion / Re-plan
```

### Fast Path (Single-step Tasks)

```
User Input → Router → [Confidence >= 0.8?] → Tool (Fast, single-step)
```

## Task Data Structure

```python
# agent/core/planner/schemas.py

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class Task(BaseModel):
    """A single unit of work in a plan."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: list[str] = []  # Task IDs this depends on
    tool_calls: list[dict] = []   # Planned tool invocations
    actual_results: list[str] = []  # Execution results
    reflection: Optional[str] = None  # Reviewer's assessment
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class Plan(BaseModel):
    """A hierarchical plan containing multiple tasks."""
    id: str
    goal: str  # Original user request
    tasks: list[Task]
    current_task_index: int = 0
    total_episodes: int = 0  # For memory compression
    status: str = "active"  # active, completed, abandoned
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

## Hierarchical Memory

### Level 1: Scratchpad (Short-term)

- Current Task's detailed Tool Outputs
- FIFO, 4k-8k tokens max

### Level 2: Episodic Summary (Medium-term)

- Generated when Task completes
- Stored in SQLite/JSONL
- Injected into future System Prompts

```python
# Example Episode Summary
"""
Episode 3 (Task: Fix auth bug in login.py):
- Attempted: Direct sed replacement of auth check
- Failed: Syntax error in replacement pattern
- Pivot: Used code_tools.structural_replace()
- Result: Successfully fixed authentication flow
- Lesson: Pattern-based replacement is safer for nested conditions
"""
```

### Level 3: Knowledge Graph (Long-term)

- Vectorized Episode Summaries
- Retrieved by `Wisdom Injection` for similar tasks

## API Reference

### Planner

```python
from agent.core.planner import Planner, Plan, Task

# Decompose a goal into tasks
planner = Planner()
plan = await planner.decompose(
    goal="Refactor the authentication module",
    context="Current codebase has auth issues in login.py"
)

# Get next task to execute
task = plan.get_next_task()
```

### Executor

```python
from agent.core.planner import Executor

executor = Executor()
result = await executor.execute_task(
    task=task,
    tools=available_tools,
    context=current_context
)

# Result contains: output, reflection, next_action
```

### Memory

```python
from agent.core.planner import EpisodeMemory

memory = EpisodeMemory()

# Store completed episode
await memory.store_episode(
    plan_id=plan.id,
    task_id=task.id,
    summary="Episode summary text",
    metrics={"tokens": 1200, "duration": 5.2}
)

# Retrieve relevant episodes
episodes = await memory.retrieve_relevant(
    query="auth bug fix patterns",
    limit=3
)
```

## Integration Points

### Hybrid Router Integration

```python
# When confidence < 0.8, route to Planner
if confidence < 0.8:
    return RouterAction.PLAN, plan_id
```

### Conductor Integration

```python
# Update context with episodic memory
context = conductor._build_cca_context(
    user_input,
    include_episodes=True  # New flag
)
```

## Related Documentation

- [Trinity Architecture](../explanation/trinity-architecture.md)
- [Memory Mesh](./memory-mesh.md)
- [LangGraph Workflow Guide](../llm/langgraph-workflow-guide.md)
