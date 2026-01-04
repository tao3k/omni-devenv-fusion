"""
src/agent/core/orchestrator.py
Orchestrator - The Central Switchboard.

Phase 14 Enhancement:
- Coordinates flow between User -> Router -> Specialized Agents
- Handles dispatch, context injection, and execution lifecycle

Usage:
    from agent.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(inference)
    response = await orchestrator.dispatch(user_query, history)
"""
import structlog
from typing import Dict, Any, Optional, List

from agent.core.router import get_hive_router, AgentRoute
from agent.core.agents.base import BaseAgent, AgentResult
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent

logger = structlog.get_logger()


class Orchestrator:
    """
    The Central Switchboard.
    Coordinates the flow between User -> Router -> Specialized Agents.

    Responsibilities:
    1. Route: Consult HiveRouter for agent delegation
    2. Instantiate: Create the right Agent for the job
    3. Execute: Run the agent with Mission Brief
    4. Return: Aggregate results back to user
    """

    def __init__(self, inference_engine=None):
        """
        Initialize Orchestrator.

        Args:
            inference_engine: Optional inference engine for LLM calls
        """
        self.inference = inference_engine
        self.router = get_hive_router()

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
        Main Dispatch Loop.

        Args:
            user_query: The user's request
            history: Conversation history
            context: Additional context (files, etc.)

        Returns:
            Agent's response content
        """
        logger.info("🎹 Orchestrator processing request", query=user_query[:80])

        # === Phase 1: Hive Routing ===
        route = await self.router.route_to_agent(
            query=user_query,
            context=str(history) if history else "",
            use_cache=True
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

        try:
            result: AgentResult = await worker.run(
                task=user_query,
                mission_brief=task_brief,
                constraints=route.constraints or [],
                relevant_files=route.relevant_files or [],
                chat_history=history or []
            )

            logger.info(
                f"✅ {target_agent_class.name.upper()} complete",
                success=result.success,
                confidence=result.confidence
            )

            return result.content

        except Exception as e:
            logger.error("❌ Agent execution failed", error=str(e))
            return f"System Error during execution: {str(e)}"

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
