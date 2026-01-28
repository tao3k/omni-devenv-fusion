"""
orchestrator.py - Cognitive Pipeline Orchestrator

Parallel fetch, sequential assembly for optimal performance.
"""

from __future__ import annotations

import asyncio

from omni.foundation.config.logging import get_logger

from .base import ContextProvider, ContextResult
from .providers import (
    ActiveSkillProvider,
    AvailableToolsProvider,
    EpisodicMemoryProvider,
    SystemPersonaProvider,
)

logger = get_logger("omni.core.context.orchestrator")


class ContextOrchestrator:
    """The Cognitive Pipeline - assembles context from multiple providers.

    Strategy:
    1. Parallel fetch: Use asyncio.gather for concurrent provider execution
    2. Sequential assembly: Build final context respecting priority order
    """

    def __init__(
        self,
        providers: list[ContextProvider],
        max_tokens: int = 128000,
        output_reserve: int = 4096,
    ) -> None:
        self._providers = sorted(providers, key=lambda p: getattr(p, "priority", 50))
        self._max_input_tokens = max_tokens - output_reserve

    async def build_context(self, state: dict[str, object]) -> str:
        """Build unified context from all providers.

        Args:
            state: LangGraph state dict

        Returns:
            Assembled context string
        """
        # 1. Parallel fetch with unlimited initial budget
        budget = self._max_input_tokens
        tasks = [p.provide(state, budget) for p in self._providers]

        results: list[ContextResult] = []
        provider_outputs: list[dict] = []  # For detailed logging
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if isinstance(result, ContextResult):
                    results.append(result)
                    provider_outputs.append(
                        {
                            "name": result.name,
                            "priority": result.priority,
                            "tokens": result.token_count,
                            "chars": len(result.content),
                            "preview": result.content[:100].replace("\n", " ") + "...",
                        }
                    )
                elif result is None:
                    logger.warning("A provider returned None")
            except Exception as e:
                logger.error(f"Provider error: {e}")

        # Log detailed provider outputs
        logger.info(
            "Context providers output",
            providers=provider_outputs,
            total_tokens=sum(r.token_count for r in results),
        )

        # 2. Sort by priority (0 = highest)
        results.sort(key=lambda r: r.priority)

        # 3. Sequential assembly with budget tracking
        final_parts: list[str] = []
        remaining = self._max_input_tokens

        for res in results:
            if res.token_count == 0:
                continue

            if remaining >= res.token_count:
                final_parts.append(res.content)
                remaining -= res.token_count
            else:
                logger.debug(
                    f"Budget exhausted for {res.name}",
                    required=res.token_count,
                    remaining=remaining,
                )

        return "\n\n".join(final_parts)


def create_planner_orchestrator() -> ContextOrchestrator:
    """Create orchestrator optimized for planning/architecting."""
    return ContextOrchestrator(
        [
            SystemPersonaProvider(role="architect"),
            AvailableToolsProvider(),
            ActiveSkillProvider(),
            EpisodicMemoryProvider(),
        ]
    )


def create_executor_orchestrator() -> ContextOrchestrator:
    """Create orchestrator optimized for coding/execution."""
    return ContextOrchestrator(
        [
            SystemPersonaProvider(role="developer"),
            ActiveSkillProvider(),
        ]
    )


def create_omni_loop_context() -> ContextOrchestrator:
    """Create orchestrator for the Main ReAct Loop (Omni-Orchestrator).

    Uses agent-specific RoutingGuidanceProvider for meta-cognition protocol.
    Includes EpisodicMemoryProvider for automatic memory recall.

    Returns:
        ContextOrchestrator with Persona + Routing Protocol + Tools + Active Skill + Memory
    """
    # Import from agent package (agent depends on core, not vice versa)
    # This allows core to remain framework-agnostic while agent provides
    # the specific routing protocol implementation.
    try:
        from omni.agent.core.context.providers import RoutingGuidanceProvider
    except ImportError:
        # Fallback if agent package not available
        logger.warning("RoutingGuidanceProvider not found, using basic orchestrator")
        return create_executor_orchestrator()

    return ContextOrchestrator(
        [
            SystemPersonaProvider(role="developer"),  # Main role for Omni Loop
            RoutingGuidanceProvider(),  # Meta-cognition protocol
            AvailableToolsProvider(),  # Tool index
            ActiveSkillProvider(),  # Active skill context
            EpisodicMemoryProvider(top_k=3),  # [NEW] Automatic memory recall
        ]
    )


__all__ = [
    "ContextOrchestrator",
    "create_executor_orchestrator",
    "create_planner_orchestrator",
    "create_omni_loop_context",
]
