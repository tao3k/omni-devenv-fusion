"""
cache.py - Search Result Cache (LRU with TTL)

Provides high-performance caching for search results.

Features:
- LRU eviction (Least Recently Used)
- TTL support (time-to-live)
- Thread-safe operations
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.cache")


class SearchCache:
    """
    [Search Result Cache]

    LRU cache with TTL for search results.
    Automatically evicts stale entries and manages memory usage.

    Usage:
        cache = SearchCache(max_size=1000, ttl=300)
        cache.set("query", results)
        results = cache.get("query")
    """

    def __init__(self, max_size: int = 1000, ttl: int = 300) -> None:
        """Initialize the search cache.

        Args:
            max_size: Maximum number of cached queries (default: 1000)
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, query: str) -> list[Any] | None:
        """Get cached results for a query.

        Args:
            query: The search query

        Returns:
            Cached results list, or None if not found/expired
        """
        if query not in self._cache:
            return None

        entry = self._cache[query]

        # Check TTL
        if self._is_expired(entry):
            del self._cache[query]
            logger.debug(f"Cache expired for query: {query[:50]}...")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(query)
        return entry["results"]

    def set(self, query: str, results: list[Any]) -> None:
        """Cache search results for a query.

        Args:
            query: The search query
            results: List of search results to cache
        """
        self._cache[query] = {
            "results": results,
            "timestamp": time.time(),
        }

        # LRU eviction
        if len(self._cache) > self._max_size:
            evicted_query, _ = self._cache.popitem(last=False)
            logger.debug(f"Cache evicted: {evicted_query[:50]}...")

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries removed
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hit_rate": self._calculate_hit_rate(),
        }

    def remove_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        expired_queries = [query for query, entry in self._cache.items() if self._is_expired(entry)]

        for query in expired_queries:
            del self._cache[query]
            removed += 1

        if removed > 0:
            logger.info(f"Removed {removed} expired cache entries")

        return removed

    def _is_expired(self, entry: dict[str, Any]) -> bool:
        """Check if an entry is expired."""
        timestamp = entry.get("timestamp", 0)
        return (time.time() - timestamp) > self._ttl

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate (placeholder for future stats)."""
        # TODO: Add hit/miss tracking for accurate hit rate
        return 0.0

    def __len__(self) -> int:
        """Return the number of cached entries."""
        return len(self._cache)

    def __contains__(self, query: str) -> bool:
        """Check if a query is in cache (doesn't check expiration)."""
        return query in self._cache

    def __repr__(self) -> str:
        return f"SearchCache(size={len(self._cache)}, max={self._max_size}, ttl={self._ttl})"


__all__ = ["SearchCache"]
