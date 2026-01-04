"""
src/agent/core/router/cache.py
Hive Mind Cache - LRU cache for routing decisions.

Provides zero-latency routing for high-frequency queries.

Usage:
    from agent.core.router import HiveMindCache, get_cache

    cache = HiveMindCache()
    cache.set("run tests", RoutingResult(...))
    result = cache.get("run tests")
"""
import hashlib
import time
from typing import Dict, Optional

from agent.core.router.models import RoutingResult


class HiveMindCache:
    """
    Simple LRU-style cache for routing decisions.

    Why? High-frequency queries (like "run tests", "commit", "check status")
    don't need to call LLM every time. Direct cache return reduces latency
    from ~2s to ~0ms.

    Features:
    - Exact match on query hash
    - Max size to prevent memory bloat
    - Time-based expiration (TTL)
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, RoutingResult] = {}
        self.max_size = max_size
        self.ttl = ttl_seconds

    def _hash_query(self, query: str) -> str:
        """Generate deterministic hash for query."""
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[RoutingResult]:
        """
        Get cached routing result.

        Returns None if not found or expired.
        """
        query_hash = self._hash_query(query)
        cached = self.cache.get(query_hash)

        if cached is None:
            return None

        # Check TTL
        if time.time() - cached.timestamp > self.ttl:
            del self.cache[query_hash]
            return None

        # Mark as cache hit and return
        cached.from_cache = True
        return cached

    def set(self, query: str, result: RoutingResult):
        """Cache a routing result."""
        query_hash = self._hash_query(query)

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            # Remove first item (simple eviction)
            first_key = next(iter(self.cache))
            del self.cache[first_key]

        self.cache[query_hash] = result

    def clear(self):
        """Clear all cached entries."""
        self.cache.clear()

    def size(self) -> int:
        """Return current cache size."""
        return len(self.cache)

    def contains(self, query: str) -> bool:
        """Check if query is in cache (without TTL check)."""
        query_hash = self._hash_query(query)
        return query_hash in self.cache


# Global cache instance for convenience
_cache_instance: Optional[HiveMindCache] = None


def get_cache() -> HiveMindCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = HiveMindCache()
    return _cache_instance
