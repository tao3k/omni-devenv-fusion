"""
Phase 61: Cognitive Scaffolding - Planner Schemas

Task, Plan, and Episode data structures for the Planner module.
遵循 ODF-EP 标准:
- Pydantic BaseModel
- Type hints required
- Google docstrings
- Async-first ready
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    """Get current UTC time with timezone awareness."""
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    """Status of a task within a plan."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskPriority(int, Enum):
    """Priority level for task execution ordering."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class Task(BaseModel):
    """A single unit of work in a plan.

    Attributes:
        id: Unique identifier for the task.
        description: Human-readable description of what needs to be done.
        status: Current execution status.
        priority: Execution priority (lower = more urgent).
        dependencies: List of task IDs that must complete before this task.
        tool_calls: Planned tool invocations for this task.
        actual_results: Results from actual execution.
        reflection: Reviewer's assessment after execution.
        created_at: Timestamp when task was created.
        started_at: Timestamp when task execution started.
        completed_at: Timestamp when task execution completed.
        metadata: Additional task-specific metadata.
    """

    id: str = Field(..., description="Unique task identifier")
    description: str = Field(..., description="What needs to be done")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current execution status")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Execution priority")
    dependencies: list[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="Planned tool invocations"
    )
    actual_results: list[str] = Field(default_factory=list, description="Results from execution")
    reflection: Optional[str] = Field(default=None, description="Reviewer's assessment")
    created_at: datetime = Field(default_factory=_utcnow, description="Task creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Execution start timestamp")
    completed_at: Optional[datetime] = Field(
        default=None, description="Execution completion timestamp"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")

    @field_validator("id")
    @classmethod
    def id_must_be_non_empty(cls: type["Task"], v: str) -> str:
        """Validate task ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Task ID must not be empty")
        return v.strip()

    def mark_in_progress(self) -> None:
        """Mark task as in progress with timestamp."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = _utcnow()

    def mark_completed(self) -> None:
        """Mark task as completed with timestamp."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = _utcnow()

    def mark_failed(self, reason: str) -> None:
        """Mark task as failed with reason."""
        self.status = TaskStatus.FAILED
        self.completed_at = _utcnow()
        self.reflection = reason

    def can_execute(self, completed_ids: set[str]) -> bool:
        """Check if all dependencies are satisfied.

        Args:
            completed_ids: Set of completed task IDs.

        Returns:
            True if all dependencies are in completed_ids.
        """
        return all(dep in completed_ids for dep in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "tool_calls": self.tool_calls,
            "actual_results": self.actual_results,
            "reflection": self.reflection,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PlanStatus(str, Enum):
    """Status of a plan."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    REVISING = "revising"


class Plan(BaseModel):
    """A hierarchical plan containing multiple tasks.

    Attributes:
        id: Unique identifier for the plan.
        goal: Original user request or goal.
        tasks: List of tasks in execution order.
        current_task_index: Index of currently executing task.
        status: Plan execution status.
        created_at: Plan creation timestamp.
        updated_at: Last update timestamp.
        metadata: Additional plan metadata.
    """

    id: str = Field(..., description="Unique plan identifier")
    goal: str = Field(..., description="Original user goal")
    tasks: list[Task] = Field(default_factory=list, description="Tasks in this plan")
    current_task_index: int = Field(default=0, description="Index of current executing task")
    status: PlanStatus = Field(default=PlanStatus.ACTIVE, description="Plan execution status")
    created_at: datetime = Field(default_factory=_utcnow, description="Plan creation timestamp")
    updated_at: datetime = Field(default_factory=_utcnow, description="Last update timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional plan metadata")

    @field_validator("id")
    @classmethod
    def id_must_be_non_empty(cls: type["Plan"], v: str) -> str:
        """Validate plan ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Plan ID must not be empty")
        return v.strip()

    @property
    def current_task(self) -> Optional[Task]:
        """Get the currently executing task."""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    @property
    def completed_tasks(self) -> list[Task]:
        """Get all completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    @property
    def pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    @property
    def completed_ids(self) -> set[str]:
        """Get set of completed task IDs."""
        return {t.id for t in self.completed_tasks}

    def get_next_executable_task(self) -> Optional[Task]:
        """Get next task whose dependencies are satisfied."""
        for task in self.tasks[self.current_task_index :]:
            if task.status == TaskStatus.PENDING and task.can_execute(self.completed_ids):
                return task
        return None

    def advance_to_task(self, task_id: str) -> bool:
        """Advance execution to specified task.

        Args:
            task_id: ID of task to advance to.

        Returns:
            True if advancement was successful.
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.current_task_index = i
                self.updated_at = _utcnow()
                return True
        return False

    def add_task(self, task: Task) -> None:
        """Add a task to the plan.

        Args:
            task: Task to add.
        """
        self.tasks.append(task)
        self.updated_at = _utcnow()

    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for t in self.tasks)

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary for serialization."""
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "current_task_index": self.current_task_index,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Episode(BaseModel):
    """A completed episode for scratchpad memory.

    Attributes:
        id: Unique episode identifier.
        plan_id: Associated plan ID.
        task_id: Associated task ID.
        goal: Episode goal description.
        actions: List of actions taken.
        results: List of results obtained.
        reflection: Self-assessment of the episode.
        tokens_used: Token consumption for this episode.
        duration_seconds: Episode duration.
        created_at: Episode creation timestamp.
    """

    id: str = Field(..., description="Unique episode identifier")
    plan_id: str = Field(..., description="Associated plan ID")
    task_id: str = Field(..., description="Associated task ID")
    goal: str = Field(..., description="Episode goal")
    actions: list[dict[str, Any]] = Field(
        default_factory=list, description="Actions taken in this episode"
    )
    results: list[str] = Field(default_factory=list, description="Results obtained")
    reflection: Optional[str] = Field(default=None, description="Self-assessment")
    tokens_used: int = Field(default=0, description="Token consumption")
    duration_seconds: float = Field(default=0.0, description="Episode duration in seconds")
    created_at: datetime = Field(default_factory=_utcnow, description="Episode creation timestamp")

    def to_dict(self) -> dict[str, Any]:
        """Convert episode to dictionary for serialization."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "actions": self.actions,
            "results": self.results,
            "reflection": self.reflection,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Phase 61: Dynamic Workflow Schemas
# =============================================================================


class WorkflowNode(BaseModel):
    """A node in the dynamic workflow graph.

    Attributes:
        id: Unique node identifier (e.g., 'read_file_1').
        type: Type of node - skill, function, or llm.
        target: Target skill command (skill.cmd) or function name.
        fixed_args: Static arguments for the node execution.
        state_inputs: Mapping from state keys to argument names.
    """

    id: str = Field(..., description="Unique node identifier")
    type: Literal["skill", "function", "llm"] = Field(..., description="Type of node")
    target: str = Field(..., description="Target skill command (skill.cmd) or function name")
    fixed_args: Dict[str, Any] = Field(default_factory=dict, description="Static arguments")
    state_inputs: Dict[str, str] = Field(
        default_factory=dict, description="State key -> arg name mapping"
    )


class WorkflowEdge(BaseModel):
    """An edge defining flow between nodes.

    Attributes:
        source: Source node ID.
        target: Target node ID.
        condition: Optional condition logic for branching.
    """

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    condition: Optional[str] = Field(None, description="Condition logic (e.g., 'result.success')")


class WorkflowBlueprint(BaseModel):
    """Blueprint for a dynamic workflow generated by the Planner.

    This schema defines a complete execution graph that can be compiled
    by DynamicGraphBuilder into a runnable LangGraph.

    Attributes:
        name: Name of the workflow.
        description: Description of what this workflow does.
        nodes: List of execution nodes.
        edges: List of flow edges.
        entry_point: ID of the starting node.
    """

    name: str = Field(..., description="Name of the workflow")
    description: str = Field(..., description="Description of what this workflow does")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="List of execution nodes")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="List of flow edges")
    entry_point: str = Field(..., description="ID of the starting node")

    def to_dict(self) -> dict[str, Any]:
        """Convert blueprint to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
            "entry_point": self.entry_point,
        }
