"""
simple.py - Adaptive Planner for OmniLoop.

Provides lightweight task estimation and initial planning without the full weight of the heavy planner.
"""

from __future__ import annotations

import re
from typing import Any, Tuple

import structlog

logger = structlog.get_logger(__name__)


class AdaptivePlanner:
    """
    Lightweight adaptive planner that estimates task complexity and generates initial plans.

    This is a simplified alternative to the full Planner class for quick task assessment.
    It focuses on step estimation and high-level guidance without the overhead of
    hierarchical task decomposition.
    """

    def __init__(self, client: Any | None = None) -> None:
        """Initialize the adaptive planner.

        Args:
            client: Optional LLM client for generating plans.
        """
        self._client = client

    def estimate_steps(self, task: str) -> int:
        """Estimate the number of steps required for a task based on keywords.

        This is a fast heuristic that runs without LLM calls.

        Args:
            task: The user's task description.

        Returns:
            Estimated number of steps (with safety buffer).
        """
        task_lower = task.lower()

        # Base complexity detection
        if any(kw in task_lower for kw in ["analyze", "list", "find", "show", "get"]):
            base_steps = 2
        elif any(kw in task_lower for kw in ["edit", "update", "change", "modify", "replace"]):
            base_steps = 4
        elif any(kw in task_lower for kw in ["create", "add", "implement", "write"]):
            base_steps = 5
        elif any(kw in task_lower for kw in ["refactor", "restructure", "migrate"]):
            base_steps = 8
        elif any(kw in task_lower for kw in ["debug", "fix", "troubleshoot", "investigate"]):
            base_steps = 6
        else:
            base_steps = 3

        # Multi-file indicator
        if any(kw in task_lower for kw in ["all", "every", "multiple", "across", "project-wide"]):
            base_steps += 2

        # Documentation indicator - suggest writer skill
        if any(kw in task_lower for kw in ["readme", "documentation", "doc", "docs", "read me"]):
            base_steps = max(base_steps, 4)

        # Safety buffer
        estimated_steps = base_steps + 2

        logger.info(
            "AdaptivePlanner: Step estimation complete",
            task_preview=task[:50],
            estimated_steps=estimated_steps,
        )

        return estimated_steps

    def suggest_skill(self, task: str) -> str | None:
        """Suggest the most appropriate skill for a task.

        Args:
            task: The user's task description.

        Returns:
            Suggested skill name or None.
        """
        task_lower = task.lower()

        if any(
            kw in task_lower
            for kw in [
                "write",
                "edit",
                "replace",
                "update",
                "modify",
                "documentation",
                "readme",
                "polish",
            ]
        ):
            return "writer"
        elif any(kw in task_lower for kw in ["grep", "search", "find", "pattern", "match"]):
            return "grep"
        elif any(kw in task_lower for kw in ["run", "execute", "test", "build", "compile"]):
            return "runner"
        elif any(kw in task_lower for kw in ["git", "commit", "branch", "merge"]):
            return "git"
        elif any(kw in task_lower for kw in ["file", "list", "structure", "tree"]):
            return "file_ops"

        return None

    async def analyze_task(self, task: str) -> Tuple[int, str]:
        """Analyze a task and generate an initial plan.

        Uses LLM for complex tasks, falls back to heuristics for simple ones.

        Args:
            task: The user's task description.

        Returns:
            Tuple of (estimated_steps, plan_text).
        """
        # First, do fast heuristic estimation
        estimated_steps = self.estimate_steps(task)
        suggested_skill = self.suggest_skill(task)

        # If we have an LLM client, generate a more detailed plan
        if self._client:
            try:
                plan_text = await self._generate_llm_plan(task, suggested_skill)
            except Exception as e:
                logger.warning(f"AdaptivePlanner: LLM planning failed: {e}")
                plan_text = self._fallback_plan(task, suggested_skill)
        else:
            plan_text = self._fallback_plan(task, suggested_skill)

        return estimated_steps, plan_text

    async def _generate_llm_plan(self, task: str, suggested_skill: str | None) -> str:
        """Generate a plan using the LLM client.

        Args:
            task: The user's task description.
            suggested_skill: The skill suggested for this task.

        Returns:
            Generated plan text.
        """
        skill_hint = f"\n- Suggested skill: {suggested_skill}" if suggested_skill else ""

        prompt = f"""You are the Planning Module for an autonomous coding agent.
Analyze the following task:
"{task}"

1. Estimate the number of steps (cycles of Observe-Think-Act) required.
   - Simple query/read: 2-3 steps
   - Single file edit: 4-6 steps (Read -> Search -> Edit -> Verify)
   - Refactor/Multi-file: 8-15 steps
   - Complex architecture: 15+ steps
   *ALWAYS* add a safety buffer of +2 steps.

2. Create a concise, high-level plan (bullet points).
   If the task involves editing text or documentation, EXPLICITLY suggest using the 'writer' skill.{skill_hint}

Output format STRICTLY as:
STEPS: <number>
PLAN:
- <step 1>
- <step 2>
...
"""

        try:
            response = await self._client.complete(
                system_prompt="You are a pragmatic technical lead. Be realistic but efficient.",
                user_query=prompt,
                max_tokens=500,
            )
            content = response.get("content", "").strip()

            # Parse the response
            steps_match = re.search(r"STEPS:\s*(\d+)", content, re.IGNORECASE)
            if steps_match:
                parsed_steps = int(steps_match.group(1))
                # Use the larger of heuristic and LLM estimate
                estimated = max(self.estimate_steps(task), parsed_steps)

            plan_match = re.search(r"(PLAN:.*)", content, re.IGNORECASE | re.DOTALL)
            if plan_match:
                plan = plan_match.group(1).strip()
            else:
                plan = content

            logger.info("AdaptivePlanner: LLM plan generated successfully")
            return plan

        except Exception as e:
            logger.warning(f"AdaptivePlanner: LLM planning error: {e}")
            return self._fallback_plan(task, suggested_skill)

    def _fallback_plan(self, task: str, suggested_skill: str | None) -> str:
        """Generate a fallback plan without LLM.

        Args:
            task: The user's task description.
            suggested_skill: The skill suggested for this task.

        Returns:
            Fallback plan text.
        """
        task_lower = task.lower()
        steps = []

        # General workflow for most tasks
        steps.append("Analyze the task and identify the target file(s)")

        if suggested_skill == "writer":
            steps.extend(
                [
                    "Load the target file to understand current content",
                    "Use writer skill to make the required changes",
                    "Verify the changes are correctly applied",
                ]
            )
        elif suggested_skill == "grep":
            steps.extend(
                [
                    "Execute grep to find relevant patterns",
                    "Analyze the search results",
                    "Report findings or take action based on results",
                ]
            )
        else:
            # Generic edit workflow
            steps.extend(
                [
                    "Read the target file(s)",
                    "Make the required changes",
                    "Verify the changes",
                ]
            )

        steps.append("Confirm task completion")

        plan_lines = ["- " + s for s in steps]
        return "PLAN:\n" + "\n".join(plan_lines)


async def create_adaptive_planner(client: Any | None = None) -> AdaptivePlanner:
    """Factory function to create an AdaptivePlanner instance.

    Args:
        client: Optional LLM client.

    Returns:
        Configured AdaptivePlanner instance.
    """
    return AdaptivePlanner(client=client)


__all__ = ["AdaptivePlanner", "create_adaptive_planner"]
