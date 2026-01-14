"""
Phase 61: Cognitive Scaffolding - Planner

Main Planner class for task decomposition and planning.
遵循 ODF-EP 标准:
- Type hints required
- Async-first
- Composition over inheritance
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from agent.core.planner.schemas import Plan, PlanStatus, Task
from agent.core.planner.decomposer import TaskDecomposer, DecompositionError

logger = logging.getLogger(__name__)


class Planner:
    """Planner for decomposing complex goals into actionable tasks.

    The Planner uses LLM-based decomposition to break down user goals
    into ordered, independent tasks that can be executed by the Executor.

    Attributes:
        decomposer: TaskDecomposer instance for decomposition.
        inference_client: Client for LLM inference.
    """

    def __init__(
        self,
        inference_client: Any,
        available_tools: list[str],
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        """Initialize the Planner.

        Args:
            inference_client: Client for LLM inference.
            available_tools: List of available tool names.
            model: LLM model for decomposition.
        """
        self.decomposer = TaskDecomposer(
            inference_client=inference_client,
            available_tools=available_tools,
            model=model,
        )

    async def create_plan(
        self,
        goal: str,
        context: str | None = None,
    ) -> Plan:
        """Create a new plan from a goal.

        Args:
            goal: The user goal to decompose.
            context: Optional context about the project.

        Returns:
            A Plan with ordered tasks.

        Raises:
            DecompositionError: If plan creation fails.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating plan {plan_id} for goal: {goal[:50]}...")

        try:
            plan = await self.decomposer.decompose(
                goal=goal,
                context=context,
                plan_id=plan_id,
            )
            logger.info(f"Plan {plan_id} created with {len(plan.tasks)} tasks")
            return plan

        except DecompositionError as e:
            logger.error(f"Failed to create plan: {e}")
            raise

    async def revise_plan(
        self,
        plan: Plan,
        failed_task_id: str,
        failure_reason: str,
    ) -> Plan:
        """Revise a plan after task failure.

        Args:
            plan: The current plan.
            failed_task_id: ID of the task that failed.
            failure_reason: Reason for the failure.

        Returns:
            Revised plan.

        Raises:
            ValueError: If failed_task_id not found in plan.
        """
        # Find the failed task
        failed_task = None
        for task in plan.tasks:
            if task.id == failed_task_id:
                failed_task = task
                break

        if failed_task is None:
            raise ValueError(f"Task {failed_task_id} not found in plan")

        logger.info(f"Revising plan {plan.id} after task {failed_task_id} failed")

        # Mark failed task
        failed_task.mark_failed(failure_reason)

        # Get completed task IDs for context
        completed_ids = plan.completed_ids

        # Simple revision: mark failed and skip, create new task if needed
        # In a full implementation, this would use LLM to replan

        # Create a retry task with different approach
        retry_task = Task(
            id=f"{failed_task_id}_retry",
            description=f"Retry: {failed_task.description} (attempt 2)",
            priority=failed_task.priority,
            dependencies=list(completed_ids),
        )

        # Add retry task after failed task
        failed_task_index = plan.tasks.index(failed_task)
        plan.tasks.insert(failed_task_index + 1, retry_task)

        plan.status = PlanStatus.REVISING
        plan.updated_at = failed_task.completed_at or datetime.utcnow()

        logger.info(f"Plan {plan.id} revised. Added retry task {retry_task.id}")
        return plan

    def get_next_task(self, plan: Plan) -> Task | None:
        """Get the next executable task from a plan.

        Args:
            plan: The plan to get next task from.

        Returns:
            Next Task to execute, or None if plan is complete.
        """
        return plan.get_next_executable_task()

    def advance_to_task(self, plan: Plan, task_id: str) -> bool:
        """Advance plan execution to a specific task.

        Args:
            plan: The plan to advance.
            task_id: ID of task to advance to.

        Returns:
            True if advancement was successful.
        """
        return plan.advance_to_task(task_id)

    def check_plan_complete(self, plan: Plan) -> bool:
        """Check if a plan is fully complete.

        Args:
            plan: The plan to check.

        Returns:
            True if all tasks are completed or skipped.
        """
        return plan.is_complete()

    def get_plan_summary(self, plan: Plan) -> dict[str, Any]:
        """Get a summary of plan execution status.

        Args:
            plan: The plan to summarize.

        Returns:
            Dictionary with plan status summary.
        """
        return {
            "plan_id": plan.id,
            "goal": plan.goal,
            "total_tasks": len(plan.tasks),
            "completed": len(plan.completed_tasks),
            "pending": len(plan.pending_tasks),
            "progress": f"{len(plan.completed_tasks)}/{len(plan.tasks)}",
            "current_task": plan.current_task.id if plan.current_task else None,
            "status": plan.status.value,
        }
