"""
agent/core/orchestrator/dispatch.py
Dispatch logic for Orchestrator.

Contains the main dispatch() method and dispatch_with_hive_context().
"""

from typing import Dict, Any, Optional, List

from agent.core.agents.base import AgentResult
from agent.core.agents.coder import CoderAgent
from agent.core.telemetry import CostEstimator
from agent.core.router import get_router


async def dispatch_standard(
    self,
    user_query: str,
    history: List[Dict[str, Any]] = None,
) -> str:
    """
    Standard dispatch execution (non-feedback path).

    Args:
        user_query: The user's request
        history: Conversation history

    Returns:
        Agent's response content
    """
    import structlog

    logger = structlog.get_logger(__name__)

    # ===  Hive Routing ===
    self.ux.start_routing()
    route = await self.router.route_to_agent(
        query=user_query, context=str(history) if history else "", use_cache=True
    )
    self.ux.stop_routing()

    #  Show routing result
    self.ux.show_routing_result(
        agent_name=route.target_agent,
        mission_brief=route.task_brief or user_query,
        confidence=route.confidence,
        from_cache=route.from_cache,
    )

    #  Auto-trigger SemanticRouter for skill-level routing
    # This happens in parallel - skill routing is independent of agent routing
    try:
        router = get_router()
        skill_route = await router.route(user_query, history, use_cache=True)

        # Show skill suggestions if remote skills found
        if skill_route.remote_suggestions:
            self.ux.show_skill_suggestions(skill_route.remote_suggestions)

            # Log skill suggestions
            logger.bind(
                session_id=self._session_id,
                remote_skill_count=len(skill_route.remote_suggestions),
            ).info("skill_suggestions_found")

    except Exception as e:
        # Skill routing failure should not block agent execution
        logger.bind(
            session_id=self._session_id,
            error=str(e),
        ).warning("skill_routing_failed")

    #  Log routing decision with cost estimate
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

    # ===  Agent Instantiation ===
    target_agent_class = self.agent_map.get(route.target_agent)

    if not target_agent_class:
        logger.bind(
            session_id=self._session_id,
            requested_agent=route.target_agent,
        ).warning("no_specialized_agent_fallback")
        target_agent_class = CoderAgent

    # Create agent instance with injected dependencies
    tools = self._get_tools_for_agent(route.target_agent)
    worker = target_agent_class(
        inference=self.inference,
        tools=tools,
    )

    logger.bind(
        session_id=self._session_id,
        agent_name=route.target_agent,
        tool_count=len(tools),
    ).debug("agent_instantiated")

    # ===  Execution with Mission Brief ===
    task_brief = route.task_brief or user_query

    logger.bind(
        session_id=self._session_id,
        agent_class=target_agent_class.name,
        brief_preview=task_brief[:50],
    ).debug("executing_agent")

    #  Feedback Loop for Coder tasks
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

        #  Show RAG sources
        if result.rag_sources:
            self.ux.show_rag_hits(result.rag_sources)

        #  Show agent response
        self.ux.print_agent_response(result.content, f"{target_agent_class.name.upper()} Output")

        #  Log agent output
        agent_usage = CostEstimator.estimate(task_brief + user_query, result.content)
        self.session.log("agent_action", target_agent_class.name, result.content, agent_usage)

        #  Update GraphState with agent response
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


async def dispatch_with_hive_context(
    self,
    user_query: str,
    hive_context: Dict[str, Any],
) -> str:
    """
    Dispatch with additional Hive context (from Orchestrator MCP).

    Args:
        user_query: The user's request
        hive_context: Additional context from Orchestrator MCP tools

    Returns:
        Agent's response content
    """
    import structlog

    logger = structlog.get_logger(__name__)

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


__all__ = ["dispatch_standard", "dispatch_with_hive_context"]
