"""
agent/core/orchestrator/core.py
Orchestrator - The Central Switchboard.

Coordinates flow between User -> Router -> Specialized Agents
Implements Virtuous Cycle (Feedback Loop)
Glass Cockpit Integration
The Black Box (SessionManager)
ODF-EP v6.0 Core Refactoring
LangGraph Cognitive Graph (opt-in)

Usage:
    from agent.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(inference)
    response = await orchestrator.dispatch(user_query, history)
"""

from typing import Dict, Any, Optional, List

from tenacity import retry, stop_after_attempt, wait_exponential

from agent.core.router import get_hive_router
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.ux import get_ux_manager
from agent.core.session import SessionManager
from agent.core.state import get_checkpointer, create_initial_state
from agent.core.graph import get_graph, OmniGraph

# Dynamic Workflow imports
from agent.core.skill_runtime import SkillManager
from agent.core.orchestrator.builder import DynamicGraphBuilder
from agent.core.planner.planner import Planner

# Lazy Logger Initialization
_cached_logger = None


def _get_logger() -> Any:
    """Lazy logger initialization for fast imports."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# Import from sub-modules
from agent.core.orchestrator.config import DEFAULT_MAX_RETRIES, DEFAULT_FEEDBACK_ENABLED
from agent.core.orchestrator.dispatch import dispatch_standard, dispatch_with_hive_context
from agent.core.orchestrator.feedback import execute_with_feedback_loop
from agent.core.orchestrator.tools import get_tools_for_agent
from agent.core.orchestrator.state import (
    load_state,
    save_state,
    update_state,
    get_state,
    get_state_history,
    get_status,
)
from agent.core.orchestrator.graph import dispatch_graph_mode


class Orchestrator:
    """
    The Central Switchboard.
    Coordinates the flow between User -> Router -> Specialized Agents.

    Implements the Virtuous Cycle (Feedback Loop):
    1. Route: Consult HiveRouter for agent delegation
    2. Execute: Worker agent runs with Mission Brief
    3. Audit: Reviewer checks output (for Coder tasks)
    4. Self-Correct: Retry with feedback if audit fails
    5. Return: Quality-assured result to user

    Glass Cockpit Integration:
    - Uses UXManager for beautiful terminal visualization
    - Shows routing, RAG knowledge, and audit results in real-time

    The Black Box:
    - SessionManager for session persistence and telemetry
    - Records all decisions, actions, and costs for traceability

    ODF-EP v6.0
    - Uses Pydantic Shield DTOs
    - Context-aware logging with logger.bind()

    LangGraph Cognitive Graph (opt-in)
    - Replaces procedural loop with state machine

    Dynamic Workflow Builder
    - WorkflowArchitect generates blueprints from goals
    - DynamicGraphBuilder compiles graphs at runtime
    - dispatch_dynamic() enables intent-to-execution flow
    """

    def __init__(
        self,
        inference_engine=None,
        feedback_enabled: bool = DEFAULT_FEEDBACK_ENABLED,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session_id: Optional[str] = None,
        checkpointer=None,
        use_graph_mode: bool = False,
    ):
        """
        Initialize Orchestrator.

        Args:
            inference_engine: Optional inference engine for LLM calls
            feedback_enabled: Enable feedback loop (default: True)
            max_retries: Maximum self-correction retries (default: 2)
            session_id: Optional session ID for resumption
            checkpointer: Optional StateCheckpointer for state persistence
            use_graph_mode: Enable LangGraph cognitive graph (default: False)
        """
        logger = _get_logger()

        # Auto-create inference client if not provided
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
        self.ux = get_ux_manager()

        # SessionManager for persistence and telemetry
        self.session = SessionManager(session_id=session_id)
        self._session_id = self.session.session_id

        # State Checkpointer
        self._checkpointer = checkpointer or get_checkpointer()
        self._load_state()

        # LangGraph Cognitive Graph
        self.use_graph_mode = use_graph_mode
        if use_graph_mode:
            self._graph: OmniGraph = get_graph()
            self._graph_config = {"configurable": {"thread_id": self._session_id}}
            logger.bind(session_id=self._session_id).info("graph_mode_enabled")
        else:
            self._graph = None
            self._graph_config = None

        # Agent Registry
        self.agent_map: Dict[str, type] = {
            "coder": CoderAgent,
            "reviewer": ReviewerAgent,
            "orchestrator": None,
        }

        # Dynamic Workflow Components
        # Initialize SkillManager for dynamic graph execution
        from agent.core.skill_runtime import _get_singleton_manager

        self.skill_manager = _get_singleton_manager()
        available_tools = self.skill_manager.list_available()
        self.planner = Planner(self.inference, available_tools)
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
        self,
        user_query: str,
        history: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
    ) -> str:
        """
        Main Dispatch Loop with Feedback Loop and UX.

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

        # Start task visualization
        self.ux.start_task(user_query)

        logger.bind(session_id=self._session_id).info("orchestrator_processing_request")

        # Log user input to session
        self.session.log("user", "user", user_query)

        # Update GraphState with user message
        self._update_state({"messages": [{"role": "user", "content": user_query}]})

        # Use LangGraph cognitive graph if enabled
        if self.use_graph_mode and self._graph is not None:
            return await self._dispatch_graph_mode(user_query, history, context)

        # Standard dispatch
        return await self._dispatch_standard(user_query, history)

    async def dispatch_dynamic(self, user_query: str) -> str:
        """Dynamic Graph Execution Mode.

        This method uses the Planner's WorkflowArchitect to design a workflow
        blueprint, then compiles and executes it using DynamicGraphBuilder.

        Flow:
        1. Architect: Generate Blueprint (LLM)
        2. Build: Compile Graph (DynamicGraphBuilder)
        3. Execute: Run (LangGraph)

        Args:
            user_query: The user's request.

        Returns:
            Agent's response content from graph execution.
        """
        logger = _get_logger()
        logger.bind(session_id=self._session_id, query_preview=user_query[:50])
        logger.info("Starting dynamic dispatch")

        try:
            # Step 1: Generate Blueprint from LLM
            blueprint = await self.planner.create_dynamic_workflow(user_query)

            # Step 2: Build Graph from Blueprint
            builder = DynamicGraphBuilder(self.skill_manager)

            # Add nodes
            for node in blueprint.nodes:
                if node.type == "skill":
                    # Parse skill.command
                    if "." in node.target:
                        skill_name, cmd_name = node.target.split(".", 1)
                    else:
                        skill_name = node.target
                        cmd_name = node.target

                    builder.add_skill_node(
                        node.id,
                        skill_name,
                        cmd_name,
                        fixed_args=node.fixed_args,
                        state_input=node.state_inputs,
                    )

            # Add edges
            for edge in blueprint.edges:
                if edge.condition:
                    # Conditional edges would need a condition function
                    # For now, use simple edge
                    builder.add_edge(edge.source, edge.target)
                else:
                    builder.add_edge(edge.source, edge.target)

            # Set entry point and compile
            builder.set_entry_point(blueprint.entry_point)
            graph = builder.compile()

            # Step 3: Execute Graph
            initial_state = {
                "messages": [{"role": "user", "content": user_query}],
                "context_ids": [],
                "current_plan": "",
                "error_count": 0,
                "workflow_state": {},
            }

            result = await graph.ainvoke(initial_state)

            logger.info(
                "Dynamic dispatch completed",
                workflow=blueprint.name,
                nodes=len(blueprint.nodes),
            )

            return str(result)

        except Exception as e:
            logger.error("Dynamic dispatch failed", error=str(e), exc_info=True)
            return f"Error executing dynamic workflow: {e}"

    # Delegate to sub-module functions
    _dispatch_standard = dispatch_standard
    _execute_with_feedback_loop = execute_with_feedback_loop
    _get_tools_for_agent = get_tools_for_agent
    _load_state = load_state
    _save_state = save_state
    _update_state = update_state
    get_state = get_state
    get_state_history = get_state_history
    get_status = get_status
    _dispatch_graph_mode = dispatch_graph_mode
    dispatch_with_hive_context = dispatch_with_hive_context


async def orchestrator_main():
    """CLI entry point for testing Orchestrator."""
    from rich.console import Console

    console = Console()

    console.print(" Omni Agentic OS - Orchestrator Mode")
    console.print("=" * 50)

    orchestrator = Orchestrator()

    history = []

    while True:
        try:
            user_input = input("\n You: ")
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print(" Goodbye!")
                break

            response = await orchestrator.dispatch(user_input, history)

            console.print(f"\n Agent: {response}")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            if len(history) > 20:
                history = history[-20:]

        except KeyboardInterrupt:
            console.print("\n Interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f" Error: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(orchestrator_main())
