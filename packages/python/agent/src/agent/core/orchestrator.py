"""
src/agent/core/orchestrator.py
Orchestrator - The Central Switchboard.

Phase 14 Enhancement:
- Coordinates flow between User -> Router -> Specialized Agents
- Handles dispatch, context injection, and execution lifecycle

Phase 15 Enhancement:
- Feedback Loop: Coder executes → Reviewer audits → Self-correction if needed
- Virtuous Cycle ensures quality output before returning to user

Phase 18 Enhancement:
- Glass Cockpit: UXManager for real-time TUI visualization
- Shows routing, RAG knowledge, and audit results beautifully

Usage:
    from agent.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(inference)
    response = await orchestrator.dispatch(user_query, history)
"""
import structlog
from typing import Dict, Any, Optional, List

from agent.core.router import get_hive_router, AgentRoute
from agent.core.agents.base import BaseAgent, AgentResult, AuditResult
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.ux import get_ux_manager  # Phase 18: Glass Cockpit

logger = structlog.get_logger()

# Phase 15: Feedback Loop Configuration
DEFAULT_MAX_RETRIES = 2
DEFAULT_FEEDBACK_ENABLED = True


class Orchestrator:
    """
    The Central Switchboard.
    Coordinates the flow between User -> Router -> Specialized Agents.

    Phase 15: Implements the Virtuous Cycle (Feedback Loop):
    1. Route: Consult HiveRouter for agent delegation
    2. Execute: Worker agent runs with Mission Brief
    3. Audit: Reviewer checks output (for Coder tasks)
    4. Self-Correct: Retry with feedback if audit fails
    5. Return: Quality-assured result to user

    Phase 18: Glass Cockpit Integration:
    - Uses UXManager for beautiful terminal visualization
    - Shows routing, RAG knowledge, and audit results in real-time
    """

    def __init__(self, inference_engine=None, feedback_enabled: bool = DEFAULT_FEEDBACK_ENABLED, max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Initialize Orchestrator.

        Args:
            inference_engine: Optional inference engine for LLM calls
            feedback_enabled: Enable Phase 15 feedback loop (default: True)
            max_retries: Maximum self-correction retries (default: 2)
        """
        self.inference = inference_engine
        self.router = get_hive_router()
        self.feedback_enabled = feedback_enabled
        self.max_retries = max_retries
        self.ux = get_ux_manager()  # Phase 18: Glass Cockpit

        # Agent Registry - Maps target_agent names to Agent classes
        self.agent_map: Dict[str, type] = {
            "coder": CoderAgent,
            "reviewer": ReviewerAgent,
            "orchestrator": None,  # Reserved for future general-purpose agent
        }

    async def dispatch(
        self,
        user_query: str,
        history: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Main Dispatch Loop with Phase 15 Feedback Loop and Phase 18 UX.

        Phase 15 Flow:
        1. Route request to appropriate agent
        2. Execute worker (Coder/Reviewer)
        3. If Coder: Reviewer audits output
        4. If audit fails: Retry with correction brief
        5. Return quality-assured result

        Phase 18: Glass Cockpit shows:
        - User query in a panel
        - Routing decision with mission brief
        - RAG knowledge hits
        - Execution progress
        - Audit results

        Args:
            user_query: The user's request
            history: Conversation history
            context: Additional context (files, etc.)

        Returns:
            Agent's response content
        """
        # Phase 18: Start task visualization
        self.ux.start_task(user_query)

        logger.info("🎹 Orchestrator processing request", query=user_query[:80])

        # === Phase 1: Hive Routing ===
        self.ux.start_routing()
        route = await self.router.route_to_agent(
            query=user_query,
            context=str(history) if history else "",
            use_cache=True
        )
        self.ux.stop_routing()

        # Phase 18: Show routing result
        self.ux.show_routing_result(
            agent_name=route.target_agent,
            mission_brief=route.task_brief or user_query,
            confidence=route.confidence,
            from_cache=route.from_cache
        )

        logger.info(
            "👉 Routing decision",
            target_agent=route.target_agent,
            confidence=route.confidence
        )

        # === Phase 2: Agent Instantiation ===
        target_agent_class = self.agent_map.get(route.target_agent)

        if not target_agent_class:
            logger.warning(
                f"⚠️ No specialized agent for '{route.target_agent}', "
                f"falling back to Coder"
            )
            target_agent_class = CoderAgent

        # Create agent instance
        worker: BaseAgent = target_agent_class()

        # === Phase 3: Execution with Mission Brief ===
        task_brief = route.task_brief or user_query

        logger.info(
            f"🚀 Executing with {target_agent_class.name.upper()}",
            brief=task_brief[:80]
        )

        # Phase 15: Feedback Loop for Coder tasks
        if self.feedback_enabled and route.target_agent == "coder":
            return await self._execute_with_feedback_loop(
                user_query=user_query,
                worker=worker,
                task_brief=task_brief,
                constraints=route.constraints or [],
                relevant_files=route.relevant_files or [],
                history=history or []
            )

        # Standard execution (non-feedback path)
        try:
            self.ux.start_execution(target_agent_class.name)
            result: AgentResult = await worker.run(
                task=user_query,
                mission_brief=task_brief,
                constraints=route.constraints or [],
                relevant_files=route.relevant_files or [],
                chat_history=history or []
            )
            self.ux.stop_execution()

            # Phase 18: Show RAG sources
            if result.rag_sources:
                self.ux.show_rag_hits(result.rag_sources)

            # Phase 18: Show agent response
            self.ux.print_agent_response(result.content, f"{target_agent_class.name.upper()} Output")

            logger.info(
                f"✅ {target_agent_class.name.upper()} complete",
                success=result.success,
                confidence=result.confidence
            )

            self.ux.end_task(success=result.success)
            return result.content

        except Exception as e:
            self.ux.show_error("Agent execution failed", str(e))
            logger.error("❌ Agent execution failed", error=str(e))
            self.ux.end_task(success=False)
            return f"System Error during execution: {str(e)}"

    async def _execute_with_feedback_loop(
        self,
        user_query: str,
        worker: BaseAgent,
        task_brief: str,
        constraints: List[str],
        relevant_files: List[str],
        history: List[Dict[str, Any]]
    ) -> str:
        """
        Execute with Phase 15 Feedback Loop and Phase 18 UX.

        The Virtuous Cycle:
        1. Execute CoderAgent
        2. Reviewer audits output
        3. If rejected: Retry with correction brief
        4. Repeat until approved or max retries

        Phase 18: Visualizes each step with UXManager.

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
        reviewer = ReviewerAgent()
        audit_history = []

        for attempt in range(1, self.max_retries + 1):
            # Phase 18: Show correction loop entry
            self.ux.show_correction_loop(attempt, self.max_retries)
            logger.info(f"🔄 Execution attempt {attempt}/{self.max_retries}")

            # Step 1: Execute worker (Coder)
            try:
                self.ux.start_execution(worker.name)
                result: AgentResult = await worker.run(
                    task=user_query,
                    mission_brief=task_brief,
                    constraints=constraints,
                    relevant_files=relevant_files,
                    chat_history=history
                )
                self.ux.stop_execution()

                # Phase 18: Show RAG sources
                if result.rag_sources:
                    self.ux.show_rag_hits(result.rag_sources)

                # Phase 18: Show agent response
                self.ux.print_agent_response(result.content, f"{worker.name.upper()} Output (Attempt {attempt})")

            except Exception as e:
                self.ux.show_error("Worker execution failed", str(e))
                logger.error("❌ Worker execution failed", error=str(e))
                self.ux.end_task(success=False)
                return f"System Error during execution: {str(e)}"

            # Step 2: Reviewer audits output
            self.ux.start_review()
            logger.info("🕵️ Reviewer auditing output...")
            audit_result: AuditResult = await reviewer.audit(
                task=user_query,
                agent_output=result.content,
                context={
                    "constraints": constraints,
                    "relevant_files": relevant_files,
                    "attempt": attempt
                }
            )

            # Phase 18: Show audit result
            self.ux.show_audit_result(
                approved=audit_result.approved,
                feedback=audit_result.feedback,
                issues=audit_result.issues_found,
                suggestions=audit_result.suggestions
            )

            audit_entry = {
                "attempt": attempt,
                "approved": audit_result.approved,
                "feedback": audit_result.feedback,
                "issues": audit_result.issues_found,
                "suggestions": audit_result.suggestions
            }
            audit_history.append(audit_entry)

            # Step 3: Check if approved
            if audit_result.approved:
                logger.info(
                    "✅ Audit passed",
                    confidence=audit_result.confidence,
                    attempt=attempt
                )

                # Log full audit history for transparency
                logger.debug("Audit history", audits=audit_history)

                self.ux.end_task(success=True)
                return result.content

            # Step 4: Self-correction loop
            logger.info(
                "⚠️ Audit failed, initiating self-correction",
                issues=audit_result.issues_found[:3]  # Log first 3 issues
            )

            # Build correction brief for retry
            correction_parts = [
                f"Previous attempt (attempt {attempt}) was rejected by quality review.",
                f"Issues found: {', '.join(audit_result.issues_found)}",
                f"Reviewer feedback: {audit_result.feedback}",
                "",
                "Original task: " + user_query,
                "",
                "Please fix the issues and provide corrected output."
            ]

            if audit_result.suggestions:
                correction_parts.extend([
                    "",
                    "Suggestions for improvement:",
                    * [f"- {s}" for s in audit_result.suggestions]
                ])

            task_brief = "\n".join(correction_parts)

        # Max retries exceeded
        logger.error("❌ Max retries exceeded, returning last result with warnings")
        self.ux.show_error(
            f"Quality review failed after {self.max_retries} attempts",
            f"Audit issues: {', '.join(audit_history[-1]['issues'])}"
        )

        # Include audit history in final response for transparency
        warning_header = f"⚠️ Quality review failed after {self.max_retries} attempts.\n"
        audit_summary = f"Audit issues: {', '.join(audit_history[-1]['issues'])}\n"
        last_feedback = audit_history[-1]['feedback']

        self.ux.end_task(success=False)
        return f"{warning_header}{audit_summary}\nReviewer said: {last_feedback}\n\n{result.content}"

    async def dispatch_with_hive_context(
        self,
        user_query: str,
        hive_context: Dict[str, Any]
    ) -> str:
        """
        Dispatch with additional Hive context (from Orchestrator MCP).

        Args:
            user_query: The user's request
            hive_context: Additional context from Orchestrator MCP tools
                - mission_brief: Commander's Intent
                - constraints: List of constraints
                - relevant_files: Files to work with
                - history: Conversation history

        Returns:
            Agent's response content
        """
        # Extract context fields
        mission_brief = hive_context.get("mission_brief", user_query)
        constraints = hive_context.get("constraints", [])
        relevant_files = hive_context.get("relevant_files", [])
        history = hive_context.get("history", [])

        # Determine target agent from context or route
        explicit_agent = hive_context.get("target_agent")
        if explicit_agent and explicit_agent in self.agent_map:
            target_agent_class = self.agent_map[explicit_agent]
            worker = target_agent_class()

            logger.info(
                f"🚀 Direct dispatch to {explicit_agent.upper()}",
                brief=mission_brief[:80]
            )

            try:
                result: AgentResult = await worker.run(
                    task=user_query,
                    mission_brief=mission_brief,
                    constraints=constraints,
                    relevant_files=relevant_files,
                    chat_history=history
                )
                return result.content
            except Exception as e:
                logger.error("❌ Direct dispatch failed", error=str(e))
                return f"System Error: {str(e)}"

        # Fall back to normal routing
        return await self.dispatch(user_query, history)

    def get_status(self) -> Dict[str, Any]:
        """
        Get Orchestrator status for debugging/monitoring.

        Returns:
            Dict with status information
        """
        return {
            "router_loaded": self.router is not None,
            "agents_available": list(self.agent_map.keys()),
            "inference_configured": self.inference is not None
        }


async def orchestrator_main():
    """
    CLI entry point for testing Orchestrator.
    """
    from rich.console import Console
    console = Console()

    console.print("🎯 Omni Agentic OS - Orchestrator Mode")
    console.print("=" * 50)

    orchestrator = Orchestrator()

    history = []

    while True:
        try:
            user_input = input("\n🎤 You: ")
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("👋 Goodbye!")
                break

            response = await orchestrator.dispatch(user_input, history)

            console.print(f"\n🤖 Agent: {response}")

            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            # Keep history manageable
            if len(history) > 20:
                history = history[-20:]

        except KeyboardInterrupt:
            console.print("\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ Error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(orchestrator_main())
