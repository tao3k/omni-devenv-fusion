"""
src/agent/core/router/main.py
Main Router Utilities - Singleton management and utilities.

Contains:
- clear_routing_cache(): Clear all routing caches
- Router singleton management

Usage:
    from agent.core.router import clear_routing_cache, get_router, get_hive_router
"""

from agent.core.router.cache import HiveMindCache
from agent.core.router.semantic_router import get_router, SemanticRouter
from agent.core.router.hive import get_hive_router, HiveRouter


def clear_routing_cache():
    """Clear the Hive Mind Cache. Useful for debugging or after major changes."""
    router = get_router()
    if hasattr(router, "cache") and isinstance(router.cache, HiveMindCache):
        router.cache.cache.clear()

    # Also clear hive router cache
    hive_router = get_hive_router()
    if hasattr(hive_router, "clear_cache"):
        hive_router.clear_cache()
