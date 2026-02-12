# Memory Module Architecture

> Project Memory System - ADR-based Long-term Storage
> **Status**: Active | **Version**: v2.0.0 | **Date**: 2026-01-30

## Overview

The `omni.foundation.services.memory` module provides long-term memory storage for project decisions, tasks, and context using the ADR (Architectural Decision Record) pattern.

## Architecture

```
omni.foundation.services.memory/
├── __init__.py                    # Package entry point, public API exports
├── base.py                        # Public API exports
├── core/
│   ├── __init__.py               # Core module exports
│   ├── interface.py              # Abstract interfaces and data types
│   ├── project_memory.py         # ProjectMemory main class
│   └── utils.py                  # Shared utility functions
└── stores/
    ├── __init__.py               # Stores module exports
    └── lancedb.py                # LanceDB storage implementation
```

## Module Responsibilities

| Module                   | Responsibility                                                                |
| ------------------------ | ----------------------------------------------------------------------------- |
| `core/interface.py`      | Defines `MemoryStore` abstract interfaces and `Decision`, `Task` data classes |
| `core/project_memory.py` | `ProjectMemory` main class, LanceDB-backed operations                         |
| `core/utils.py`          | `format_decision`, `parse_decision` utility functions                         |
| `stores/lancedb.py`      | LanceDB storage implementation                                                |

## Quick Start

```python
from omni.foundation.services.memory import (
    ProjectMemory,
    STORAGE_MODE_LANCE,
)

# LanceDB mode (default and only backend)
memory = ProjectMemory()

# Explicit constant remains available for API clarity
assert STORAGE_MODE_LANCE == "lance"
```

## Core Interfaces

### MemoryStore (Abstract)

Unified interface for all memory operations:

```python
from omni.foundation.services.memory.core.interface import MemoryStore

class MemoryStore(DecisionStore, TaskStore, ContextStore, ActiveContextStore):
    def add_decision(...) -> dict: ...
    def list_decisions() -> list: ...
    def get_decision(title: str) -> dict | None: ...
    def delete_decision(title: str) -> bool: ...

    def add_task(...) -> dict: ...
    def list_tasks(status: str | None = None) -> list: ...
    def get_task(title: str) -> dict | None: ...
    def delete_task(title: str) -> bool: ...

    def save_context(data: dict | None = None) -> dict: ...
    def get_latest_context() -> dict | None: ...

    def update_status(...) -> dict: ...
    def get_status() -> str: ...
    def log_scratchpad(entry: str, source: str = "Note") -> dict: ...

    def migrate_from_file(source_dir: Path) -> dict: ...
    def get_storage_mode() -> str: ...
```

## Data Types

### Decision

```python
@dataclass
class Decision:
    id: str
    title: str
    content: str
    problem: str
    solution: str
    rationale: str
    status: str  # open, accepted, rejected, deprecated
    author: str
    date: str
    metadata: dict
```

### Task

```python
@dataclass
class Task:
    id: str
    title: str
    content: str
    status: str  # pending, in_progress, completed, blocked
    assignee: str
    created: str
    metadata: dict
```

## Usage Examples

### Managing Decisions

```python
from omni.foundation.services.memory import ProjectMemory

memory = ProjectMemory()

# Add a decision
memory.add_decision(
    title="Use LanceDB for Memory Storage",
    problem="File-based storage is slow for large datasets",
    solution="Migrate to LanceDB for better performance",
    rationale="LanceDB provides efficient structured data storage with ACID guarantees",
    status="accepted",
)

# List all decisions
decisions = memory.list_decisions()
for d in decisions:
    print(f"- {d['title']} [{d['status']}]")

# Get specific decision
decision = memory.get_decision("Use LanceDB for Memory Storage")
```

### Managing Tasks

```python
from omni.foundation.services.memory import ProjectMemory

memory = ProjectMemory()

# Add a task
memory.add_task(
    title="Implement Memory Migration",
    content="Create migration script from markdown exports to LanceDB",
    status="pending",
    assignee="Claude",
)

# List tasks by status
pending = memory.list_tasks(status="pending")
in_progress = memory.list_tasks(status="in_progress")
all_tasks = memory.list_tasks()
```

### Context Management

```python
from omni.foundation.services.memory import ProjectMemory

memory = ProjectMemory()

# Save context snapshot
memory.save_context({
    "files_tracked": 100,
    "active_skills": ["git", "memory"],
})

# Get latest context
context = memory.get_latest_context()

# Update project status
memory.update_status(
    phase="implementation",
    focus="writing tests",
    blockers="None",
    sentiment="Neutral",
)

# Get current status
status = memory.get_status()

# Log to scratchpad
memory.log_scratchpad("Running unit tests", source="System")
```

### Migration from Markdown Exports

```python
from omni.foundation.services.memory import ProjectMemory
from pathlib import Path

# Create memory store
memory = ProjectMemory(dir_path=Path(".cache/memory"))

# Import from legacy markdown directory layout (decisions/*.md, tasks/*.md)
result = memory.migrate_from_file(Path(".cache/memory"))
print(f"Migrated: {result['decisions']} decisions, {result['tasks']} tasks")
```

## Storage Backend

### LanceDB

- **Location**: `.cache/omni-vector/memory.lance`
- **Tables**: `decisions`, `tasks`, `context`, `active_context`
- **Performance**: Fast structured data queries with ACID guarantees

## Comparison: Memory vs Knowledge vs Episodic

| Aspect      | Memory (Project)              | Knowledge               | Episodic                |
| ----------- | ----------------------------- | ----------------------- | ----------------------- |
| **Source**  | Project decisions/tasks       | Documentation files     | Agent experiences       |
| **Storage** | LanceDB (structured)          | File system (markdown)  | LanceDB (vector)        |
| **Query**   | CRUD operations               | Keyword/semantic search | Semantic similarity     |
| **Purpose** | "What decisions did we make?" | "What are the rules?"   | "What happened before?" |
| **Update**  | Manual                        | Pre-indexed             | Real-time (per task)    |

## Related Documentation

- [Hippocampus](../human/architecture/hippocampus.md) - Memory Interface
- [Memory Mesh](../human/architecture/memory-mesh.md) - Episodic Memory for Agents
- [Knowledge Matrix](../human/architecture/knowledge-matrix.md) - Documentation RAG
