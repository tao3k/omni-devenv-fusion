"""
agent/core/orchestrator/feedback.py
Feedback Loop for Orchestrator.

Phase 15: Virtuous Cycle - Coder executes -> Reviewer audits -> Self-correction.
"""

from typing import Dict, Any, List

from agent.core.agents.base import AgentResult
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.telemetry import CostEstimator


async def execute_with_feedback_loop(
    self,
    user_query: str,
    worker,
    task_brief: str,
    constraints: List[str],
    relevant_files: List[str],
    history: List[Dict[str, Any]],
) -> str:
    """
    Execute with Phase 15 Feedback Loop and Phase 18 UX.

    The Virtuous Cycle:
    1. Execute CoderAgent
    2. Reviewer audits output
    3. If rejected: Retry with correction brief
    4. Repeat until approved or max retries

    Args:
        user_query: Original user request
        worker: CoderAgent instance
        task_brief: Mission Brief
        constraints: Task constraints
        relevant_files: Relevant files
        history: Conversation history

    Returns:
        Quality-assured response content
    """
    import structlog

    logger = structlog.get_logger(__name__)
    reviewer = ReviewerAgent()
    audit_history = []

    for attempt in range(1, self.max_retries + 1):
        # Phase 18: Show correction loop entry
        self.ux.show_correction_loop(attempt, self.max_retries)
        logger.bind(
            session_id=self._session_id,
            worker_name=worker.name,
            attempt=attempt,
            max_retries=self.max_retries,
        ).info("execution_attempt")

        # Phase 19: Log attempt start
        self.session.log(
            "agent_action",
            worker.name,
            f"Attempt {attempt} started",
            metadata={"attempt": attempt, "max_retries": self.max_retries},
        )

        # Step 1: Execute worker (Coder)
        try:
            self.ux.start_execution(worker.name)
            result: AgentResult = await worker.run(
                task=user_query,
                mission_brief=task_brief,
                constraints=constraints,
                relevant_files=relevant_files,
                chat_history=history,
            )
            self.ux.stop_execution()

            # Phase 18: Show RAG sources
            if result.rag_sources:
                self.ux.show_rag_hits(result.rag_sources)

            # Phase 18: Show agent response
            self.ux.print_agent_response(
                result.content, f"{worker.name.upper()} Output (Attempt {attempt})"
            )

            # Phase 19: Log agent output with cost
            agent_usage = CostEstimator.estimate(task_brief + user_query, result.content)
            self.session.log(
                "agent_action",
                worker.name,
                result.content,
                agent_usage,
                metadata={"attempt": attempt, "success": result.success},
            )

        except Exception as e:
            logger.bind(
                session_id=self._session_id,
                worker_name=worker.name,
                attempt=attempt,
                error=str(e),
            ).error("worker_execution_failed")
            self.ux.show_error("Worker execution failed", str(e))
            self.session.log("error", worker.name, str(e), metadata={"attempt": attempt})
            self.ux.end_task(success=False)
            return f"System Error during execution: {str(e)}"

        # Step 2: Reviewer audits output
        self.ux.start_review()
        logger.bind(session_id=self._session_id, attempt=attempt).debug("reviewer_auditing")
        audit_result = await reviewer.audit(
            task=user_query,
            agent_output=result.content,
            context={
                "constraints": constraints,
                "relevant_files": relevant_files,
                "attempt": attempt,
            },
        )

        # Phase 18: Show audit result
        self.ux.show_audit_result(
            approved=audit_result.approved,
            feedback=audit_result.feedback,
            issues=audit_result.issues_found,
            suggestions=audit_result.suggestions,
        )

        # Phase 19: Log audit result
        audit_entry = {
            "attempt": attempt,
            "approved": audit_result.approved,
            "feedback": audit_result.feedback,
            "issues": audit_result.issues_found,
            "suggestions": audit_result.suggestions,
        }
        audit_history.append(audit_entry)

        # Log audit to session
        self.session.log(
            "agent_action",
            "reviewer",
            f"Audit {'approved' if audit_result.approved else 'rejected'}",
            metadata=audit_entry,
        )

        # Step 3: Check if approved
        if audit_result.approved:
            logger.bind(
                session_id=self._session_id,
                confidence=audit_result.confidence,
                attempt=attempt,
            ).info("audit_passed")

            # Log full audit history for transparency
            logger.bind(session_id=self._session_id, audit_history=audit_history).debug(
                "audit_history"
            )

            self.ux.end_task(success=True)
            return result.content

        # Step 4: Self-correction loop
        logger.bind(
            session_id=self._session_id,
            issues=audit_result.issues_found[:3],
        ).warning("audit_failed_self_correction")

        # Build correction brief for retry
        correction_parts = [
            f"Previous attempt (attempt {attempt}) was rejected by quality review.",
            f"Issues found: {', '.join(audit_result.issues_found)}",
            f"Reviewer feedback: {audit_result.feedback}",
            "",
            "Original task: " + user_query,
            "",
            "Please fix the issues and provide corrected output.",
        ]

        if audit_result.suggestions:
            correction_parts.extend(
                [
                    "",
                    "Suggestions for improvement:",
                    *[f"- {s}" for s in audit_result.suggestions],
                ]
            )

        task_brief = "\n".join(correction_parts)

    # Max retries exceeded
    logger.bind(
        session_id=self._session_id,
        max_retries=self.max_retries,
        final_issues=audit_history[-1]["issues"],
    ).error("max_retries_exceeded")
    self.ux.show_error(
        f"Quality review failed after {self.max_retries} attempts",
        f"Audit issues: {', '.join(audit_history[-1]['issues'])}",
    )

    # Include audit history in final response for transparency
    warning_header = f"Quality review failed after {self.max_retries} attempts.\n"
    audit_summary = f"Audit issues: {', '.join(audit_history[-1]['issues'])}\n"
    last_feedback = audit_history[-1]["feedback"]

    self.ux.end_task(success=False)
    return f"{warning_header}{audit_summary}\nReviewer said: {last_feedback}\n\n{result.content}"


__all__ = ["execute_with_feedback_loop"]
