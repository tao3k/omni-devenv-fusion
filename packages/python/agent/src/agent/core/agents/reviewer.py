"""
src/agent/core/agents/reviewer.py
Reviewer Agent - Quality Gatekeeper for Code Review.

Phase 14 Enhancement:
- Context Narrowing: Reviewer only sees quality-related tools
- Mission Brief: Focused on review, testing, and commit decisions

Skills (Narrow Context):
- git: View diffs, check status, create commits
- testing: Run pytest and analyze results
- documentation: Verify docs are updated
- linter: Run code quality checks

Usage:
    from agent.core.agents import ReviewerAgent

    agent = ReviewerAgent()
    result = await agent.run(
        task="Review the changes in router.py",
        mission_brief="Review the changes. If tests pass and lint is clean, commit with message 'fix(router): ...'",
        constraints=["Run tests", "Check lint", "Verify docs updated"],
        relevant_files=["packages/python/agent/src/agent/core/router.py"]
    )
"""
from typing import List

from agent.core.agents.base import BaseAgent


class ReviewerAgent(BaseAgent):
    """
    Quality Gatekeeper Agent - Specializes in code review and quality assurance.

    The Reviewer focuses on:
    - Code review and feedback
    - Running tests
    - Lint and format checks
    - Commit decisions
    - Documentation verification

    Reviewer does NOT have access to:
    - File modification (use CoderAgent)
    - File content reading (limited scope)
    """

    name = "reviewer"
    role = "Quality Assurance Lead"
    description = "Quality gatekeeper for code review, testing, and commits"

    # ✅ Narrow Context: Only quality/QA-related skills
    default_skills = [
        "git",              # View diffs, check status, create commits
        "testing",          # Run pytest and analyze results
        "documentation",    # Verify docs are updated
        "linter",           # Run code quality checks
        "terminal",         # Run verification commands
    ]

    async def run(
        self,
        task: str,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        chat_history: List[dict] = None
    ) -> dict:
        """
        Execute review task with Mission Brief.

        Reviewer-specific enhancements:
        - Automatically adds review standards to constraints
        - Prefers commit-ready verification
        """
        # Add default review constraints if not present
        if constraints is None:
            constraints = []
        review_constraints = [
            "Check code quality and style",
            "Run tests to verify functionality",
            "Ensure changes are properly documented"
        ]
        for c in review_constraints:
            if c.lower() not in " ".join(constraints).lower():
                constraints.append(c)

        return await super().run(
            task=task,
            mission_brief=mission_brief,
            constraints=constraints,
            relevant_files=relevant_files,
            chat_history=chat_history
        )

    async def _execute_with_llm(
        self,
        task: str,
        context,
        history: List[dict]
    ) -> dict:
        """
        Execute review task with LLM.

        Reviewer-specific behavior:
        - Provides detailed review feedback
        - Makes commit recommendations
        - Reports test results clearly
        """
        # Placeholder for actual LLM integration
        # In real implementation: call inference.chat with context.system_prompt

        return {
            "success": True,
            "content": f"[REVIEWER] Reviewed: {task}",
            "message": f"Reviewer completed quality check",
            "confidence": 0.9,
            "tool_calls": [],
            "tests_passed": True,
            "lint_clean": True,
            "review_notes": []
        }

    async def should_commit(self, diff: str) -> dict:
        """
        Analyze diff and recommend commit action.

        Args:
            diff: Git diff output

        Returns:
            Dict with commit recommendation and reasoning
        """
        # In real implementation: analyze diff with LLM
        return {
            "should_commit": True,
            "message": "Changes look good for commit",
            "confidence": 0.85,
            "suggested_message": "feat(core): implement agent review"
        }
