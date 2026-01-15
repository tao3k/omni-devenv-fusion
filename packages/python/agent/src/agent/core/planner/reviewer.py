"""
 Cognitive Scaffolding - Reviewer

Reflexion/evaluation logic for task outcomes.
遵循 ODF-EP 标准:
- Type hints required
- Async-first
- Composition over inheritance
"""

import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agent.core.planner.schemas import Episode, Task, TaskStatus
from agent.core.planner.prompts import get_reflexion_prompt

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """Status of a task review."""

    CONTINUE = "continue"
    PIVOT = "pivot"
    COMPLETE = "complete"
    ABORT = "abort"


class ReviewResult(BaseModel):
    """Result of reviewing a task execution."""

    status: ReviewStatus = Field(..., description="Review decision")
    reflection: str = Field(..., description="Assessment of the task")
    next_action: str = Field(..., description="Recommended next step")
    issues: list[str] = Field(
        default_factory=list,
        description="Issues found during review",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this review",
    )


class Reviewer:
    """Reviews task execution and provides reflexion.

    The Reviewer evaluates:
    1. Goal Achievement: Did we accomplish what we set out to do?
    2. Code Quality: Did we maintain or improve code quality?
    3. Side Effects: Did we introduce any bugs or regressions?
    4. Next Steps: Should we continue, pivot, or stop?

    Attributes:
        inference_client: Client for LLM-based review.
        model: LLM model for reflexion.
    """

    def __init__(
        self,
        inference_client: Any | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        """Initialize the Reviewer.

        Args:
            inference_client: Optional LLM client for complex reviews.
            model: LLM model for reflexion.
        """
        self.inference_client = inference_client
        self.model = model

    async def review_task(
        self,
        task: Task,
        result: str,
        output: Any,
    ) -> ReviewResult:
        """Review a completed task.

        Args:
            task: The task that was executed.
            result: Result description of the execution.
            output: Actual output from tools.

        Returns:
            ReviewResult with assessment and recommendation.
        """
        logger.info(f"Reviewing task {task.id}")

        if self.inference_client:
            return await self._llm_review(task, result, output)

        return self._rule_based_review(task, result, output)

    async def _llm_review(
        self,
        task: Task,
        result: str,
        output: Any,
    ) -> ReviewResult:
        """Perform LLM-based review.

        Args:
            task: The task that was executed.
            result: Result description.
            output: Actual output from tools.

        Returns:
            ReviewResult from LLM assessment.
        """
        prompt = get_reflexion_prompt(
            task_goal=task.description,
            task_result=result,
            task_output=str(output),
        )

        try:
            response = await self.inference_client.complete(
                model=self.model,
                system=REFLEXION_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=1024,
                temperature=0.3,
            )

            return self._parse_review_response(response)

        except Exception as e:
            logger.error(f"LLM review failed: {e}")
            return self._rule_based_review(task, result, output)

    def _parse_review_response(self, response: str) -> ReviewResult:
        """Parse LLM response into ReviewResult.

        Args:
            response: LLM response text.

        Returns:
            Parsed ReviewResult.
        """
        try:
            data = json.loads(response)
            return ReviewResult(
                status=ReviewStatus(data.get("status", "continue")),
                reflection=data.get("reflection", ""),
                next_action=data.get("next_action", ""),
                issues=data.get("issues", []),
                confidence=0.7,
            )
        except json.JSONDecodeError:
            return ReviewResult(
                status=ReviewStatus.CONTINUE,
                reflection="Could not parse LLM response",
                next_action="Continue with plan execution",
                issues=["Failed to parse review response"],
                confidence=0.3,
            )

    def _rule_based_review(
        self,
        task: Task,
        result: str,
        output: Any,
    ) -> ReviewResult:
        """Perform rule-based review without LLM.

        Args:
            task: The task that was executed.
            result: Result description.
            output: Actual output from tools.

        Returns:
            ReviewResult based on simple rules.
        """
        issues: list[str] = []
        success = result.lower() in ("success", "completed", "true")

        if not success:
            issues.append(f"Task reported failure: {result}")

        if "error" in str(output).lower():
            issues.append("Error detected in output")

        if "exception" in str(output).lower():
            issues.append("Exception detected in output")

        if task.status == TaskStatus.FAILED:
            status = ReviewStatus.PIVOT
            reflection = f"Task {task.id} failed - revision needed"
            next_action = "Revise plan and retry"
        elif issues:
            status = ReviewStatus.CONTINUE
            reflection = "Task completed with warnings"
            next_action = "Address issues and continue"
        else:
            status = ReviewStatus.CONTINUE
            reflection = f"Task {task.id} completed successfully"
            next_action = "Proceed to next task"

        return ReviewResult(
            status=status,
            reflection=reflection,
            next_action=next_action,
            issues=issues,
            confidence=0.8,
        )

    async def review_episode(self, episode: Episode) -> ReviewResult:
        """Review a completed episode.

        Args:
            episode: The episode to review.

        Returns:
            ReviewResult for the episode.
        """
        return await self.review_task(
            task=Task(
                id=episode.task_id,
                description=episode.goal,
                status=TaskStatus.COMPLETED,
            ),
            result=episode.reflection or "Completed",
            output=episode.results,
        )

    def should_retry(self, review: ReviewResult) -> bool:
        """Determine if a task should be retried.

        Args:
            review: The review result.

        Returns:
            True if retry is recommended.
        """
        return review.status in (ReviewStatus.PIVOT, ReviewStatus.CONTINUE) and any(
            "retry" in issue.lower() or "failed" in issue.lower() for issue in review.issues
        )


# =============================================================================
# Polyfactory for Testing
# =============================================================================


def create_reviewer(
    inference_client: Any | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> Reviewer:
    """Factory function to create a Reviewer.

    Args:
        inference_client: Optional LLM client for reviews.
        model: LLM model for reflexion.

    Returns:
        Configured Reviewer instance.
    """
    return Reviewer(
        inference_client=inference_client,
        model=model,
    )


# =============================================================================
# Reflexion Prompt Template
# =============================================================================

REFLEXION_SYSTEM_PROMPT = """You are a task reviewer. After each major step, you evaluate:
1. Did we achieve the task goal?
2. Did we introduce any issues?
3. Should we continue, revise the plan, or stop?

## Review Criteria
- Goal Achievement: Did we accomplish what we set out to do?
- Code Quality: Did we maintain or improve code quality?
- Side Effects: Did we introduce any bugs or regressions?
- Next Steps: Should we continue, pivot, or stop?

## Output Format
Return JSON with:
- status: "continue" | "pivot" | "complete" | "abort"
- reflection: Brief assessment of what happened
- next_action: Recommended next step
- issues: List of any issues found"""
