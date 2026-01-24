"""
omni/langgraph/graph.py - LangGraph Cognitive Graph

The Cognitive Graph - LangGraph implementation for Omni.

Replaces procedural loops with a state machine.

Architecture:
- Nodes: plan, execute, reflect (think-act-observe cycle)
- Edges: Conditional transitions based on state
- Checkpointer: Cross-session state persistence

Usage:
    from omni.langgraph.graph import OmniGraph, get_graph

    graph = get_graph()
    result = await graph.run(
        user_query="Fix the bug in main.py",
        thread_id="session-123",
    )
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from structlog import get_logger

from omni.langgraph.nodes.recall import recall_node
from omni.langgraph.orchestrator.compiled import CompiledGraph
from omni.langgraph.state import GraphState, StateCheckpointer, get_checkpointer

logger = get_logger()


# =============================================================================
# Graph Input/Output Types
# =============================================================================


class GraphInput(TypedDict):
    """Input to the graph."""

    user_query: str
    context: dict[str, Any] | None = None


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


async def plan_node(
    state: GraphState,
    router: Any = None,
    inference: Any = None,
) -> dict[str, Any]:
    """
    Planning node: Route user query to appropriate agent/workflow.

    Uses LLM or router to determine the task approach.
    Injects recalled lessons from past experiences if available.
    """
    # Get last user message
    if not state.get("messages"):
        return {"error_count": state.get("error_count", 0) + 1}

    last_msg = state["messages"][-1]
    user_content = last_msg.get("content", "")

    log = logger.bind(node="plan")

    # Check for recalled lessons from previous recall node
    workflow = state.get("workflow_state", {})
    recalled_lessons = workflow.get("recalled_lessons", [])

    if recalled_lessons:
        log.info("injecting_recalled_lessons", count=len(recalled_lessons))
        lessons_block = "\n\nRELEVANT PAST EXPERIENCES:\n" + "\n".join(recalled_lessons)
    else:
        lessons_block = ""

    if router is not None:
        # Use semantic router if available
        try:
            route = await router.route(user_content)
            log.info("route_selected", target=route.get("target_agent", "default"))
            return {
                "current_plan": route.get("task_brief", user_content),
                "workflow_state": {
                    "target_agent": route.get("target_agent", "coder"),
                    "route_confidence": route.get("confidence", 0.5),
                    "constraints": route.get("constraints", []),
                    "relevant_files": route.get("relevant_files", []),
                },
            }
        except Exception as e:
            log.warning("router_failed", error=str(e))
    elif inference is not None:
        # Use LLM for planning with recalled wisdom
        system_prompt = f"""You are a planning agent. Analyze the user's request and create a plan.{lessons_block}

Return a JSON object with:
- task_brief: A brief description of the task to execute
- target_agent: The type of agent (coder, reviewer, etc.)
- confidence: Your confidence in this plan (0-1)
- constraints: Any constraints or considerations
"""
        try:
            response = await inference.complete(
                system_prompt=system_prompt,
                user_query=user_content,
                messages=[],
            )

            # Try to parse the response as JSON
            import json

            try:
                plan = json.loads(response.get("content", "{}"))
                return {
                    "current_plan": plan.get("task_brief", user_content),
                    "workflow_state": {
                        "target_agent": plan.get("target_agent", "coder"),
                        "route_confidence": plan.get("confidence", 0.5),
                        "constraints": plan.get("constraints", []),
                        "relevant_files": plan.get("relevant_files", []),
                    },
                }
            except json.JSONDecodeError:
                pass
        except Exception as e:
            log.warning("inference_planning_failed", error=str(e))

    # Fallback: simple direct execution
    log.info("using_direct_plan")
    return {
        "current_plan": user_content,
        "workflow_state": {
            "target_agent": "default",
            "route_confidence": 0.5,
            "constraints": [],
            "relevant_files": [],
        },
    }


async def execute_node(
    state: GraphState,
    skill_runner: Any = None,
    inference: Any = None,
) -> dict[str, Any]:
    """
    Execution node: Execute task using appropriate method.

    Uses skill runner or LLM inference to execute the plan.
    """
    log = logger.bind(node="execute")

    workflow = state.get("workflow_state", {})
    target_agent = workflow.get("target_agent", "default")
    task_brief = state.get("current_plan", "")

    log.info("executing", agent=target_agent, task=task_brief[:100])

    # Use skill runner if available
    if skill_runner is not None:
        try:
            # Parse skill.command format
            target = target_agent
            if "." in target:
                skill_name, command_name = target.split(".", 1)
            else:
                skill_name = target
                command_name = target

            result = await skill_runner.run(skill_name, command_name, {"task": task_brief})

            log.info(
                "execution_complete",
                success=True,
            )

            return {
                "messages": [{"role": "assistant", "content": result}],
                "workflow_state": {
                    **workflow,
                    "last_result": {
                        "success": True,
                        "confidence": 0.9,
                    },
                },
            }
        except Exception as e:
            log.error("skill_execution_failed", error=str(e))
            return {
                "messages": [{"role": "assistant", "content": f"Error: {e!s}"}],
                "error_count": state.get("error_count", 0) + 1,
            }

    # Fallback: use LLM inference
    if inference is not None:
        try:
            response = await inference.complete(
                system_prompt="You are a helpful assistant. Execute the task.",
                user_query=task_brief,
                messages=state.get("messages", []),
            )

            log.info(
                "execution_complete",
                success=True,
            )

            return {
                "messages": [{"role": "assistant", "content": response.get("content", "")}],
                "workflow_state": {
                    **workflow,
                    "last_result": {
                        "success": True,
                        "confidence": response.get("confidence", 0.5),
                    },
                },
            }
        except Exception as e:
            log.error("inference_execution_failed", error=str(e))
            return {
                "messages": [{"role": "assistant", "content": f"Error: {e!s}"}],
                "error_count": state.get("error_count", 0) + 1,
            }

    # No execution method available
    return {
        "messages": [{"role": "assistant", "content": "Cannot execute: no runner available"}],
        "error_count": state.get("error_count", 0) + 1,
    }


async def reflect_node(
    state: GraphState,
    inference: Any = None,
) -> dict[str, Any]:
    """
    Reflection node: Evaluate execution result.

    Determines if the result is satisfactory or needs revision.
    """
    log = logger.bind(node="reflect")

    workflow = state.get("workflow_state", {})
    target_agent = workflow.get("target_agent", "default")

    # Get last assistant message
    messages = state.get("messages", [])
    if not messages:
        return {"error_count": state.get("error_count", 0) + 1}

    last_output = messages[-1].get("content", "")
    task_brief = state.get("current_plan", "")

    log.info("reflecting", content_length=len(last_output))

    # Use LLM for reflection if available
    if inference is not None:
        system_prompt = """You are a quality reviewer. Evaluate the assistant's response to the user's request.

Consider:
- Did it address the user's request?
- Is the response accurate and helpful?
- Are there any issues or improvements needed?

Return a JSON object with:
- approved: true if the response is satisfactory, false if revision needed
- confidence: Your confidence in this evaluation (0-1)
- feedback: If not approved, explain what needs to be improved
"""
        try:
            response = await inference.complete(
                system_prompt=system_prompt,
                user_query=f"Task: {task_brief}\n\nResponse: {last_output}",
                messages=[],
            )

            import json

            try:
                review = json.loads(response.get("content", "{}"))
                approved = review.get("approved", True)
                confidence = review.get("confidence", 0.5)
                feedback = review.get("feedback", "")

                log.info(
                    "audit_complete",
                    approved=approved,
                    confidence=confidence,
                )

                if approved:
                    return {
                        "workflow_state": {
                            **workflow,
                            "approved": True,
                            "audit_confidence": confidence,
                        },
                    }
                else:
                    # Request revision
                    return {
                        "messages": [{"role": "user", "content": f"Feedback: {feedback}"}],
                        "error_count": state.get("error_count", 0) + 1,
                        "workflow_state": {
                            **workflow,
                            "approved": False,
                            "audit_feedback": feedback,
                        },
                    }
            except json.JSONDecodeError:
                pass
        except Exception as e:
            log.warning("inference_reflection_failed", error=str(e))

    # Fallback: auto-approve if no issues
    log.info("auto_approving")
    return {"workflow_state": {**workflow, "approved": True}}


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
    target_agent = workflow.get("target_agent", "default")

    # If this is first execution (no messages from assistant yet), go to execute
    messages = state.get("messages", [])
    has_assistant_response = any(msg.get("role") == "assistant" for msg in messages)

    if not has_assistant_response:
        return "execute"

    # After execution, decide next step
    if target_agent != "default":
        return "reflect"

    return "__end__"


def audit_decision(state: GraphState) -> Literal["recall", "__end__"]:
    """
    Decide whether to recall past experiences or end after reflection.

    Recall if:
    - Not approved AND error_count < max_retries

    End if:
    - Approved by reviewer
    - OR max retries exceeded
    """
    workflow = state.get("workflow_state", {})
    error_count = state.get("error_count", 0)
    max_retries = 3

    log = logger.bind(node="audit_decision")

    # Check if approved
    if workflow.get("approved"):
        log.info("audit_approved_ending")
        return "__end__"

    # Check retry count
    if error_count >= max_retries:
        log.warning("max_retries_exceeded", errors=error_count)
        return "__end__"

    # Trigger recall to learn from past experiences
    log.info("triggering_recall", errors=error_count)
    return "recall"


# =============================================================================
# Graph Builder
# =============================================================================


class OmniGraph:
    """
    Cognitive Graph for Omni Agent.

    Implements ReAct (Reasoning + Acting) pattern with LangGraph.
    Uses MemorySaver for LangGraph checkpointer, StateCheckpointer for persistence.

    Self-Healing Flow:
        plan → execute → reflect
                      ↓
                    recall (if not approved)
                      ↓
                    plan (with recalled wisdom)
    """

    def __init__(
        self,
        inference_client: Any = None,
        skill_runner: Any = None,
        router: Any = None,
        checkpointer: StateCheckpointer | None = None,
        use_memory_checkpointer: bool = True,
        lance_checkpointer: Any = None,  # LanceCheckpointer for recall
    ):
        """
        Initialize the cognitive graph.

        Args:
            inference_client: Optional inference client for LLM calls
            skill_runner: Optional skill runner for executing skills
            router: Optional router for task routing
            checkpointer: Optional StateCheckpointer for persistence (not used by LangGraph)
            use_memory_checkpointer: Use MemorySaver for LangGraph (default: True)
            lance_checkpointer: Optional LanceCheckpointer for semantic recall
        """
        self.inference = inference_client
        self.skill_runner = skill_runner
        self.router = router
        self.checkpointer = checkpointer or get_checkpointer()
        self.lance_checkpointer = lance_checkpointer
        self._app: CompiledGraph | None = None
        self._memory_checkpointer = MemorySaver() if use_memory_checkpointer else None

    def _create_workflow(self) -> StateGraph:
        """Create the state workflow with nodes and edges."""
        workflow = StateGraph(GraphState)

        # Add nodes with bound methods
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("execute", self._execute_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("recall", self._recall_node)

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

        # Conditional: reflect -> recall (retry) or __end__
        workflow.add_conditional_edges(
            "reflect",
            audit_decision,
            {
                "recall": "recall",
                "__end__": END,
            },
        )

        # Recall -> plan (with injected wisdom)
        workflow.add_edge("recall", "plan")

        return workflow

    async def _plan_node(self, state: GraphState) -> dict[str, Any]:
        """Planning node wrapper."""
        return await plan_node(state, router=self.router, inference=self.inference)

    async def _execute_node(self, state: GraphState) -> dict[str, Any]:
        """Execution node wrapper."""
        return await execute_node(
            state,
            skill_runner=self.skill_runner,
            inference=self.inference,
        )

    async def _reflect_node(self, state: GraphState) -> dict[str, Any]:
        """Reflection node wrapper."""
        return await reflect_node(state, inference=self.inference)

    async def _recall_node(self, state: GraphState) -> dict[str, Any]:
        """Recall node wrapper - retrieves similar past experiences."""
        log = logger.bind(node="recall")

        if self.lance_checkpointer is None:
            log.debug("no_lance_checkpointer_skipping_recall")
            return {"workflow_state": state.get("workflow_state", {})}

        try:
            return await recall_node(
                state=state,
                checkpointer=self.lance_checkpointer,
                top_k=3,
            )
        except Exception as e:
            log.error("recall_node_failed", error=str(e))
            return {"workflow_state": state.get("workflow_state", {})}

    def get_app(self) -> CompiledGraph:
        """Get the compiled graph application."""
        if self._app is None:
            workflow = self._create_workflow()
            self._app = CompiledGraph(
                graph=workflow.compile(checkpointer=self._memory_checkpointer),
            )
        return self._app

    async def run(
        self,
        user_query: str,
        thread_id: str,
        context: dict[str, Any] | None = None,
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
        config = app.get_config(thread_id)

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
            async for event in app.stream(initial_state, thread_id=thread_id):
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
                final_state = await app.aget_state(thread_id)
                if final_state and final_state.values:
                    workflow = final_state.values.get("workflow_state", {})
                    confidence = workflow.get("last_result", {}).get("confidence", 0.9)

        except Exception as e:
            log.error("graph_error", error=str(e))
            result_content = f"Error: {e!s}"

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


def get_graph(
    inference_client: Any = None,
    skill_runner: Any = None,
    router: Any = None,
) -> OmniGraph:
    """Get or create the global graph instance."""
    global _graph, _graph_lock
    if _graph_lock is None:
        import threading

        _graph_lock = threading.Lock()

    with _graph_lock:
        if _graph is None:
            _graph = OmniGraph(
                inference_client=inference_client,
                skill_runner=skill_runner,
                router=router,
            )
        return _graph


def reset_graph() -> None:
    """Reset the global graph instance (for testing)."""
    global _graph
    _graph = None


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "GraphInput",
    "GraphOutput",
    "OmniGraph",
    "audit_decision",
    "execute_node",
    "get_graph",
    "plan_node",
    "reflect_node",
    "reset_graph",
    "should_continue",
]
