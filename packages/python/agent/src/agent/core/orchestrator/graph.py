"""
agent/core/orchestrator/graph.py
LangGraph Cognitive Graph Integration for Orchestrator.

Phase 34: Dispatch using LangGraph cognitive state machine.
Plan -> Execute -> Reflect cycle with conditional edges.
"""

from typing import Dict, Any, List

from agent.core.telemetry import CostEstimator


async def dispatch_graph_mode(
    self,
    user_query: str,
    history: List[Dict[str, Any]] = None,
    context: Dict[str, Any] = None,
) -> str:
    """
    Dispatch using LangGraph cognitive state machine.

    Phase 34: Replaces procedural dispatch loop with graph-based execution.
    Uses plan -> execute -> reflect cycle with conditional edges.

    Args:
        user_query: The user's request
        history: Conversation history
        context: Additional context (files, etc.)

    Returns:
        Agent's response content
    """
    import structlog

    logger = structlog.get_logger(__name__)
    logger.bind(
        session_id=self._session_id,
        query_preview=user_query[:50],
        graph_mode=True,
    ).info("graph_dispatch_started")

    # Phase 18: Start task visualization
    self.ux.start_task(user_query)

    # Phase 19: Log user input to session
    self.session.log("user", "user", user_query)

    try:
        # Run the cognitive graph
        result = await self._graph.run(
            user_query=user_query,
            thread_id=self._session_id,
            context=context,
        )

        # Phase 18: Show result
        self.ux.print_agent_response(result.content, "Graph Output")

        # Phase 19: Log to session
        usage = CostEstimator.estimate(user_query, result.content)
        self.session.log("graph_action", "omni_graph", result.content, usage)

        logger.bind(
            session_id=self._session_id,
            success=result.success,
            confidence=result.confidence,
            iterations=result.iterations,
        ).info("graph_dispatch_complete")

        self.ux.end_task(success=result.success)

        if not result.success:
            return f"Graph execution failed: {result.content}"

        return result.content

    except Exception as e:
        logger.bind(
            session_id=self._session_id,
            error=str(e),
        ).error("graph_dispatch_failed")
        self.ux.show_error("Graph execution failed", str(e))
        self.session.log("error", "omni_graph", str(e))
        self.ux.end_task(success=False)
        return f"System Error during graph execution: {str(e)}"


__all__ = ["dispatch_graph_mode"]
