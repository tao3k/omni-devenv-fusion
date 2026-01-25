"""
providers.py - Agent-Specific Context Providers

Layer-specific providers for the Omni Loop (ReAct loop).
"""

from __future__ import annotations

from typing import Any, Optional

from omni.foundation.config.logging import get_logger
from omni.core.context.base import ContextProvider, ContextResult

logger = get_logger("omni.agent.core.context.providers")


class RoutingGuidanceProvider(ContextProvider):
    """
    Layer 1.1: Meta-Cognition Protocol.

    Forces the Agent to 'Think before it Acts'.
    Loads routing protocol from assets/prompts/routing/intent_protocol.md

    Usage:
        from omni.agent.core.context.providers import RoutingGuidanceProvider
        provider = RoutingGuidanceProvider()
    """

    def __init__(self, prompt_name: str = "routing/intent_protocol") -> None:
        self.prompt_name = prompt_name
        self._content: Optional[str] = None

    async def provide(self, state: dict[str, Any], budget: int) -> Optional[ContextResult]:
        # Load from file via API (cached)
        if self._content is None:
            try:
                from omni.agent.core.common.prompts import PromptLoader

                self._content = PromptLoader.load(self.prompt_name, must_exist=False)
            except ImportError:
                # Fallback if PromptLoader not available
                self._content = ""
                logger.warning("PromptLoader not available, routing protocol disabled")

        if not self._content:
            return None

        # Rough token estimate
        token_count = len(self._content.split())

        return ContextResult(
            content=self._content,
            token_count=token_count,
            name="routing_protocol",
            priority=5,  # High priority, just below Persona
        )


__all__ = [
    "RoutingGuidanceProvider",
]
