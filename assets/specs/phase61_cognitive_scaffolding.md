# Phase 61: The Cognitive Scaffolding (认知脚手架)

> Based on Confucius Code Agent (CCA) Paper Principles
> Version: v1.0 | 2026-01-13

## Overview

Phase 60.5 gave us Rust acceleration and Hybrid Routing. Phase 61 introduces **Cognitive Architecture** - the "prefrontal cortex" for handling long-horizon tasks.

### Core Philosophy

| Component    | CCA Concept                 | Purpose                                |
| ------------ | --------------------------- | -------------------------------------- |
| **Planner**  | Task Decomposition          | Break complex goals into ordered Tasks |
| **Executor** | Step-by-Step                | Execute Tasks, report results          |
| **Reviewer** | Reflexion Loop              | Evaluate progress, detect drift        |
| **Memory**   | Hierarchical Working Memory | Scratchpad → Episodes → Knowledge      |

---

## 1. Architecture: Planner & Executor

### Current State

```
User Input → Router → Tool (Fast, single-step)
```

### Target State

```
User Input → Router → [Confidence < 0.8?]
                           ↓ Yes
                    Planner (Decompose → Task List)
                           ↓
                    Executor (Loop: Execute Task → Review → Next)
                           ↓
                    Completion / Re-plan
```

### Task Data Structure

```python
# agent/core/planner/schemas.py
from enum import Enum
from pydantic import BaseModel
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

---

## 2. Hierarchical Memory

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
- Pivot: Used structural_editing.replace_node()
- Result: Successfully fixed authentication flow
- Lesson: Pattern-based replacement is safer for nested conditions
"""
```

### Level 3: Knowledge Graph (Long-term)

- Vectorized Episode Summaries
- Retrieved by `Wisdom Injection` for similar tasks

---

## 3. Implementation Roadmap

### Step 1: Core Schemas (Day 1)

- [ ] `agent/core/planner/schemas.py` - Task, Plan, Episode
- [ ] `agent/core/planner/task_store.py` - SQLite storage

### Step 2: Planner Module (Day 2-3)

- [ ] `agent/core/planner/decomposer.py` - LLM-based decomposition
- [ ] `agent/core/planner/prompts.py` - Decomposition prompt templates
- [ ] `agent/core/planner/planner.py` - Main Planner class

### Step 3: Executor & Reviewer (Day 4-5)

- [ ] `agent/core/planner/executor.py` - Task execution loop
- [ ] `agent/core/planner/reviewer.py` - Reflexion/evaluation logic

### Step 4: Memory Integration (Day 6-7)

- [ ] Episode generation in Executor
- [ ] Vector storage integration with Librarian
- [ ] Prompt injection in ContextOrchestrator

### Step 5: Observability (Day 8)

- [ ] Structured tracing (OpenTelemetry/JSONL)
- [ ] `omni trace view` command

---

## 4. API Reference

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

---

## 5. Integration Points

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

---

## 6. Testing Strategy

| Component     | Test Type          | Examples                                           |
| ------------- | ------------------ | -------------------------------------------------- |
| Task Schema   | Unit               | Valid/invalid task creation, dependency resolution |
| Decomposition | Integration        | Goal → Plan conversion, edge cases                 |
| Executor      | E2E                | Full task execution, error recovery                |
| Memory        | Unit + Integration | Episode storage, vector retrieval                  |

---

## Files to Create/Modify

### New Files

```
agent/core/planner/
├── __init__.py
├── schemas.py          # Task, Plan, Episode
├── task_store.py       # SQLite storage
├── decomposer.py       # LLM-based decomposition
├── prompts.py          # Prompt templates
├── planner.py          # Main Planner class
├── executor.py         # Task execution
├── reviewer.py         # Reflexion logic
└── tracer.py           # Structured tracing

agent/core/omni_agent.py  # Dual-loop architecture
```

### Modified Files

```
agent/core/router.py     # Confidence threshold routing
agent/core/orchestrator.py  # Episode injection
agent/tests/
├── unit/test_planner_schemas.py
└── integration/test_planner.py
```
