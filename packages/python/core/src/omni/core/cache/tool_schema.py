"""
omni.core.cache.tool_schema - Tool Schema Cache

Caches tool schemas with TTL support for performance optimization.

Usage:
    from omni.core.cache.tool_schema import ToolSchemaCache, get_schema_cache

    cache = get_schema_cache()
    schema = cache.get("git.status")
    if schema is None:
        schema = extract_schema(handler)
        cache.set("git.status", schema)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.cache.tool_schema")


class ToolSchemaCache:
    """Thread-safe cache for tool schemas with TTL support."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize schema cache.

        Args:
            ttl_seconds: Time-to-live for cached schemas in seconds
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, tool_name: str) -> dict[str, Any] | None:
        """Get cached schema for a tool.

        Args:
            tool_name: Full tool name (e.g., "git.status")

        Returns:
            Cached schema dict or None if not found/expired
        """
        with self._lock:
            if tool_name not in self._cache:
                return None

            # Check TTL
            timestamp = self._timestamps.get(tool_name, 0)
            if time.time() - timestamp > self._ttl:
                # Expired - remove
                del self._cache[tool_name]
                del self._timestamps[tool_name]
                logger.debug(f"Schema cache expired for: {tool_name}")
                return None

            return self._cache[tool_name].copy()

    def set(self, tool_name: str, schema: dict[str, Any]) -> None:
        """Cache a tool schema.

        Args:
            tool_name: Full tool name
            schema: Tool schema dictionary
        """
        with self._lock:
            self._cache[tool_name] = schema.copy()
            self._timestamps[tool_name] = time.time()
            logger.debug(f"Cached schema for: {tool_name}")

    def invalidate(self, tool_name: str | None = None) -> None:
        """Invalidate cached schema(s).

        Args:
            tool_name: Specific tool to invalidate, or None for all
        """
        with self._lock:
            if tool_name is None:
                count = len(self._cache)
                self._cache.clear()
                self._timestamps.clear()
                logger.info(f"Invalidated all {count} cached schemas")
            else:
                if tool_name in self._cache:
                    del self._cache[tool_name]
                    del self._timestamps[tool_name]
                    logger.debug(f"Invalidated schema for: {tool_name}")

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            expired = [name for name, ts in self._timestamps.items() if now - ts > self._ttl]

            for name in expired:
                del self._cache[name]
                del self._timestamps[name]

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired schema entries")

            return len(expired)

    @property
    def size(self) -> int:
        """Get number of cached entries."""
        with self._lock:
            return len(self._cache)

    def get_ttl(self) -> int:
        """Get current TTL setting."""
        return self._ttl

    def set_ttl(self, seconds: int) -> None:
        """Set TTL for new entries.

        Args:
            seconds: New TTL in seconds
        """
        with self._lock:
            self._ttl = seconds


# Global cache singleton
_schema_cache: ToolSchemaCache | None = None


def get_schema_cache() -> ToolSchemaCache:
    """Get or create the global schema cache.

    Returns:
        ToolSchemaCache instance
    """
    global _schema_cache
    if _schema_cache is None:
        # Load TTL from config
        try:
            from omni.core.config.loader import load_skill_limits

            limits = load_skill_limits()
            _schema_cache = ToolSchemaCache(ttl_seconds=limits.schema_cache_ttl)
        except Exception:
            _schema_cache = ToolSchemaCache()

    return _schema_cache


def reset_cache() -> None:
    """Reset the global cache (for testing)."""
    global _schema_cache
    if _schema_cache is not None:
        _schema_cache.invalidate()
    _schema_cache = None


# Utility function for extracting schemas with caching
def get_cached_schema(
    tool_name: str,
    extractor: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Get schema from cache or extract and cache it.

    Args:
        tool_name: Tool name for cache key
        extractor: Function to extract schema if not cached

    Returns:
        Tool schema dictionary
    """
    cache = get_schema_cache()

    # Try cache first
    schema = cache.get(tool_name)
    if schema is not None:
        logger.debug(f"Schema cache hit: {tool_name}")
        return schema

    # Extract and cache
    logger.debug(f"Schema cache miss: {tool_name}")
    schema = extractor()
    cache.set(tool_name, schema)
    return schema


__all__ = [
    "ToolSchemaCache",
    "get_cached_schema",
    "get_schema_cache",
    "reset_cache",
]
