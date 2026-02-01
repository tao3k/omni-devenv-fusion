"""
nodes.py - Prefrontal Cortex Task Graph Structures

Defines TaskNode, TaskGroup, and TaskGraph for parallel task orchestration.

Integration: CortexOrchestrator → UniversalSolver → OmniCell
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    BLOCKED = "blocked"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels."""

    CRITICAL = 0  # Must execute first
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class TaskNode:
    """
    A single task node in the execution graph.

    Attributes:
        id: Unique task identifier
        description: Human-readable task description
        command: The command to execute
        dependencies: List of task IDs that must complete before this task
        status: Current execution status
        priority: Execution priority (lower = higher priority)
        timeout_seconds: Maximum execution time
        retry_count: Number of retries remaining
        max_retries: Maximum allowed retries
        result: Execution result when complete
        metadata: Additional task metadata (affected files, patterns, etc.)
        created_at: Task creation timestamp
        started_at: When task started execution
        completed_at: When task completed
        executor_id: ID of the executor handling this task
    """

    id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    description: str = ""
    command: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    timeout_seconds: int = 300  # 5 minutes default
    retry_count: int = 0
    max_retries: int = 2
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    executor_id: str | None = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, TaskNode):
            return self.id == other.id
        return False

    @property
    def is_blocked(self) -> bool:
        """Check if task is blocked by unfinished dependencies."""
        return self.status == TaskStatus.BLOCKED

    @property
    def is_complete(self) -> bool:
        """Check if task has finished (success or failed)."""
        return self.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def duration_ms(self) -> float | None:
        """Calculate execution duration in milliseconds."""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds() * 1000

    def add_dependency(self, task_id: str) -> None:
        """Add a dependency on another task."""
        if task_id not in self.dependencies:
            self.dependencies.append(task_id)

    def can_execute(self, completed_tasks: set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep_id in completed_tasks for dep_id in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "command": self.command,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskNode":
        """Deserialize from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        return cls(**data)


@dataclass
class TaskGroup:
    """
    A group of tasks that can execute in parallel.

    Attributes:
        id: Unique group identifier
        name: Human-readable group name
        tasks: List of tasks in this group
        depends_on: Groups that must complete before this group
        execute_in_parallel: Whether tasks should run concurrently
        max_concurrent: Maximum concurrent executions (0 = unlimited)
        barrier: Sync point for all tasks in group
    """

    id: str = field(default_factory=lambda: f"group_{uuid4().hex[:8]}")
    name: str = ""
    tasks: list[TaskNode] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # Group IDs
    execute_in_parallel: bool = True
    max_concurrent: int = 0  # 0 = unlimited
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_task(self, task: TaskNode) -> None:
        """Add a task to this group."""
        self.tasks.append(task)

    def get_ready_tasks(self, completed_tasks: set[str]) -> list[TaskNode]:
        """Get tasks that are ready to execute."""
        if self.execute_in_parallel:
            # Return all ready tasks
            return [
                t
                for t in self.tasks
                if t.status == TaskStatus.PENDING and t.can_execute(completed_tasks)
            ]
        else:
            # Return first ready task (sequential execution)
            for task in self.tasks:
                if task.status == TaskStatus.PENDING and task.can_execute(completed_tasks):
                    return [task]
            return []

    @property
    def is_complete(self) -> bool:
        """Check if all tasks in group are complete."""
        return all(t.is_complete for t in self.tasks)

    @property
    def has_failed(self) -> bool:
        """Check if any task in group has failed."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "task_ids": [t.id for t in self.tasks],
            "depends_on": self.depends_on,
            "execute_in_parallel": self.execute_in_parallel,
            "max_concurrent": self.max_concurrent,
            "is_complete": self.is_complete,
            "metadata": self.metadata,
        }


class TaskGraph:
    """
    A directed acyclic graph (DAG) of task groups.

    Supports:
    - Topological sorting for execution order
    - Dependency resolution
    - Parallel group execution
    - Cycle detection
    """

    def __init__(self, name: str = ""):
        self.name = name
        self.groups: dict[str, TaskGroup] = {}
        self.all_tasks: dict[str, TaskNode] = {}
        self.created_at = datetime.now()

    def add_group(self, group: TaskGroup) -> None:
        """Add a task group to the graph."""
        self.groups[group.id] = group
        for task in group.tasks:
            self.all_tasks[task.id] = task

    def add_task(self, task: TaskNode, group_id: str | None = None) -> None:
        """Add a task, optionally creating a default group."""
        self.all_tasks[task.id] = task
        if group_id:
            if group_id not in self.groups:
                self.groups[group_id] = TaskGroup(id=group_id)
            self.groups[group_id].add_task(task)

    def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Add a dependency between two tasks."""
        if task_id in self.all_tasks and depends_on_id in self.all_tasks:
            self.all_tasks[task_id].add_dependency(depends_on_id)

    def topological_sort(self) -> list[str]:
        """
        Perform topological sort on task dependencies.

        Returns:
            List of task IDs in execution order

        Raises:
            ValueError: If cycle detected
        """
        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = {tid: 0 for tid in self.all_tasks}
        dependencies: dict[str, list[str]] = {tid: [] for tid in self.all_tasks}

        for task in self.all_tasks.values():
            for dep in task.dependencies:
                if dep in in_degree:
                    in_degree[task.id] += 1
                    dependencies[dep].append(task.id)

        # Find tasks with no dependencies
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for dependent in dependencies[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.all_tasks):
            # Cycle detected
            remaining = set(self.all_tasks.keys()) - set(result)
            raise ValueError(f"Cycle detected involving tasks: {remaining}")

        return result

    def get_execution_levels(self) -> list[list[str]]:
        """
        Group tasks by dependency level (tasks with no deps, then their dependents, etc.).

        Returns:
            List of levels, each level is a list of task IDs
        """
        levels: list[set[str]] = []
        remaining = set(self.all_tasks.keys())

        while remaining:
            # Find tasks with all dependencies satisfied
            current_level = {
                tid
                for tid in remaining
                if all(dep not in remaining for dep in self.all_tasks[tid].dependencies)
            }
            if not current_level:
                raise ValueError("Cycle detected in task graph")

            levels.append(current_level)
            remaining -= current_level

        return [list(level) for level in levels]

    def get_ready_tasks(self, completed: set[str]) -> list[TaskNode]:
        """Get all tasks ready to execute (dependencies satisfied)."""
        return [
            task
            for task in self.all_tasks.values()
            if task.status == TaskStatus.PENDING and task.can_execute(completed)
        ]

    def detect_cycles(self) -> bool:
        """Detect if the graph contains cycles."""
        try:
            self.topological_sort()
            return False
        except ValueError:
            return True

    def get_group_execution_order(self) -> list[str]:
        """Get groups in execution order based on dependencies."""
        # Build group dependency graph
        group_deps: dict[str, set[str]] = {gid: set() for gid in self.groups}

        for group in self.groups.values():
            for task in group.tasks:
                for dep_id in task.dependencies:
                    dep_task = self.all_tasks.get(dep_id)
                    if dep_task:
                        # Find which group the dependency belongs to
                        for gid, g in self.groups.items():
                            if dep_task in g.tasks:
                                if gid != group.id:
                                    group_deps[group.id].add(gid)
                                break

        # Topological sort of groups
        in_degree = {gid: 0 for gid in self.groups}
        for gid, deps in group_deps.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[gid] += 1

        queue = [gid for gid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            for gid, deps in group_deps.items():
                if current in deps:
                    in_degree[gid] -= 1
                    if in_degree[gid] == 0:
                        queue.append(gid)

        return result

    def summary(self) -> dict[str, Any]:
        """Get a summary of the task graph."""
        return {
            "name": self.name,
            "total_groups": len(self.groups),
            "total_tasks": len(self.all_tasks),
            "pending_tasks": sum(
                1 for t in self.all_tasks.values() if t.status == TaskStatus.PENDING
            ),
            "has_cycles": self.detect_cycles(),
            "execution_levels": len(self.get_execution_levels()),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "groups": {gid: g.to_dict() for gid, g in self.groups.items()},
            "tasks": {tid: t.to_dict() for tid, t in self.all_tasks.items()},
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    "TaskNode",
    "TaskGroup",
    "TaskGraph",
    "TaskStatus",
    "TaskPriority",
]
