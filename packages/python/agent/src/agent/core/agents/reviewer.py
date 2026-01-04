"""
src/agent/core/agents/reviewer.py
Reviewer Agent - Quality Gatekeeper for Code Review.

Phase 14 Enhancement:
- Context Narrowing: Reviewer only sees quality-related tools
- Mission Brief: Focused on review, testing, and commit decisions

Phase 15 Enhancement:
- audit(): Auto-review other agents' output (Feedback Loop)

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

    # Phase 15: Audit Coder's output
    audit = await agent.audit(task, coder_response)
"""
from typing import Any, Dict, List, Optional

from agent.core.agents.base import BaseAgent, AgentResult, AuditResult


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

    async def audit(
        self,
        task: str,
        agent_output: str,
        context: Dict[str, Any] = None
    ) -> AuditResult:
        """
        Phase 15: Audit another agent's output (Feedback Loop).

        This is the core of the Virtuous Cycle - Reviewer checks Coder's work
        before it's returned to the user.

        Args:
            task: The original task description
            agent_output: The output from the executing agent (Coder)
            context: Additional context (relevant files, etc.)

        Returns:
            AuditResult with approval status and feedback

        Usage:
            reviewer = ReviewerAgent()
            audit = await reviewer.audit(
                task="Fix the bug in router.py",
                agent_output="Fixed the IndexError by adding bounds check"
            )

            if audit.approved:
                print("✅ Approved!")
            else:
                print(f"❌ Rejected: {audit.feedback}")
        """
        # Build audit system prompt
        audit_prompt = self._build_audit_prompt(task, agent_output, context)

        # Log audit start
        print(f"[reviewer] 🕵️ Starting audit for: {task[:50]}...")

        # Placeholder: In real implementation, call LLM with audit_prompt
        # For now, simulate basic validation

        # Simulate LLM-based audit result
        approved = True
        feedback = ""
        issues_found = []
        suggestions = []

        # Basic validation checks
        if not agent_output or len(agent_output.strip()) == 0:
            approved = False
            feedback = "Output is empty or missing."
            issues_found.append("empty_output")
        elif len(agent_output) < 10:
            approved = False
            feedback = "Output is suspiciously short. Did the agent complete the task?"
            issues_found.append("short_output")
        else:
            # Simulate successful audit
            approved = True
            feedback = "Output meets quality standards."
            suggestions.append("Consider adding comments for complex logic.")

        # Placeholder: In production, this would be:
        # result = await self.inference.chat(
        #     query=f"Audit this output: {agent_output}",
        #     system_prompt=audit_prompt
        # )

        result = AuditResult(
            approved=approved,
            feedback=feedback,
            confidence=0.85 if approved else 0.6,
            issues_found=issues_found,
            suggestions=suggestions
        )

        print(f"[reviewer] ✅ Audit complete: approved={approved}")

        return result

    def _build_audit_prompt(
        self,
        task: str,
        agent_output: str,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Build the audit system prompt for quality review.

        Phase 15: This is where quality gates are enforced.
        """
        prompt_parts = [
            "# ROLE: Quality Assurance Lead",
            "",
            "You are auditing the output of another specialized agent.",
            "",
            "## ORIGINAL TASK",
            "=" * 50,
            task,
            "=" * 50,
            "",
            "## AGENT OUTPUT TO AUDIT",
            "=" * 50,
            agent_output[:2000],  # Truncate for context limit
            "=" * 50,
            "",
            "## AUDIT CRITERIA",
            "1. **Completeness**: Does it solve the user's request?",
            "2. **Correctness**: Is the solution logically sound?",
            "3. **Safety**: Are there any obvious bugs or security issues?",
            "4. **Quality**: Is the code idiomatic and well-structured?",
            "",
            "## OUTPUT FORMAT",
            "Return a JSON object with:",
            "- approved: boolean (true if output meets standards)",
            "- feedback: string (constructive criticism or praise)",
            "- issues_found: list of specific issues",
            "- suggestions: list of improvements",
        ]

        return "\n".join(prompt_parts)
