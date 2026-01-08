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

Phase 19 Enhancement:
- The Black Box: SessionManager for session persistence and telemetry
- Records all decisions, actions, and costs for traceability

Phase 33: ODF-EP v6.0 Core Refactoring

ODF-EP v6.0 Pillars:
- Pillar A: Pydantic Shield (ConfigDict(frozen=True))
- Pillar B: Protocol-Oriented Design (typing.Protocol)
- Pillar C: Tenacity Pattern (@retry for resilience)
- Pillar D: Context-Aware Observability (logger.bind())

Usage:
    from agent.core.orchestrator import Orchestrator, IOrchestrator

    orchestrator = Orchestrator(inference)
    response = await orchestrator.dispatch(user_query, history)
"""

from typing import Dict, Any, Optional, List, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agent.core.router import get_hive_router, AgentRoute
from agent.core.agents.base import BaseAgent, AgentResult, AuditResult
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.ux import get_ux_manager  # Phase 18: Glass Cockpit
from agent.core.session import SessionManager  # Phase 19: The Black Box
from agent.core.telemetry import CostEstimator  # Phase 19: Telemetry
from agent.core.state import (
    GraphState,
    StateCheckpointer,
    get_checkpointer,
    create_initial_state,
    merge_state,
)  # Phase 34: State Persistence

# =============================================================================
# Lazy Logger Initialization (Phase 32 Import Optimization)
# =============================================================================

_cached_logger = None


def _get_logger() -> Any:
    """Lazy logger initialization for fast imports."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Pydantic Shield DTOs (Pillar A)
# =============================================================================


class DispatchParams(BaseModel):
    """Parameters for dispatch operation."""

    model_config = ConfigDict(frozen=True)
    user_query: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class DispatchResult(BaseModel):
    """Result of dispatch operation."""

    model_config = ConfigDict(frozen=True)
    success: bool
    content: str
    agent_name: Optional[str] = None
    confidence: float = 0.0
    cost_usd: float = 0.0
    attempt_count: int = 1


class HiveContext(BaseModel):
    """Additional Hive context for dispatch."""

    model_config = ConfigDict(frozen=True)
    mission_brief: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    relevant_files: List[str] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    target_agent: Optional[str] = None


# =============================================================================
# IOrchestrator Protocol (Pillar B)
# =============================================================================


@runtime_checkable
class IOrchestrator(Protocol):
    """Protocol for orchestrator implementation."""

    @property
    def session(self) -> SessionManager:
        """Session manager for persistence."""

    @property
    def router(self) -> Any:
        """Hive router for agent delegation."""

    async def dispatch(
        self, user_query: str, history: List[Dict[str, Any]] = None, context: Dict[str, Any] = None
    ) -> str:
        """Dispatch user query to appropriate agent."""

    async def dispatch_with_hive_context(
        self, user_query: str, hive_context: Dict[str, Any]
    ) -> str:
        """Dispatch with additional Hive context."""


# =============================================================================
# Configuration Constants
# =============================================================================

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

    Phase 19: The Black Box:
    - SessionManager for session persistence and telemetry
    - Records all decisions, actions, and costs for traceability

    Phase 33: ODF-EP v6.0
    - Uses Pydantic Shield DTOs
    - Implements IOrchestrator Protocol
    - Context-aware logging with logger.bind()
    """

    def __init__(
        self,
        inference_engine=None,
        feedback_enabled: bool = DEFAULT_FEEDBACK_ENABLED,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session_id: Optional[str] = None,
        checkpointer: Optional[StateCheckpointer] = None,
    ):
        """
        Initialize Orchestrator.

        Phase 19: If no inference engine is provided, creates one automatically.
        Phase 19: SessionManager for persistence and cost tracking.
        Phase 34: StateCheckpointer for cross-session state persistence.

        Args:
            inference_engine: Optional inference engine for LLM calls
            feedback_enabled: Enable Phase 15 feedback loop (default: True)
            max_retries: Maximum self-correction retries (default: 2)
            session_id: Optional session ID for resumption
            checkpointer: Optional StateCheckpointer for state persistence
        """
        logger = _get_logger()

        # Phase 19: Auto-create inference client if not provided
        if inference_engine is None:
            try:
                from common.mcp_core.inference import InferenceClient

                inference_engine = InferenceClient()
                logger.info("inference_engine_initialized")
            except Exception as e:
                logger.bind(error=str(e)).warning("inference_engine_init_failed")

        self.inference = inference_engine
        self.router = get_hive_router()
        self.feedback_enabled = feedback_enabled
        self.max_retries = max_retries
        self.ux = get_ux_manager()  # Phase 18: Glass Cockpit

        # Phase 19: The Black Box - SessionManager for persistence and telemetry
        self.session = SessionManager(session_id=session_id)
        self._session_id = self.session.session_id

        # Phase 34: State Checkpointer for GraphState persistence
        self._checkpointer = checkpointer or get_checkpointer()
        self._load_state()

        # Agent Registry - Maps target_agent names to Agent classes
        self.agent_map: Dict[str, type] = {
            "coder": CoderAgent,
            "reviewer": ReviewerAgent,
            "orchestrator": None,  # Reserved for future general-purpose agent
        }

        logger.bind(
            session_id=self._session_id,
            feedback_enabled=feedback_enabled,
            max_retries=max_retries,
        ).debug("orchestrator_initialized")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=1.0, max=10.0),
        reraise=True,
    )
    async def dispatch(
        self, user_query: str, history: List[Dict[str, Any]] = None, context: Dict[str, Any] = None
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

        Phase 19: The Black Box logs:
        - User input to session
        - Routing decision with cost
        - Agent actions and outputs

        Phase 33: ODF-EP v6.0
        - Uses tenacity retry for resilience
        - Context-aware logging with logger.bind()

        Args:
            user_query: The user's request
            history: Conversation history
            context: Additional context (files, etc.)

        Returns:
            Agent's response content
        """
        logger = _get_logger()
        logger.bind(
            session_id=self._session_id,
            query_preview=user_query[:50],
        ).debug("dispatch_started")

        # Phase 18: Start task visualization
        self.ux.start_task(user_query)

        logger.bind(session_id=self._session_id).info("orchestrator_processing_request")

        # Phase 19: Log user input to session
        self.session.log("user", "user", user_query)

        # Phase 34: Update GraphState with user message
        self._update_state({"messages": [{"role": "user", "content": user_query}]})

        # === Phase 1: Hive Routing ===
        self.ux.start_routing()
        route = await self.router.route_to_agent(
            query=user_query, context=str(history) if history else "", use_cache=True
        )
        self.ux.stop_routing()

        # Phase 18: Show routing result
        self.ux.show_routing_result(
            agent_name=route.target_agent,
            mission_brief=route.task_brief or user_query,
            confidence=route.confidence,
            from_cache=route.from_cache,
        )

        # Phase 19: Log routing decision with cost estimate
        route_info = {
            "target_agent": route.target_agent,
            "task_brief": route.task_brief,
            "confidence": route.confidence,
            "constraints": route.constraints,
            "from_cache": route.from_cache,
        }
        usage = CostEstimator.estimate(user_query, str(route_info))
        self.session.log("router", "hive_router", route_info, usage)

        logger.bind(
            session_id=self._session_id,
            target_agent=route.target_agent,
            confidence=route.confidence,
            from_cache=route.from_cache,
        ).info("routing_decision")

        # === Phase 2: Agent Instantiation (Phase 19: Dependency Injection) ===
        target_agent_class = self.agent_map.get(route.target_agent)

        if not target_agent_class:
            logger.bind(
                session_id=self._session_id,
                requested_agent=route.target_agent,
            ).warning("no_specialized_agent_fallback")
            target_agent_class = CoderAgent

        # Create agent instance with injected dependencies
        tools = self._get_tools_for_agent(route.target_agent)
        worker: BaseAgent = target_agent_class(
            inference=self.inference,
            tools=tools,
        )

        logger.bind(
            session_id=self._session_id,
            agent_name=route.target_agent,
            tool_count=len(tools),
        ).debug("agent_instantiated")

        # === Phase 3: Execution with Mission Brief ===
        task_brief = route.task_brief or user_query

        logger.bind(
            session_id=self._session_id,
            agent_class=target_agent_class.name,
            brief_preview=task_brief[:50],
        ).debug("executing_agent")

        # Phase 15: Feedback Loop for Coder tasks
        if self.feedback_enabled and route.target_agent == "coder":
            return await self._execute_with_feedback_loop(
                user_query=user_query,
                worker=worker,
                task_brief=task_brief,
                constraints=route.constraints or [],
                relevant_files=route.relevant_files or [],
                history=history or [],
            )

        # Standard execution (non-feedback path)
        try:
            self.ux.start_execution(target_agent_class.name)
            result: AgentResult = await worker.run(
                task=user_query,
                mission_brief=task_brief,
                constraints=route.constraints or [],
                relevant_files=route.relevant_files or [],
                chat_history=history or [],
            )
            self.ux.stop_execution()

            # Phase 18: Show RAG sources
            if result.rag_sources:
                self.ux.show_rag_hits(result.rag_sources)

            # Phase 18: Show agent response
            self.ux.print_agent_response(
                result.content, f"{target_agent_class.name.upper()} Output"
            )

            # Phase 19: Log agent output
            agent_usage = CostEstimator.estimate(task_brief + user_query, result.content)
            self.session.log("agent_action", target_agent_class.name, result.content, agent_usage)

            # Phase 34: Update GraphState with agent response
            self._update_state({"messages": [{"role": "assistant", "content": result.content}]})

            logger.bind(
                session_id=self._session_id,
                agent_name=target_agent_class.name,
                success=result.success,
                confidence=result.confidence,
            ).info("agent_execution_complete")

            self.ux.end_task(success=result.success)
            return result.content

        except Exception as e:
            logger.bind(
                session_id=self._session_id,
                agent_name=target_agent_class.name,
                error=str(e),
            ).error("agent_execution_failed")
            self.ux.show_error("Agent execution failed", str(e))
            self.session.log("error", "orchestrator", str(e))
            self.ux.end_task(success=False)
            return f"System Error during execution: {str(e)}"

    async def _execute_with_feedback_loop(
        self,
        user_query: str,
        worker: BaseAgent,
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

        Phase 18: Visualizes each step with UXManager.
        Phase 19: Logs each attempt to the Black Box session.

        Phase 33: ODF-EP v6.0
        - Context-aware logging with logger.bind()

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
        logger = _get_logger()
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
            audit_result: AuditResult = await reviewer.audit(
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
        return (
            f"{warning_header}{audit_summary}\nReviewer said: {last_feedback}\n\n{result.content}"
        )

    async def dispatch_with_hive_context(
        self, user_query: str, hive_context: Dict[str, Any]
    ) -> str:
        """
        Dispatch with additional Hive context (from Orchestrator MCP).

        Phase 33: ODF-EP v6.0
        - Context-aware logging with logger.bind()

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
        logger = _get_logger()

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

            logger.bind(
                session_id=self._session_id,
                agent=explicit_agent,
                brief_preview=mission_brief[:50],
            ).info("direct_dispatch")

            try:
                result: AgentResult = await worker.run(
                    task=user_query,
                    mission_brief=mission_brief,
                    constraints=constraints,
                    relevant_files=relevant_files,
                    chat_history=history,
                )
                return result.content
            except Exception as e:
                logger.bind(
                    session_id=self._session_id,
                    agent=explicit_agent,
                    error=str(e),
                ).error("direct_dispatch_failed")
                return f"System Error: {str(e)}"

        # Fall back to normal routing
        return await self.dispatch(user_query, history)

    # =========================================================================
    # Phase 19: Tool Registry for Agent Dependency Injection
    # =========================================================================

    def _get_tools_for_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Get tools for a specific agent type.

        Phase 19: Maps skill tools to agent capabilities using the Skill Registry.

        Args:
            agent_name: Name of the agent (coder, reviewer, etc.)

        Returns:
            Dict of tool name -> callable function
        """
        from agent.core.registry import get_skill_tools

        # Get tools from loaded skills via Skill Registry
        tools = {}

        # Get filesystem skill tools
        fs_tools = get_skill_tools("filesystem")
        tools.update(fs_tools)

        # Get file_ops skill tools (may have additional tools)
        file_ops_tools = get_skill_tools("file_ops")
        tools.update(file_ops_tools)

        # Add agent-specific tools
        if agent_name == "coder":
            # Coder gets write_file (already included in filesystem tools)
            pass

        elif agent_name == "reviewer":
            # Reviewer gets git and testing tools from skill registry
            from agent.core.registry import get_skill_tools

            git_tools = get_skill_tools("git")
            testing_tools = get_skill_tools("testing")
            tools.update(git_tools)
            tools.update(testing_tools)

        return tools

    # =========================================================================
    # Phase 34: State Persistence
    # =========================================================================

    def _load_state(self) -> None:
        """Load GraphState from checkpointer on initialization."""
        logger = _get_logger()

        saved_state = self._checkpointer.get(self._session_id)
        if saved_state:
            self._state = saved_state
            logger.bind(
                session_id=self._session_id,
                message_count=len(saved_state["messages"]),
                current_plan=saved_state.get("current_plan", "")[:50],
            ).info("state_resumed_from_checkpoint")
        else:
            self._state = create_initial_state()
            logger.bind(session_id=self._session_id).info("state_initialized")

    def _save_state(self, force: bool = False) -> None:
        """Save GraphState to checkpointer."""
        self._checkpointer.put(self._session_id, self._state)

    def _update_state(self, updates: dict[str, Any]) -> None:
        """Update GraphState with new values."""
        self._state = merge_state(self._state, updates)
        self._save_state()

    def get_state(self) -> GraphState:
        """Get current GraphState."""
        return self._state

    def get_state_history(self, limit: int = 10) -> list[dict]:
        """Get checkpoint history for current session."""
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "timestamp": cp.timestamp,
                "state_keys": cp.state_keys,
                "size_bytes": cp.state_size_bytes,
            }
            for cp in self._checkpointer.get_history(self._session_id, limit)
        ]

    def get_status(self) -> Dict[str, Any]:
        """
        Get Orchestrator status for debugging/monitoring.

        Returns:
            Dict with status information
        """
        return {
            "router_loaded": self.router is not None,
            "agents_available": list(self.agent_map.keys()),
            "inference_configured": self.inference is not None,
            "session_id": self._session_id,
            "state_messages": len(self._state.get("messages", [])),
            "state_plan": self._state.get("current_plan", "")[:100],
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
            if user_input.lower() in ["exit", "quit", "q"]:
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
