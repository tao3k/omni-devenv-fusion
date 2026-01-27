"""
main.py - The Grand Unified Router

Facade that整合 (integrates) all routing components into a single entry point.
Migrated from: src/agent/core/router/main.py

Provides:
- Indexer: Memory building
- Semantic: Vector search
- Hybrid: Semantic + Keyword search with LRU caching
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

from .cache import SearchCache
from .hive import HiveRouter
from .hybrid_search import HybridSearch
from .indexer import SkillIndexer
from .router import RouteResult, SemanticRouter
from .sniffer import IntentSniffer

logger = get_logger("omni.core.router.main")


class OmniRouter:
    """
    [The Grand Unified Router]

    Main entry point for all routing operations.
    Integrates Cortex (semantic), Hive (decision), and Sniffer (context).
    Uses HybridSearch (semantic + keyword) with LRU caching.

    Architecture:
        User Query
            ↓
        ┌─────────────────────────────────────┐
        │         OmniRouter (Facade)          │
        └─────────────────────────────────────┘
            ↓           ↓           ↓
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │  Hive   │ │ Hybrid  │ │ Sniffer │
        │ (Logic) │ │+ Cache  │ │(Context)│
        └─────────┘ └─────────┘ └─────────┘
    """

    def __init__(
        self,
        storage_path: str | None = None,
        cache_size: int | None = None,
        cache_ttl: int | None = None,
        semantic_weight: float | None = None,
        keyword_weight: float | None = None,
    ):
        """Initialize the unified router.

        Args:
            storage_path: Path for vector index storage (None = use unified path, ":memory:" for in-memory)
            cache_size: Maximum cache entries (default: from settings or 1000)
            cache_ttl: Cache TTL in seconds (default: from settings or 300)
            semantic_weight: Weight for semantic search (default: from settings or 0.7)
            keyword_weight: Weight for keyword search (default: from settings or 0.3)
        """
        # Load settings from config
        from omni.foundation.config.settings import get_setting

        if cache_size is None:
            cache_size = int(get_setting("router.cache.max_size", 1000))
        if cache_ttl is None:
            cache_ttl = int(get_setting("router.cache.ttl", 300))
        if semantic_weight is None:
            semantic_weight = float(get_setting("router.search.semantic_weight", 0.7))
        if keyword_weight is None:
            keyword_weight = float(get_setting("router.search.keyword_weight", 0.3))

        self._indexer = SkillIndexer(storage_path)
        self._semantic = SemanticRouter(self._indexer)

        # Keyword search disabled - semantic-only mode for Rust
        self._keyword_indexer = None

        self._hybrid = HybridSearch(
            self._indexer,
            keyword_indexer=None,
            semantic_weight=semantic_weight,
            keyword_weight=0.0,  # Disabled
        )
        self._cache = SearchCache(max_size=cache_size, ttl=cache_ttl)
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
    def hybrid(self) -> HybridSearch:
        """Get the hybrid search engine."""
        return self._hybrid

    @property
    def cache(self) -> SearchCache:
        """Get the search cache."""
        return self._cache

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

    async def route(self, query: str, context: dict[str, Any] | None = None) -> RouteResult | None:
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

    async def route_hybrid(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.4,
        use_cache: bool = True,
    ) -> list[RouteResult]:
        """Route using Hybrid Search with caching.

        Uses semantic + keyword search with LRU caching for improved
        performance on repeated queries.

        Flow:
            1. Check Cache -> Return if hit
            2. Hybrid Search (Vector + Keyword)
            3. Update Cache
            4. Return Results

        Args:
            query: User query
            limit: Maximum number of results
            threshold: Minimum score threshold
            use_cache: Whether to use cache

        Returns:
            List of RouteResults sorted by score
        """
        # 1. Cache Lookup
        if use_cache:
            cached = self._cache.get(query)
            if cached:
                logger.debug(f"Cache hit for: {query[:50]}...")
                return cached

        # 2. Hybrid Search
        matches = await self._hybrid.search(query, limit=limit * 2)

        # 3. Convert to RouteResults and filter by threshold
        results: list[RouteResult] = []
        for match in matches:
            if match.combined_score >= threshold:
                # Extract skill and command from id (format: "skill.command" or "skill")
                id_parts = match.id.split(".", 1) if "." in match.id else [match.id, ""]
                skill_name = id_parts[0] if id_parts[0] else "unknown"

                # For command_name, try metadata first, then fall back to id
                if len(id_parts) > 1:
                    command_name = id_parts[1]
                elif match.metadata.get("command"):
                    command_name = match.metadata.get("command")
                elif match.metadata.get("tool_name"):
                    # Handle cases where tool_name is the full id
                    tool_parts = match.metadata.get("tool_name", "").split(".")
                    command_name = tool_parts[-1] if len(tool_parts) > 1 else ""
                else:
                    command_name = ""

                # Skip skill-level entries (not actual tools)
                # Skill entries have empty command_name and type="skill"
                if not command_name:
                    continue

                # Determine confidence (lowercase for RouteConfidence enum)
                if match.combined_score >= 0.75:
                    confidence = "high"
                elif match.combined_score >= 0.5:
                    confidence = "medium"
                else:
                    confidence = "low"

                results.append(
                    RouteResult(
                        skill_name=skill_name,
                        command_name=command_name,
                        score=match.combined_score,
                        confidence=confidence,  # type: ignore
                    )
                )

        # 4. Update Cache
        if use_cache:
            self._cache.set(query, results)

        logger.info(f"Hybrid route: '{query}' -> {len(results)} results")
        return results

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
            "hybrid_stats": self._hybrid.stats(),
            "cache_stats": self._cache.stats(),
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
