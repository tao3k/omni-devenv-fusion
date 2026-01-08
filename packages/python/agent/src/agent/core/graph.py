"""
agent/core/graph.py
The Cognitive Graph - LangGraph implementation for Omni.

Phase 34: Replaces procedural loops with a state machine.
Uses ODF-EP v6.0 Pillars (Pydantic, Tenacity, Observability).

Architecture:
- Nodes: plan, execute, reflect (think-act-observe cycle)
- Edges: Conditional transitions based on state
- Checkpointer: Cross-session state persistence
"""

from __future__ import annotations

from typing import Literal, Dict, Any, TypedDict

from langgraph.graph import StateGraph, END
from structlog import get_logger

# Import existing components (Step 1-3)
from agent.core.state import GraphState, get_checkpointer, StateCheckpointer
from agent.core.router import AgentRoute, get_hive_router
from agent.core.agents.base import AgentResult
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent

logger = get_logger()


# =============================================================================
# Graph Input/Output Types
# =============================================================================


class GraphInput(TypedDict):
    """Input to the graph."""

    user_query: str
    context: Dict[str, Any] | None = None


class GraphOutput(TypedDict):
    """Output from the graph."""

    success: bool
    content: str
    confidence: float
    iterations: int
    approved: bool


# =============================================================================
# Node Functions
# =============================================================================


async def plan_node(state: GraphState) -> Dict[str, Any]:
    """
    Planning node: Route user query to appropriate agent.

    Uses Hive Router to determine target agent and task brief.
    """
    log = logger.bind(node="plan")

    # Get last user message
    if not state.get("messages"):
        return {"error_count": state.get("error_count", 0) + 1}

    last_msg = state["messages"][-1]
    user_content = last_msg.get("content", "")

    log.info("planning", query=user_content[:100])

    # Route using Hive Router
    router = get_hive_router()
    route: AgentRoute = await router.route_to_agent(
        query=user_content,
        context=str(state.get("messages", [])),
        use_cache=True,
    )

    log.info(
        "route_selected",
        target=route.target_agent,
        confidence=route.confidence,
    )

    # Return updates
    return {
        "current_plan": route.task_brief or user_content,
        "workflow_state": {
            "target_agent": route.target_agent,
            "route_confidence": route.confidence,
            "constraints": route.constraints or [],
            "relevant_files": route.relevant_files or [],
        },
    }


async def execute_node(state: GraphState) -> Dict[str, Any]:
    """
    Execution node: Execute task using appropriate agent.

    Uses enhanced tools with resilience (CommandResult).
    """
    log = logger.bind(node="execute")

    workflow = state.get("workflow_state", {})
    target_agent = workflow.get("target_agent", "coder")
    task_brief = state.get("current_plan", "")

    log.info("executing", agent=target_agent, task=task_brief[:100])

    # Select and run agent
    try:
        if target_agent == "coder":
            agent = CoderAgent()
        elif target_agent == "reviewer":
            agent = ReviewerAgent()
        else:
            # Default to Coder
            agent = CoderAgent()

        result: AgentResult = await agent.run(task_brief)

        log.info(
            "execution_complete",
            success=result.success,
            confidence=result.confidence,
        )

        return {
            "messages": [{"role": "assistant", "content": result.content}],
            "workflow_state": {
                **workflow,
                "last_result": {
                    "success": result.success,
                    "confidence": result.confidence,
                },
            },
        }

    except Exception as e:
        log.error("execution_error", error=str(e))
        return {
            "messages": [{"role": "assistant", "content": f"Error: {str(e)}"}],
            "error_count": state.get("error_count", 0) + 1,
        }


async def reflect_node(state: GraphState) -> Dict[str, Any]:
    """
    Reflection node: Audit execution result with Reviewer.

    Determines if the result is approved or needs revision.
    """
    log = logger.bind(node="reflect")

    workflow = state.get("workflow_state", {})
    target_agent = workflow.get("target_agent", "coder")

    # Only run reflection for coder tasks
    if target_agent != "coder":
        log.debug("skipping_reflection", agent=target_agent)
        return {"workflow_state": {**workflow, "approved": True}}

    # Get last assistant message
    messages = state.get("messages", [])
    if not messages:
        return {"error_count": state.get("error_count", 0) + 1}

    last_output = messages[-1].get("content", "")
    task_brief = state.get("current_plan", "")

    log.info("reflecting", content_length=len(last_output))

    # Run reviewer audit
    try:
        reviewer = ReviewerAgent()
        audit = await reviewer.audit(task_brief, last_output)

        log.info(
            "audit_complete",
            approved=audit.approved,
            confidence=audit.confidence,
        )

        if audit.approved:
            return {
                "workflow_state": {
                    **workflow,
                    "approved": True,
                    "audit_confidence": audit.confidence,
                },
            }
        else:
            # Request revision
            return {
                "messages": [{"role": "user", "content": f"Feedback: {audit.feedback}"}],
                "error_count": state.get("error_count", 0) + 1,
                "workflow_state": {
                    **workflow,
                    "approved": False,
                    "audit_feedback": audit.feedback,
                },
            }

    except Exception as e:
        log.error("audit_error", error=str(e))
        return {"error_count": state.get("error_count", 0) + 1}


# =============================================================================
# Edge Logic
# =============================================================================


def should_continue(state: GraphState) -> Literal["reflect", "execute", "__end__"]:
    """
    Decide what to do after planning.

    Flow:
    - Always execute first (planner -> executor)
    - Then reflect based on agent type
    """
    workflow = state.get("workflow_state", {})
    target_agent = workflow.get("target_agent", "coder")

    # If this is first execution (no messages from assistant yet), go to execute
    messages = state.get("messages", [])
    has_assistant_response = any(msg.get("role") == "assistant" for msg in messages)

    if not has_assistant_response:
        return "execute"

    # After execution, decide next step
    if target_agent == "coder":
        return "reflect"

    return "__end__"


def audit_decision(state: GraphState) -> Literal["execute", "__end__"]:
    """
    Decide whether to retry or end after reflection.

    Retry if:
    - Not approved AND error_count < max_retries

    End if:
    - Approved by reviewer
    - OR max retries exceeded
    """
    workflow = state.get("workflow_state", {})
    error_count = state.get("error_count", 0)
    max_retries = 3

    # Check if approved
    if workflow.get("approved"):
        return "__end__"

    # Check retry count
    if error_count >= max_retries:
        log = logger.bind(node="audit_decision")
        log.warning("max_retries_exceeded", errors=error_count)
        return "__end__"

    # Retry execution
    return "execute"


# =============================================================================
# Graph Builder
# =============================================================================


class OmniGraph:
    """
    Cognitive Graph for Omni Agent.

    Implements ReAct (Reasoning + Acting) pattern with LangGraph.
    Integrates with StateCheckpointer for cross-session persistence.
    """

    def __init__(
        self,
        inference_client=None,
        checkpointer: StateCheckpointer | None = None,
    ):
        """
        Initialize the cognitive graph.

        Args:
            inference_client: Optional inference client for agents
            checkpointer: Optional StateCheckpointer (default: global singleton)
        """
        self.inference = inference_client
        self.checkpointer = checkpointer or get_checkpointer()
        self._app = None

    def _create_workflow(self) -> StateGraph:
        """Create the state workflow with nodes and edges."""
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("plan", plan_node)
        workflow.add_node("execute", execute_node)
        workflow.add_node("reflect", reflect_node)

        # Set entry point
        workflow.set_entry_point("plan")

        # Define edges
        workflow.add_edge("plan", "execute")

        # Conditional: execute -> reflect or __end__
        workflow.add_conditional_edges(
            "execute",
            should_continue,
            {
                "reflect": "reflect",
                "execute": "execute",
                "__end__": END,
            },
        )

        # Conditional: reflect -> execute (retry) or __end__
        workflow.add_conditional_edges(
            "reflect",
            audit_decision,
            {
                "execute": "execute",
                "__end__": END,
            },
        )

        return workflow

    def get_app(self):
        """Get the compiled graph application."""
        if self._app is None:
            workflow = self._create_workflow()
            self._app = workflow.compile(
                checkpointer=self.checkpointer,
            )
        return self._app

    async def run(
        self,
        user_query: str,
        thread_id: str,
        context: Dict[str, Any] | None = None,
    ) -> GraphOutput:
        """
        Run the graph with a user query.

        Args:
            user_query: The user's request
            thread_id: Session identifier for checkpointer
            context: Optional context (e.g., relevant files)

        Returns:
            GraphOutput with success, content, and metadata
        """
        log = logger.bind(graph="OmniGraph", thread_id=thread_id)
        log.info("graph_invocation", query=user_query[:100])

        app = self.get_app()
        config = {"configurable": {"thread_id": thread_id}}

        # Initial state
        initial_state = GraphState(
            messages=[{"role": "user", "content": user_query}],
            context_ids=[],
            current_plan="",
            error_count=0,
            workflow_state={
                "context": context or {},
            },
        )

        result_content = ""
        success = False
        confidence = 0.0
        iterations = 0

        try:
            # Stream execution
            async for event in app.astream(initial_state, config=config):
                for node_name, state_update in event.items():
                    iterations += 1

                    # Track final result
                    if node_name == "execute":
                        messages = state_update.get("messages", [])
                        if messages:
                            result_content = messages[-1].get("content", "")

                    # Check approval
                    if node_name == "reflect":
                        workflow = state_update.get("workflow_state", {})
                        if workflow.get("approved"):
                            success = True
                            confidence = workflow.get("audit_confidence", 0.9)

                    log.debug(
                        "node_progress",
                        node=node_name,
                        iteration=iterations,
                    )

            # Get final confidence from workflow state
            if success:
                final_state = await app.aget_state(config)
                workflow = final_state.values.get("workflow_state", {})
                confidence = workflow.get("last_result", {}).get("confidence", 0.9)

        except Exception as e:
            log.error("graph_error", error=str(e))
            result_content = f"Error: {str(e)}"

        return GraphOutput(
            success=success,
            content=result_content,
            confidence=confidence,
            iterations=iterations,
            approved=success,
        )


# =============================================================================
# Factory Functions
# =============================================================================


_graph: OmniGraph | None = None
_graph_lock = None


def get_graph() -> OmniGraph:
    """Get or create the global graph instance."""
    global _graph, _graph_lock
    if _graph_lock is None:
        import threading

        _graph_lock = threading.Lock()

    with _graph_lock:
        if _graph is None:
            _graph = OmniGraph()
        return _graph


def reset_graph() -> None:
    """Reset the global graph instance (for testing)."""
    global _graph
    _graph = None


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "OmniGraph",
    "get_graph",
    "reset_graph",
    "plan_node",
    "execute_node",
    "reflect_node",
    "should_continue",
    "audit_decision",
    "GraphInput",
    "GraphOutput",
]
