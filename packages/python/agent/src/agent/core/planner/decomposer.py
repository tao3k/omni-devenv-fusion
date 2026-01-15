"""
 Cognitive Scaffolding - Task Decomposer

LLM-based task decomposition for complex goals.
遵循 ODF-EP 标准:
- Type hints required
- Async-first
- Error handling
- Structured output parsing
"""

import json
import logging
from typing import Any

from agent.core.planner.schemas import Plan, PlanStatus, Task, TaskPriority
from agent.core.planner.prompts import get_decompose_prompt

logger = logging.getLogger(__name__)


class DecompositionError(Exception):
    """Raised when task decomposition fails."""

    def __init__(self, message: str, raw_response: str | None = None) -> None:
        """Initialize decomposition error.

        Args:
            message: Error message.
            raw_response: Optional raw LLM response.
        """
        super().__init__(message)
        self.raw_response = raw_response


class TaskDecomposer:
    """Decomposes complex goals into ordered tasks using LLM.

    Attributes:
        inference_client: Client for LLM inference.
        available_tools: List of available tool names.
        model: LLM model to use.
    """

    def __init__(
        self,
        inference_client: Any,
        available_tools: list[str],
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        """Initialize the task decomposer.

        Args:
            inference_client: Client for LLM inference.
            available_tools: List of available tool names.
            model: LLM model to use for decomposition.
        """
        self.inference_client = inference_client
        self.available_tools = available_tools
        self.model = model

    async def decompose(
        self,
        goal: str,
        context: str | None = None,
        plan_id: str | None = None,
    ) -> Plan:
        """Decompose a goal into an ordered plan.

        Args:
            goal: The user goal to decompose.
            context: Optional context about the project.
            plan_id: Optional plan ID (generated if not provided).

        Returns:
            A Plan with ordered tasks.

        Raises:
            DecompositionError: If decomposition fails.
        """
        system_prompt, user_prompt = get_decompose_prompt(
            goal=goal,
            available_tools=self.available_tools,
            context=context,
        )

        try:
            response = await self._call_llm(system_prompt, user_prompt)

            tasks = self._parse_tasks(response)

            plan = Plan(
                id=plan_id or f"plan_{goal[:20].replace(' ', '_')}",
                goal=goal,
                tasks=tasks,
            )

            logger.info(f"Decomposed goal into {len(tasks)} tasks: {[t.id for t in tasks]}")
            return plan

        except Exception as e:
            logger.error(f"Failed to decompose goal: {e}")
            raise DecompositionError(
                f"Task decomposition failed: {e}",
                raw_response=getattr(e, "raw_response", None),
            ) from e

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM for task decomposition.

        Args:
            system_prompt: System prompt for decomposition.
            user_prompt: User prompt with the goal.

        Returns:
            LLM response text.

        Raises:
            DecompositionError: If inference fails.
        """
        try:
            response = await self.inference_client.complete(
                model=self.model,
                system=system_prompt,
                prompt=user_prompt,
                max_tokens=4096,
                temperature=0.2,
            )
            return response
        except Exception as e:
            raise DecompositionError(f"LLM inference failed: {e}")

    def _parse_tasks(self, response: str) -> list[Task]:
        """Parse LLM response into Task objects.

        Args:
            response: LLM response text (should be JSON).

        Returns:
            List of Task objects.

        Raises:
            DecompositionError: If parsing fails.
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove markdown code blocks
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)

            tasks_data = data.get("tasks", data.get("plan", []))
            if not tasks_data:
                raise DecompositionError("No tasks found in response")

            tasks = []
            for i, task_data in enumerate(tasks_data):
                task = Task(
                    id=task_data.get("id", f"task_{i}"),
                    description=task_data.get("description", ""),
                    priority=self._parse_priority(task_data.get("priority", 3)),
                    dependencies=task_data.get("dependencies", []),
                    tool_calls=task_data.get("tool_calls", []),
                )
                tasks.append(task)

            return tasks

        except json.JSONDecodeError as e:
            raise DecompositionError(
                f"Failed to parse JSON from LLM response: {e}",
                raw_response=response,
            ) from e

    def _parse_priority(self, priority: int | str) -> TaskPriority:
        """Parse priority value to TaskPriority enum.

        Args:
            priority: Priority value from LLM (1-4 or string).

        Returns:
            TaskPriority enum value.
        """
        if isinstance(priority, int):
            if 1 <= priority <= 4:
                return TaskPriority(priority)
            return TaskPriority.MEDIUM

        priority_map = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW,
        }
        return priority_map.get(priority.lower(), TaskPriority.MEDIUM)


# =============================================================================
# Polyfactory for Testing
# =============================================================================


def create_decomposer(
    inference_client: Any,
    available_tools: list[str],
) -> TaskDecomposer:
    """Factory function to create a TaskDecomposer.

    Args:
        inference_client: Client for LLM inference.
        available_tools: List of available tool names.

    Returns:
        Configured TaskDecomposer instance.
    """
    return TaskDecomposer(
        inference_client=inference_client,
        available_tools=available_tools,
    )
