"""
 Cognitive Scaffolding - Planner

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

from agent.core.planner.schemas import Plan, PlanStatus, Task, WorkflowBlueprint
from agent.core.planner.decomposer import TaskDecomposer, DecompositionError
from agent.core.planner.architect import WorkflowArchitect

logger = logging.getLogger(__name__)


class Planner:
    """Planner for decomposing complex goals into actionable tasks.

    The Planner uses LLM-based decomposition to break down user goals
    into ordered, independent tasks that can be executed by the Executor.

     Also provides dynamic workflow generation via WorkflowArchitect.

    Attributes:
        decomposer: TaskDecomposer instance for decomposition.
        architect: WorkflowArchitect for dynamic workflow generation.
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

        #  Workflow Architect for dynamic graph generation
        self.architect = WorkflowArchitect(
            inference_client=inference_client,
            tools=available_tools,
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

    #  Dynamic Workflow Methods
    async def create_dynamic_workflow(
        self,
        goal: str,
        context: str | None = None,
    ) -> WorkflowBlueprint:
        """Generate a dynamic executable workflow for the goal.

        This method uses the WorkflowArchitect to design a complete
        execution graph that can be compiled and run by DynamicGraphBuilder.

        Args:
            goal: The user goal to achieve.
            context: Optional context about the project.

        Returns:
            A WorkflowBlueprint ready to be compiled into a graph.
        """
        logger.info(f"Creating dynamic workflow for: {goal[:50]}...")
        return await self.architect.design_workflow(goal, context or "")

    #  Knowledge Retrieval Methods
    async def load_relevant_knowledge(
        self,
        query: str,
        limit: int = 3,
    ) -> str:
        """Load relevant past knowledge for the query.

         Long-term memory retrieval for new sessions.

        Args:
            query: The query to search knowledge for.
            limit: Maximum number of knowledge entries to return.

        Returns:
            Markdown-formatted relevant knowledge, or empty string if none found.
        """
        from pathlib import Path
        from common.prj_dirs import PRJ_DATA

        knowledge_dir = PRJ_DATA("knowledge", "harvested")
        if not knowledge_dir.exists():
            return ""

        query_lower = query.lower()
        results = []

        for category_dir in knowledge_dir.iterdir():
            if not category_dir.is_dir():
                continue

            for md_file in category_dir.glob("*.md"):
                try:
                    content = md_file.read_text().lower()
                    if query_lower in content:
                        # Extract title from frontmatter
                        frontmatter = _parse_frontmatter(md_file.read_text())
                        title = frontmatter.get("title", md_file.stem)

                        if len(results) < limit:
                            results.append(
                                {
                                    "title": title,
                                    "category": category_dir.name,
                                    "path": str(md_file),
                                    "snippet": _get_content_snippet(
                                        md_file.read_text(), query_lower
                                    ),
                                }
                            )
                except Exception as e:
                    logger.debug(f"Error reading knowledge file: {e}")
                    continue

        if not results:
            return ""

        # Format as knowledge context
        context = "\n\n## Relevant Past Knowledge\n\n"
        for i, r in enumerate(results, 1):
            context += f"### {i}. {r['title']} ({r['category']})\n\n"
            if r.get("snippet"):
                context += f"...{r['snippet']}...\n\n"
            context += f"[Source: {r['path']}]\n\n"

        return context


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content."""
    frontmatter = {}

    if content.startswith("---"):
        end_marker = content.find("---", 3)
        if end_marker != -1:
            yaml_content = content[3:end_marker].strip()
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    frontmatter[key] = value

    return frontmatter


def _get_content_snippet(content: str, query: str, context_chars: int = 150) -> str:
    """Get a snippet around the match."""
    idx = content.lower().find(query)
    if idx == -1:
        return content[:context_chars]

    start = max(0, idx - context_chars)
    end = min(len(content), idx + len(query) + context_chars)

    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet
