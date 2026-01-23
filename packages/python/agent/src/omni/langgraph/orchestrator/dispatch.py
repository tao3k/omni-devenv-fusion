"""
omni/core/orchestrator/dispatch.py - Graph Dispatch

LangGraph Cognitive Graph Integration for Orchestrator.

Dispatch using LangGraph cognitive state machine.
Plan -> Execute -> Reflect cycle with conditional edges.

Usage:
    from omni.core.orchestrator.dispatch import dispatch_graph_mode

    result = await dispatch_graph_mode(
        orchestrator=self,
        user_query="Fix the bug",
        history=[],
        context={"file": "main.py"},
    )
"""

from typing import Any


async def dispatch_graph_mode(
    orchestrator: Any,
    user_query: str,
    history: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """
    Dispatch using LangGraph cognitive state machine.

    Replaces procedural dispatch loop with graph-based execution.
    Uses plan -> execute -> reflect cycle with conditional edges.

    Args:
        orchestrator: The orchestrator instance (for session/ux access)
        user_query: The user's request
        history: Conversation history
        context: Additional context (files, etc.)

    Returns:
        Agent's response content
    """
    # Lazy import to avoid circular import
    from omni.langgraph.graph import GraphOutput, get_graph
    import structlog

    logger = structlog.get_logger(__name__)
    logger.bind(
        session_id=getattr(orchestrator, "_session_id", "unknown"),
        query_preview=user_query[:50],
        graph_mode=True,
    ).info("graph_dispatch_started")

    # Start task visualization
    if hasattr(orchestrator, "ux") and orchestrator.ux:
        orchestrator.ux.start_task(user_query)

    # Log user input to session
    if hasattr(orchestrator, "session") and orchestrator.session:
        orchestrator.session.log("user", "user", user_query)

    try:
        # Get or create the graph
        graph = get_graph(
            inference_client=getattr(orchestrator, "inference", None),
            skill_runner=getattr(orchestrator, "kernel", None),
        )

        # Run the cognitive graph
        thread_id = getattr(orchestrator, "_session_id", "default")
        result: GraphOutput = await graph.run(
            user_query=user_query,
            thread_id=thread_id,
            context=context,
        )

        # Show result
        if hasattr(orchestrator, "ux") and orchestrator.ux:
            orchestrator.ux.print_agent_response(result.content, "Graph Output")

        # Log to session
        if hasattr(orchestrator, "session") and orchestrator.session:
            orchestrator.session.log("graph_action", "omni_graph", result.content)

        logger.bind(
            session_id=thread_id,
            success=result.success,
            confidence=result.confidence,
            iterations=result.iterations,
        ).info("graph_dispatch_complete")

        if hasattr(orchestrator, "ux") and orchestrator.ux:
            orchestrator.ux.end_task(success=result.success)

        if not result.success:
            return f"Graph execution failed: {result.content}"

        return result.content

    except Exception as e:
        logger.bind(
            session_id=getattr(orchestrator, "_session_id", "unknown"),
            error=str(e),
        ).error("graph_dispatch_failed")

        if hasattr(orchestrator, "ux") and orchestrator.ux:
            orchestrator.ux.show_error("Graph execution failed", str(e))

        if hasattr(orchestrator, "session") and orchestrator.session:
            orchestrator.session.log("error", "omni_graph", str(e))

        if hasattr(orchestrator, "ux") and orchestrator.ux:
            orchestrator.ux.end_task(success=False)

        return f"System Error during graph execution: {str(e)}"


__all__ = ["dispatch_graph_mode"]
