"""
Unit tests for Planner Schemas.

Tests Task, Plan, and Episode data structures.
"""

import pytest
from datetime import datetime, timezone

from agent.core.planner.schemas import (
    TaskStatus,
    TaskPriority,
    Task,
    Plan,
    PlanStatus,
    Episode,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self) -> None:
        """Verify task status enum values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.BLOCKED == "blocked"
        assert TaskStatus.SKIPPED == "skipped"

    def test_task_status_string_enum(self) -> None:
        """Verify TaskStatus is a string enum."""
        status = TaskStatus.PENDING
        assert isinstance(status, str)
        assert status == "pending"


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_task_priority_values(self) -> None:
        """Verify task priority enum values."""
        assert TaskPriority.CRITICAL == 1
        assert TaskPriority.HIGH == 2
        assert TaskPriority.MEDIUM == 3
        assert TaskPriority.LOW == 4

    def test_task_priority_ordering(self) -> None:
        """Verify priority ordering works."""
        priorities = [
            TaskPriority.LOW,
            TaskPriority.MEDIUM,
            TaskPriority.HIGH,
            TaskPriority.CRITICAL,
        ]
        assert sorted(priorities) == priorities[::-1]


class TestTask:
    """Tests for Task model."""

    def test_task_creation_defaults(self) -> None:
        """Verify task has correct defaults."""
        task = Task(id="test_task", description="Test task")

        assert task.id == "test_task"
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM
        assert task.dependencies == []
        assert task.tool_calls == []
        assert task.actual_results == []
        assert task.reflection is None

    def test_task_creation_full(self) -> None:
        """Verify task with all fields."""
        task = Task(
            id="complex_task",
            description="Complex task with dependencies",
            priority=TaskPriority.HIGH,
            dependencies=["task_1", "task_2"],
            tool_calls=[{"name": "read_file", "arguments": {"path": "/test"}}],
        )

        assert task.priority == TaskPriority.HIGH
        assert task.dependencies == ["task_1", "task_2"]
        assert len(task.tool_calls) == 1

    def test_task_mark_in_progress(self) -> None:
        """Verify mark_in_progress sets status and timestamp."""
        task = Task(id="test", description="Test")
        task.mark_in_progress()

        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_task_mark_completed(self) -> None:
        """Verify mark_completed sets status and timestamp."""
        task = Task(id="test", description="Test")
        task.mark_completed()

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_task_mark_failed(self) -> None:
        """Verify mark_failed sets status, timestamp and reflection."""
        task = Task(id="test", description="Test")
        task.mark_failed("Something went wrong")

        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.reflection == "Something went wrong"

    def test_task_can_execute(self) -> None:
        """Verify can_execute checks dependencies."""
        task = Task(
            id="dependent_task",
            description="Task with dependencies",
            dependencies=["task_1", "task_2"],
        )

        assert not task.can_execute(set())
        assert not task.can_execute({"task_1"})
        assert task.can_execute({"task_1", "task_2"})
        assert task.can_execute({"task_1", "task_2", "task_3"})

    def test_task_to_dict(self) -> None:
        """Verify to_dict serializes correctly."""
        task = Task(
            id="test_task",
            description="Test description",
            status=TaskStatus.COMPLETED,
        )
        data = task.to_dict()

        assert data["id"] == "test_task"
        assert data["status"] == "completed"
        assert data["description"] == "Test description"

    def test_task_id_validation(self) -> None:
        """Verify task ID cannot be empty."""
        with pytest.raises(ValueError):
            Task(id="", description="Test")

        with pytest.raises(ValueError):
            Task(id="   ", description="Test")


class TestPlan:
    """Tests for Plan model."""

    def test_plan_creation_defaults(self) -> None:
        """Verify plan has correct defaults."""
        plan = Plan(id="test_plan", goal="Test goal")

        assert plan.id == "test_plan"
        assert plan.goal == "Test goal"
        assert plan.tasks == []
        assert plan.current_task_index == 0
        assert plan.status == PlanStatus.ACTIVE

    def test_plan_with_tasks(self) -> None:
        """Verify plan with tasks."""
        tasks = [
            Task(id="t1", description="Task 1"),
            Task(id="t2", description="Task 2"),
        ]
        plan = Plan(id="test_plan", goal="Test goal", tasks=tasks)

        assert len(plan.tasks) == 2
        assert plan.current_task is not None
        assert plan.current_task.id == "t1"

    def test_plan_completed_tasks(self) -> None:
        """Verify completed_tasks property."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        t1.mark_completed()

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert len(plan.completed_tasks) == 1
        assert plan.completed_tasks[0].id == "t1"

    def test_plan_pending_tasks(self) -> None:
        """Verify pending_tasks property."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        t1.mark_completed()

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert len(plan.pending_tasks) == 1
        assert plan.pending_tasks[0].id == "t2"

    def test_plan_completed_ids(self) -> None:
        """Verify completed_ids property."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        t1.mark_completed()

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert plan.completed_ids == {"t1"}

    def test_plan_get_next_executable_task(self) -> None:
        """Verify get_next_executable_task."""
        t1 = Task(id="t1", description="Task 1", dependencies=[])
        t2 = Task(id="t2", description="Task 2", dependencies=["t1"])
        t3 = Task(id="t3", description="Task 3", dependencies=[])

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2, t3])

        # t1 has no dependencies, should be executable
        assert plan.get_next_executable_task() == t1

        t1.mark_completed()

        # t2 depends on t1 (completed), should be executable
        assert plan.get_next_executable_task() == t2

    def test_plan_advance_to_task(self) -> None:
        """Verify advance_to_task moves current index."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert plan.current_task.id == "t1"

        result = plan.advance_to_task("t2")

        assert result is True
        assert plan.current_task.id == "t2"

    def test_plan_advance_to_task_not_found(self) -> None:
        """Verify advance_to_task returns False for invalid ID."""
        t1 = Task(id="t1", description="Task 1")
        plan = Plan(id="test", goal="Goal", tasks=[t1])

        result = plan.advance_to_task("nonexistent")

        assert result is False

    def test_plan_is_complete(self) -> None:
        """Verify is_complete checks all tasks."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert not plan.is_complete()

        t1.mark_completed()
        assert not plan.is_complete()

        t2.mark_completed()
        assert plan.is_complete()

    def test_plan_skip_counts_as_complete(self) -> None:
        """Verify skipped tasks count as complete."""
        t1 = Task(id="t1", description="Task 1")
        t2 = Task(id="t2", description="Task 2")

        t1.mark_completed()
        t2.status = TaskStatus.SKIPPED

        plan = Plan(id="test", goal="Goal", tasks=[t1, t2])

        assert plan.is_complete()


class TestEpisode:
    """Tests for Episode model."""

    def test_episode_creation_defaults(self) -> None:
        """Verify episode has correct defaults."""
        episode = Episode(
            id="test_episode",
            plan_id="test_plan",
            task_id="test_task",
            goal="Test goal",
        )

        assert episode.id == "test_episode"
        assert episode.plan_id == "test_plan"
        assert episode.task_id == "test_task"
        assert episode.goal == "Test goal"
        assert episode.actions == []
        assert episode.results == []
        assert episode.reflection is None
        assert episode.tokens_used == 0
        assert episode.duration_seconds == 0.0

    def test_episode_full_creation(self) -> None:
        """Verify episode with all fields."""
        episode = Episode(
            id="full_episode",
            plan_id="test_plan",
            task_id="test_task",
            goal="Test goal",
            actions=[{"tool": "read", "args": {"path": "/test"}}],
            results=["File read successfully"],
            reflection="Task completed as expected",
            tokens_used=150,
            duration_seconds=2.5,
        )

        assert len(episode.actions) == 1
        assert len(episode.results) == 1
        assert episode.tokens_used == 150
        assert episode.duration_seconds == 2.5

    def test_episode_to_dict(self) -> None:
        """Verify to_dict serializes correctly."""
        episode = Episode(
            id="test",
            plan_id="p1",
            task_id="t1",
            goal="Goal",
        )
        data = episode.to_dict()

        assert data["id"] == "test"
        assert data["plan_id"] == "p1"
        assert data["task_id"] == "t1"
        assert "created_at" in data
