"""
Unit tests for Executor.

Tests task execution and the Plan-and-Execute loop.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core.planner.executor import (
    Executor,
    ExecutionResult,
    create_executor,
)
from agent.core.planner.schemas import (
    Plan,
    PlanStatus,
    Task,
    TaskStatus,
)


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_execution_result_success(self) -> None:
        """Verify successful execution result."""
        result = ExecutionResult(
            success=True,
            output="File created successfully",
            tool_calls=[{"name": "write_file"}],
        )

        assert result.success is True
        assert result.output == "File created successfully"
        assert result.error is None
        assert len(result.tool_calls) == 1

    def test_execution_result_failure(self) -> None:
        """Verify failed execution result."""
        result = ExecutionResult(
            success=False,
            output="",
            error="File not found",
        )

        assert result.success is False
        assert result.output == ""
        assert result.error == "File not found"


class TestExecutor:
    """Tests for Executor class."""

    @pytest.fixture
    def mock_tool_registry(self) -> dict:
        """Create a mock tool registry."""
        return {
            "read_file": AsyncMock(return_value="file content"),
            "write_file": AsyncMock(return_value="file written"),
            "failing_tool": AsyncMock(side_effect=Exception("Tool failed")),
        }

    @pytest.fixture
    def executor(self, mock_tool_registry: dict) -> Executor:
        """Create an Executor instance."""
        return Executor(tool_registry=mock_tool_registry)

    def test_executor_initialization(self, executor: Executor) -> None:
        """Verify executor initializes correctly."""
        assert executor.max_retries == 2
        assert len(executor.get_available_tools()) == 3

    @pytest.mark.asyncio
    async def test_execute_task_without_tools(self, executor: Executor) -> None:
        """Verify executing a task without tool calls returns success."""
        plan = Plan(id="test_plan", goal="Test goal")
        task = Task(
            id="simple_task",
            description="A simple task",
        )

        result = await executor.execute_task(plan, task)

        assert result.success is True
        assert "No tool calls specified" in result.output

    @pytest.mark.asyncio
    async def test_execute_tool_call_success(
        self,
        executor: Executor,
        mock_tool_registry: dict,
    ) -> None:
        """Verify successful tool call."""
        task = Task(id="test", description="Test")
        tool_call = {
            "name": "read_file",
            "arguments": {"path": "/test/file.txt"},
        }

        result = await executor._execute_tool_call(task, tool_call)

        assert result.success is True
        assert result.output == "file content"
        mock_tool_registry["read_file"].assert_called_once_with(
            path="/test/file.txt",
        )

    @pytest.mark.asyncio
    async def test_execute_tool_call_unknown(
        self,
        executor: Executor,
    ) -> None:
        """Verify unknown tool returns error."""
        task = Task(id="test", description="Test")
        tool_call = {
            "name": "unknown_tool",
            "arguments": {},
        }

        result = await executor._execute_tool_call(task, tool_call)

        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_call_failure(
        self,
        executor: Executor,
    ) -> None:
        """Verify tool failure returns error."""
        task = Task(id="test", description="Test")
        tool_call = {
            "name": "failing_tool",
            "arguments": {},
        }

        result = await executor._execute_tool_call(task, tool_call)

        assert result.success is False
        assert "Tool execution failed" in result.error

    def test_can_execute_no_dependencies(self) -> None:
        """Verify task with no dependencies can execute."""
        executor = Executor(tool_registry={})
        task = Task(id="t1", description="Task", dependencies=[])

        assert executor.can_execute(task, set()) is True

    def test_can_execute_with_dependencies(self) -> None:
        """Verify task with dependencies checks correctly."""
        executor = Executor(tool_registry={})
        task = Task(id="t2", description="Task", dependencies=["t1"])

        assert executor.can_execute(task, set()) is False
        assert executor.can_execute(task, {"t1"}) is True

    def test_create_executor_factory(self) -> None:
        """Verify factory function creates executor."""
        registry = {"test_tool": AsyncMock()}
        executor = create_executor(tool_registry=registry)

        assert isinstance(executor, Executor)
        assert executor.tool_registry == registry


class TestExecutorPlanExecution:
    """Tests for plan execution flow."""

    @pytest.fixture
    def mock_tools(self) -> dict:
        """Create mock tools."""
        return {
            "read_file": AsyncMock(return_value="content"),
            "write_file": AsyncMock(return_value="written"),
        }

    @pytest.fixture
    def plan_with_tasks(self) -> Plan:
        """Create a plan with tasks."""
        t1 = Task(id="t1", description="Read file", tool_calls=[{"name": "read_file"}])
        t2 = Task(id="t2", description="Write file", tool_calls=[{"name": "write_file"}])
        return Plan(id="test_plan", goal="Test goal", tasks=[t1, t2])

    @pytest.mark.asyncio
    async def test_execute_plan_sequential(
        self,
        mock_tools: dict,
        plan_with_tasks: Plan,
    ) -> None:
        """Verify plan executes tasks sequentially."""
        executor = Executor(tool_registry=mock_tools)

        updated_plan, episodes = await executor.execute_plan(plan_with_tasks)

        assert updated_plan.status == PlanStatus.COMPLETED
        assert len(episodes) == 2
        assert len(updated_plan.completed_tasks) == 2

    @pytest.mark.asyncio
    async def test_execute_plan_with_dependencies(
        self,
        mock_tools: dict,
    ) -> None:
        """Verify plan respects task dependencies."""
        t1 = Task(id="t1", description="First task")
        t2 = Task(
            id="t2",
            description="Second task",
            dependencies=["t1"],
            tool_calls=[{"name": "read_file"}],
        )

        plan = Plan(id="test", goal="Goal", tasks=[t2, t1])

        executor = Executor(tool_registry=mock_tools)
        updated_plan, episodes = await executor.execute_plan(plan)

        # t1 should complete first (no dependencies)
        # t2 depends on t1, should complete second
        assert len(updated_plan.completed_tasks) == 2

    @pytest.mark.asyncio
    async def test_execute_plan_handles_failure(
        self,
        mock_tools: dict,
    ) -> None:
        """Verify plan handles failed tasks gracefully."""
        failing_tools = {
            "failing": AsyncMock(side_effect=Exception("Failed")),
        }

        t1 = Task(
            id="t1",
            description="Failing task",
            tool_calls=[{"name": "failing"}],
        )

        plan = Plan(id="test", goal="Goal", tasks=[t1])

        executor = Executor(tool_registry=failing_tools)
        updated_plan, episodes = await executor.execute_plan(plan)

        assert len(episodes) == 1
        assert updated_plan.tasks[0].status == TaskStatus.FAILED
