"""
Phase 61: Cognitive Scaffolding - Executor

Task execution loop for Plan-and-Execute pattern.
遵循 ODF-EP 标准:
- Type hints required
- Async-first
- Composition over inheritance
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from agent.core.planner.schemas import Episode, Plan, PlanStatus, Task, TaskStatus

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Get current UTC time with timezone awareness."""
    return datetime.now(timezone.utc)


class ExecutionResult:
    """Result of a task execution."""

    def __init__(
        self,
        success: bool,
        output: str,
        error: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize execution result.

        Args:
            success: Whether execution succeeded.
            output: Result output from execution.
            error: Error message if failed.
            tool_calls: List of tool calls made during execution.
        """
        self.success = success
        self.output = output
        self.error = error
        self.tool_calls = tool_calls or []


class Executor:
    """Executes tasks from a Plan using available tools.

    The Executor implements the Plan-and-Execute pattern where it:
    1. Gets the next executable task from the plan
    2. Executes the task using available tools
    3. Records the result as an Episode
    4. Advances to the next task or handles failures

    Attributes:
        tool_registry: Registry of available tools for execution.
        inference_client: Client for LLM inference (if needed).
        max_retries: Maximum retries per failed task.
    """

    def __init__(
        self,
        tool_registry: dict[str, Callable[..., Any]],
        inference_client: Any | None = None,
        max_retries: int = 2,
    ) -> None:
        """Initialize the Executor.

        Args:
            tool_registry: Dictionary mapping tool names to callables.
            inference_client: Optional LLM client for complex tasks.
            max_retries: Maximum retries for failed tasks.
        """
        self.tool_registry = tool_registry
        self.inference_client = inference_client
        self.max_retries = max_retries

    async def execute_plan(self, plan: Plan) -> tuple[Plan, list[Episode]]:
        """Execute all tasks in a plan.

        Args:
            plan: The plan to execute.

        Returns:
            Tuple of (updated plan, list of episodes).
        """
        logger.info(f"Starting execution of plan {plan.id}")

        episodes: list[Episode] = []

        while not plan.is_complete():
            task = plan.get_next_executable_task()

            if task is None:
                logger.info(f"No executable tasks found for plan {plan.id}")
                break

            result = await self.execute_task(plan, task)

            episode = self._create_episode(plan, task, result)
            episodes.append(episode)

            if result.success:
                task.mark_completed()
                task.actual_results.append(result.output)
            else:
                task.mark_failed(result.error or "Unknown error")
                logger.warning(f"Task {task.id} failed: {result.error}")

            plan.updated_at = _utcnow()

            if plan.is_complete():
                plan.status = PlanStatus.COMPLETED
                logger.info(f"Plan {plan.id} completed")
                break

        return plan, episodes

    async def execute_task(self, plan: Plan, task: Task) -> ExecutionResult:
        """Execute a single task.

        Args:
            plan: The plan this task belongs to.
            task: The task to execute.

        Returns:
            ExecutionResult with success status and output.
        """
        task.mark_in_progress()
        logger.info(f"Executing task {task.id}: {task.description}")

        tool_calls: list[dict[str, Any]] = []

        if task.tool_calls:
            for tool_call in task.tool_calls:
                result = await self._execute_tool_call(task, tool_call)
                tool_calls.append(tool_call)

                if not result.success:
                    return ExecutionResult(
                        success=False,
                        output="",
                        error=result.error,
                        tool_calls=tool_calls,
                    )

            return ExecutionResult(
                success=True,
                output=f"Completed {len(tool_calls)} tool calls",
                tool_calls=tool_calls,
            )

        return ExecutionResult(
            success=True,
            output="No tool calls specified - task marked as complete",
        )

    async def _execute_tool_call(
        self,
        task: Task,
        tool_call: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a single tool call from a task.

        Args:
            task: The parent task.
            tool_call: Tool call specification with name and arguments.

        Returns:
            ExecutionResult from the tool execution.
        """
        import inspect

        tool_name = tool_call.get("name")

        if tool_name not in self.tool_registry:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )

        tool_func = self.tool_registry[tool_name]
        args = tool_call.get("arguments", {})

        try:
            if not callable(tool_func):
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Tool {tool_name} is not callable",
                )

            # Handle async functions
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**args)
            else:
                result = tool_func(**args)

            return ExecutionResult(
                success=True,
                output=str(result),
                tool_calls=[tool_call],
            )

        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=f"Tool execution failed: {e}",
            )

    def _create_episode(self, plan: Plan, task: Task, result: ExecutionResult) -> Episode:
        """Create an Episode from task execution.

        Args:
            plan: The plan being executed.
            task: The completed task.
            result: Execution result.

        Returns:
            Episode recording the execution.
        """
        return Episode(
            id=f"episode_{uuid.uuid4().hex[:8]}",
            plan_id=plan.id,
            task_id=task.id,
            goal=task.description,
            actions=result.tool_calls,
            results=[result.output] if result.success else [],
            reflection=result.error if not result.success else None,
            tokens_used=0,
            duration_seconds=0.0,
        )

    def can_execute(self, task: Task, completed_ids: set[str]) -> bool:
        """Check if a task can be executed.

        Args:
            task: Task to check.
            completed_ids: Set of completed task IDs.

        Returns:
            True if all dependencies are satisfied.
        """
        return task.can_execute(completed_ids)

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names in the registry.
        """
        return list(self.tool_registry.keys())


# =============================================================================
# Polyfactory for Testing
# =============================================================================


def create_executor(
    tool_registry: dict[str, Callable[..., Any]],
    inference_client: Any | None = None,
    max_retries: int = 2,
) -> Executor:
    """Factory function to create an Executor.

    Args:
        tool_registry: Dictionary mapping tool names to callables.
        inference_client: Optional LLM client.
        max_retries: Maximum retries for failed tasks.

    Returns:
        Configured Executor instance.
    """
    return Executor(
        tool_registry=tool_registry,
        inference_client=inference_client,
        max_retries=max_retries,
    )
