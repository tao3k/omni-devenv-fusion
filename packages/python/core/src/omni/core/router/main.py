"""
main.py - The Grand Unified Router

Facade that整合 (integrates) all routing components into a single entry point.
Migrated from: src/agent/core/router/main.py

Provides:
- Indexer: Memory building
- Semantic: Vector search
- Hive: Decision logic
- Sniffer: Context awareness

Usage:
    router = OmniRouter()
    await router.initialize(skills)
    result = await router.route("帮我提交代码")
"""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger

from .hive import HiveRouter
from .indexer import SkillIndexer
from .router import RouteResult, SemanticRouter
from .sniffer import IntentSniffer

logger = get_logger("omni.core.router.main")


class OmniRouter:
    """
    [The Grand Unified Router]

    Main entry point for all routing operations.
    Integrates Cortex (semantic), Hive (decision), and Sniffer (context).

    Architecture:
        User Query
            ↓
        ┌─────────────────────────────────────┐
        │         OmniRouter (Facade)          │
        └─────────────────────────────────────┘
            ↓           ↓           ↓
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │  Hive   │ │ Semantic │ │ Sniffer │
        │ (Logic) │ │ (Match)  │ │(Context)│
        └─────────┘ └─────────┘ └─────────┘
    """

    def __init__(self, storage_path: str = ":memory:"):
        """Initialize the unified router.

        Args:
            storage_path: Path for vector index storage (":memory:" for in-memory)
        """
        self._indexer = SkillIndexer(storage_path)
        self._semantic = SemanticRouter(self._indexer)
        self._hive = HiveRouter(self._semantic)
        self._sniffer = IntentSniffer()
        self._initialized = False

    @property
    def indexer(self) -> SkillIndexer:
        """Get the skill indexer."""
        return self._indexer

    @property
    def semantic(self) -> SemanticRouter:
        """Get the semantic router."""
        return self._semantic

    @property
    def hive(self) -> HiveRouter:
        """Get the hive router."""
        return self._hive

    @property
    def sniffer(self) -> IntentSniffer:
        """Get the intent sniffer."""
        return self._sniffer

    async def initialize(self, skills: list[dict[str, Any]]) -> None:
        """Initialize the router and build the cortex.

        Args:
            skills: List of skill metadata dicts
        """
        if self._initialized:
            logger.warning("OmniRouter already initialized")
            return

        await self._indexer.index_skills(skills)
        self._initialized = True

        stats = self._indexer.get_stats()
        logger.info(f"🧠 OmniRouter initialized with {stats['entries_indexed']} indexed entries")

    async def route(
        self, query: str, context: dict[str, Any] | None = None
    ) -> RouteResult | None:
        """Route a query using the unified routing strategy.

        Args:
            query: User query (natural language or explicit command)
            context: Optional execution context

        Returns:
            RouteResult if routed, None for LLM escalation
        """
        if not self._initialized:
            logger.warning("OmniRouter not initialized, falling back to direct routing")
            return await self._hive.route(query, context)

        return await self._hive.route(query, context)

    async def suggest_skills(self, cwd: str) -> list[str]:
        """Suggest skills based on current context.

        Args:
            cwd: Current working directory

        Returns:
            List of suggested skill names
        """
        return self._sniffer.sniff(cwd)

    def is_ready(self) -> bool:
        """Check if the router is ready."""
        return self._initialized and self._indexer.is_ready

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        return {
            "initialized": self._initialized,
            "indexer_stats": self._indexer.get_stats(),
            "is_ready": self.is_ready(),
        }


class RouterRegistry:
    """
    [Router Factory & Registry]

    Manages multiple router instances for different domains or sessions.
    """

    _instances: dict[str, OmniRouter] = {}
    _default: str = "default"

    @classmethod
    def get(cls, name: str | None = None) -> OmniRouter:
        """Get or create a router instance."""
        name = name or cls._default
        if name not in cls._instances:
            cls._instances[name] = OmniRouter()
        return cls._instances[name]

    @classmethod
    def set_default(cls, name: str) -> None:
        """Set the default router name."""
        cls._default = name

    @classmethod
    def reset(cls, name: str | None = None) -> None:
        """Reset a router instance."""
        name = name or cls._default
        if name in cls._instances:
            del cls._instances[name]

    @classmethod
    def reset_all(cls) -> None:
        """Reset all router instances."""
        cls._instances.clear()


def get_router(name: str | None = None) -> OmniRouter:
    """Convenience function to get a router instance."""
    return RouterRegistry.get(name)


__all__ = ["OmniRouter", "RouterRegistry", "get_router"]
