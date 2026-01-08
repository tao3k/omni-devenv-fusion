"""
agent/core/orchestrator/protocol.py
IOrchestrator Protocol for Orchestrator.

ODF-EP v6.0 Pillar B: Protocol-Oriented Design.
"""

from typing import Dict, Any, List, Protocol, runtime_checkable

from agent.core.session import SessionManager


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


__all__ = ["IOrchestrator"]
