"""
simple.py - Adaptive Planner for OmniLoop (Optimized).

Provides lightweight task estimation and initial planning without the full weight of the heavy planner.
Optimized for efficiency: fewer steps, faster planning, avoid repeated reads.
"""

from __future__ import annotations

import re
from typing import Any, Tuple

import structlog

logger = structlog.get_logger(__name__)


class AdaptivePlanner:
    """
    Lightweight adaptive planner that estimates task complexity and generates initial plans.

    Optimized for speed:
    - Aggressive step limits for simple tasks
    - Explicit rules against repeated file reads
    - Force writer skill for text editing
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
            Estimated number of steps (optimized for efficiency).
        """
        task_lower = task.lower()

        # Base complexity detection - optimized for common tasks
        if any(kw in task_lower for kw in ["analyze", "list", "find", "show", "get"]):
            base_steps = 2
        elif any(
            kw in task_lower
            for kw in ["edit", "update", "change", "modify", "replace", "fix", "check"]
        ):
            base_steps = 3  # Reduced from 4: Read -> Edit -> Verify
        elif any(kw in task_lower for kw in ["create", "add", "implement", "write"]):
            base_steps = 4
        elif any(kw in task_lower for kw in ["refactor", "restructure", "migrate"]):
            base_steps = 6
        elif any(kw in task_lower for kw in ["debug", "troubleshoot", "investigate"]):
            base_steps = 5
        else:
            base_steps = 2

        # Multi-file indicator
        if any(kw in task_lower for kw in ["all", "every", "multiple", "across", "project-wide"]):
            base_steps += 2

        # Safety buffer - reduced from +2 to +1
        estimated_steps = base_steps + 1

        # Hard cap for single-file simple tasks (query/edit), not complex tasks
        if "all" not in task_lower and "multiple" not in task_lower and "every" not in task_lower:
            # Only cap simple tasks, not refactor/debug/create
            if base_steps <= 4:  # Simple tasks only
                estimated_steps = min(estimated_steps, 5)

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
                "style",
                "lint",
                "grammar",
                "typo",
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

        Action-Enforced Prompt: forces execution, forbids read loops.

        Args:
            task: The user's task description.
            suggested_skill: The skill suggested for this task.

        Returns:
            Generated plan text with explicit action steps.
        """
        skill_hint = f"\n- Suggested skill: {suggested_skill}" if suggested_skill else ""

        # Action-enforced prompt
        prompt = f"""You are the Execution Commander.

Task: "{task}"{skill_hint}

CRITICAL RULES:
1. **NO READ LOOPS**: Reading a file ONCE is enough. Content stays in your context history.
2. **ACTION BIAS**: If task says "fix", "update", "change", "edit" -> you MUST plan a WRITING step.
3. **TOOL EXPLICITNESS**: Name the tool to use (e.g., 'writer.replace', 'filesystem.apply_changes').

PLAN FORMAT (Strict):
- Step 1: Read file (once max)
- Step 2: Use WRITER tool to make changes <- REQUIRED for edit/fix tasks
- Step 3: Verify completion

Example for "Fix README style":
- Read README.md to identify style issues
- Use 'writer.replace' to apply style fixes
- Verify changes are applied

Output STRICTLY as:
STEPS: <number>
PLAN:
- <step 1>
...
"""

        try:
            response = await self._client.complete(
                system_prompt="You are a pragmatic Tech Lead. You hate hesitation. Force action.",
                user_query=prompt,
                max_tokens=300,
            )
            content = response.get("content", "").strip()

            # Parse the response
            steps_match = re.search(r"STEPS:\s*(\d+)", content, re.IGNORECASE)
            if steps_match:
                parsed_steps = int(steps_match.group(1))
                estimated = max(self.estimate_steps(task), parsed_steps)
                # Cap at 5 for simple tasks only
                if "all" not in task.lower() and "multiple" not in task.lower():
                    if self.estimate_steps(task) <= 4:
                        estimated = min(estimated, 5)
            else:
                estimated = self.estimate_steps(task)

            plan_match = re.search(r"(PLAN:.*)", content, re.IGNORECASE | re.DOTALL)
            if plan_match:
                plan = plan_match.group(1).strip()
            else:
                plan = content

            # Force minimum 3 steps for fix/edit tasks (Read -> Write -> Verify)
            if any(
                w in task.lower() for w in ["fix", "update", "change", "edit", "replace", "modify"]
            ):
                estimated = max(estimated, 3)

            logger.info(
                "AdaptivePlanner: Action-oriented plan generated", estimated_steps=estimated
            )
            return plan

        except Exception as e:
            logger.warning(f"AdaptivePlanner: LLM planning error: {e}")
            return self._fallback_plan(task, suggested_skill)

    def _fallback_plan(self, task: str, suggested_skill: str | None) -> str:
        """Generate a fallback plan without LLM.

        Optimized for efficiency: minimal steps, explicit tool usage.

        Args:
            task: The user's task description.
            suggested_skill: The skill suggested for this task.

        Returns:
            Fallback plan text.
        """
        task_lower = task.lower()
        steps = []

        # Optimized workflow
        if suggested_skill == "writer":
            steps.extend(
                [
                    "Read target file ONCE (content stays in context)",
                    "Use writer.replace to make changes",
                    "Verify changes applied correctly",
                ]
            )
        elif suggested_skill == "grep":
            steps.extend(
                [
                    "Execute grep to find patterns",
                    "Analyze results",
                    "Report findings",
                ]
            )
        else:
            # Generic workflow - optimized
            steps.append("Read target file (once is enough)")
            steps.append("Make required changes")
            steps.append("Verify changes")

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
