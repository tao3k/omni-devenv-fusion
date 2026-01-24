"""
hive.py - The Hive Mind Router

Advanced aggregator router that combines semantic routing with contextual rules.
Migrated from: src/agent/core/router/hive.py

The Hive Mind orchestrates multiple routing strategies:
1. Semantic routing (Cortex) - Vector-based intent matching
2. Pattern-based routing - Explicit command patterns
3. Context-aware routing - Environment sniffing
"""

from __future__ import annotations

import re
from typing import Any

from omni.foundation.config.logging import get_logger

from .router import RouteResult, SemanticRouter

logger = get_logger("omni.core.router.hive")


class FallbackRouter:
    """Fallback router when no explicit route is found."""

    async def route(
        self, query: str, context: dict[str, Any] | None = None
    ) -> RouteResult | None:
        """Return None to indicate no route found."""
        return None


class HiveRouter:
    """
    [The Hive Mind]

    Advanced aggregator router that combines multiple routing strategies.
    Uses a "swarm intelligence" approach to select the best routing path.

    Decision Logic:
    1. Check explicit command patterns (git.status, memory.save)
    2. Semantic routing via Cortex (vector search)
    3. Context-aware routing via Sniffer
    4. None means escalation to LLM Planner

    Usage:
        hive = HiveRouter(semantic_router)
        result = await hive.route("帮我提交代码")
    """

    # Explicit command pattern: skill.command
    EXPLICIT_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)$")

    def __init__(self, semantic_router: SemanticRouter):
        """Initialize Hive with a semantic router.

        Args:
            semantic_router: The Cortex/SemanticRouter for vector-based routing
        """
        self._semantic = semantic_router
        self._fallback = FallbackRouter()

    async def route(
        self, query: str, context: dict[str, Any] | None = None
    ) -> RouteResult | None:
        """Route a query using the Hive Mind strategy.

        Args:
            query: User's natural language input or explicit command
            context: Optional context (cwd, file types, git status, etc.)

        Returns:
            RouteResult if a route is found, None for LLM escalation
        """
        query = query.strip()
        if not query:
            return None

        # Strategy 1: Explicit Command Pattern (git.status)
        if match := self.EXPLICIT_PATTERN.match(query):
            skill_name = match.group(1)
            command_name = match.group(2)

            logger.debug(f"🐝 Hive matched explicit pattern: {skill_name}.{command_name}")
            return RouteResult(
                skill_name=skill_name,
                command_name=command_name,
                score=1.0,
                confidence="high",
            )

        # Strategy 2: Semantic Routing (Cortex)
        semantic_result = await self._semantic.route(query)
        if semantic_result:
            logger.info(
                f"🐝 Hive selected via Semantic: {semantic_result.skill_name}.{semantic_result.command_name}"
            )
            return semantic_result

        # Strategy 3: Context-aware fallback (based on cwd/environment)
        if context:
            route_from_context = self._route_from_context(query, context)
            if route_from_context:
                return route_from_context

        # No route found - escalate to LLM Planner
        logger.debug(f"🐝 Hive could not route: '{query}'")
        return None

    def _route_from_context(self, query: str, context: dict[str, Any]) -> RouteResult | None:
        """Route based on current context (cwd, file types, etc.).

        Args:
            query: User query
            context: Execution context with cwd, env, etc.

        Returns:
            RouteResult if context suggests a skill, None otherwise
        """
        import os

        cwd = context.get("cwd", "")
        if not cwd:
            return None

        # Check git context
        if os.path.exists(os.path.join(cwd, ".git")):
            if any(keyword in query.lower() for keyword in ["commit", "push", "branch", "status"]):
                return RouteResult(
                    skill_name="git",
                    command_name="status",  # Default to status, let skill refine
                    score=0.6,
                    confidence="low",
                )

        # Check Python context
        if os.path.exists(os.path.join(cwd, "pyproject.toml")) or os.path.exists(
            os.path.join(cwd, "requirements.txt")
        ):
            if "test" in query.lower() or "pytest" in query.lower():
                return RouteResult(
                    skill_name="testing",
                    command_name="run",
                    score=0.6,
                    confidence="low",
                )

        return None

    @property
    def is_ready(self) -> bool:
        """Check if the Hive is ready to route."""
        return self._semantic.is_ready()


class MultiHiveRouter:
    """
    [The Swarm]

    For complex scenarios where multiple routers might be needed.
    Routes to different "hives" based on domain or context.

    This is a higher-level abstraction for scaling routing.
    """

    def __init__(self):
        self._hives: dict[str, HiveRouter] = {}
        self._default_hive: HiveRouter | None = None

    def register_hive(self, name: str, hive: HiveRouter) -> None:
        """Register a specialized hive for a domain."""
        self._hives[name] = hive

    def set_default_hive(self, hive: HiveRouter) -> None:
        """Set the default hive for unhandled domains."""
        self._default_hive = hive

    async def route(
        self, query: str, domain: str = "default", context: dict | None = None
    ) -> RouteResult | None:
        """Route to a specific hive based on domain."""
        hive = self._hives.get(domain, self._default_hive)
        if hive:
            return await hive.route(query, context)
        return None


__all__ = ["HiveRouter", "MultiHiveRouter"]
