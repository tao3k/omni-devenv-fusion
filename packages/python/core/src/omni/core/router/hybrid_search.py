"""
hybrid_search.py - Hybrid Search (Semantic + Keyword)

Combines semantic vector search with keyword matching for improved relevance.

Features:
- Dual search: Semantic + Keyword
- Configurable weights for result fusion
- Re-ranking of combined results
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from omni.foundation.bridge import SearchResult
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.hybrid")


class HybridMatch(BaseModel):
    """Represents a match from hybrid search."""

    model_config = ConfigDict(frozen=True)

    id: str
    content: str
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    metadata: dict[str, Any] = {}


class HybridSearch:
    """
    [Hybrid Search Engine]

    Combines semantic search (vector similarity) with keyword matching
    for improved search relevance and recall.

    Formula: combined_score = semantic_weight * semantic_score + keyword_weight * keyword_score

    Usage:
        search = HybridSearch(indexer, cache)
        results = await search.search("git commit", limit=5)
    """

    def __init__(
        self,
        semantic_indexer,
        keyword_indexer=None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> None:
        """Initialize hybrid search.

        Args:
            semantic_indexer: Semantic search provider (e.g., SkillIndexer)
            keyword_indexer: Keyword search provider (optional)
            semantic_weight: Weight for semantic search results (0.0-1.0)
            keyword_weight: Weight for keyword search results (0.0-1.0)
        """
        self._semantic_indexer = semantic_indexer
        self._keyword_indexer = keyword_indexer
        self._semantic_weight = semantic_weight
        self._keyword_weight = keyword_weight

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[HybridMatch]:
        """Perform hybrid search.

        Args:
            query: Search query
            limit: Maximum number of results
            min_score: Minimum combined score threshold

        Returns:
            List of HybridMatch objects sorted by combined score
        """
        # Normalize weights
        total_weight = self._semantic_weight + self._keyword_weight
        if total_weight == 0:
            self._semantic_weight = 0.7
            self._keyword_weight = 0.3
        else:
            self._semantic_weight /= total_weight
            self._keyword_weight /= total_weight

        # Execute searches in parallel
        semantic_results, keyword_results = await self._execute_searches(query, limit)

        # Merge and re-rank
        matches = self._merge_results(semantic_results, keyword_results)

        # Apply minimum score filter and limit
        filtered = [m for m in matches if m.combined_score >= min_score]
        return filtered[:limit]

    async def _execute_searches(
        self,
        query: str,
        limit: int,
    ) -> tuple[list[SearchResult], list[SearchResult]]:
        """Execute semantic and keyword searches in parallel."""
        import asyncio

        semantic_result = self._semantic_indexer.search(query, limit=limit * 2)

        if asyncio.iscoroutine(semantic_result):
            semantic_result = await semantic_result

        if self._keyword_indexer:
            keyword_result = self._keyword_indexer.search(query, limit=limit * 2)
            if asyncio.iscoroutine(keyword_result):
                keyword_result = await keyword_result
            keyword_results = keyword_result if isinstance(keyword_result, list) else []
        else:
            keyword_results = self._keyword_search(query, limit * 2)

        semantic_results = semantic_result if isinstance(semantic_result, list) else []

        return semantic_results, keyword_results

    def _keyword_search(self, query: str, limit: int) -> list[SearchResult]:
        """Perform simple keyword matching against indexed content."""
        # Keyword search is deprecated - use semantic search only
        logger.debug(f"Keyword search for '{query}': disabled (Rust-only mode)")
        return []

    def _merge_results(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
    ) -> list[HybridMatch]:
        """Merge semantic and keyword results with scoring."""
        match_map: dict[str, HybridMatch] = {}

        # Process semantic results
        for i, result in enumerate(semantic_results):
            semantic_score = 1.0 - (i * 0.05)
            if result.score > 0:
                semantic_score = min(1.0, result.score)

            match = HybridMatch(
                id=result.id,
                content=result.payload.get("content", ""),
                semantic_score=semantic_score,
                keyword_score=0.0,
                combined_score=semantic_score * self._semantic_weight,
                metadata=result.payload,
            )
            match_map[result.id] = match

        # Process keyword results
        for i, result in enumerate(keyword_results):
            if result.id in match_map:
                match = match_map[result.id]
                keyword_score = 1.0 - (i * 0.05)
                if result.score > 0:
                    keyword_score = min(1.0, result.score)
                match.keyword_score = keyword_score
                match.combined_score = (
                    match.semantic_score * self._semantic_weight
                    + keyword_score * self._keyword_weight
                )
            else:
                keyword_score = 1.0 - (i * 0.05)
                if result.score > 0:
                    keyword_score = min(1.0, result.score)

                match = HybridMatch(
                    id=result.id,
                    content=result.payload.get("content", ""),
                    semantic_score=0.0,
                    keyword_score=keyword_score,
                    combined_score=keyword_score * self._keyword_weight,
                    metadata=result.payload,
                )
                match_map[result.id] = match

        matches = list(match_map.values())
        matches.sort(key=lambda m: m.combined_score, reverse=True)

        return matches

    def set_weights(self, semantic: float, keyword: float) -> None:
        """Set search weights dynamically."""
        self._semantic_weight = semantic
        self._keyword_weight = keyword
        logger.info(f"Updated weights: semantic={semantic}, keyword={keyword}")

    def get_weights(self) -> tuple[float, float]:
        """Get current search weights."""
        return self._semantic_weight, self._keyword_weight

    def stats(self) -> dict[str, Any]:
        """Get hybrid search statistics."""
        return {
            "semantic_weight": self._semantic_weight,
            "keyword_weight": self._keyword_weight,
            "has_keyword_indexer": self._keyword_indexer is not None,
        }


__all__ = ["HybridSearch", "HybridMatch"]
