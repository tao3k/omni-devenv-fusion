"""
omni.core.router - Semantic Routing Module

High-performance intent-to-action mapping with Rust-native hybrid search.

Architecture:
- HybridSearch: Rust-native (omni-vector) for vector + keyword search
- HiveRouter: Decision logic layer
- IntentSniffer: Context-aware skill suggestions
- OmniRouter: Unified facade

Migration: Python-side hybrid search logic moved to Rust (omni-vector).
The Python HybridSearch is now a thin shell over Rust's search_tools.

Usage:
    from omni.core.router import OmniRouter, HybridSearch

    # Use unified router
    router = OmniRouter()
    await router.initialize(skills)
    result = await router.route("commit the changes")

    # Or use hybrid search directly (Rust-native)
    results = await router.hybrid.search("git commit", limit=5)
"""

from .cache import SearchCache
from .hive import HiveRouter, MultiHiveRouter
from .hybrid_search import HybridMatch, HybridSearch
from .indexer import IndexedSkill, SkillIndexer
from .main import OmniRouter, RouterRegistry, get_router
from .router import (
    FallbackRouter,
    RouteResult,
    SemanticRouter,
    UnifiedRouter,
)
from .sniffer import ActivationRule, ContextualSniffer, IntentSniffer

__all__ = [
    # Cache
    "SearchCache",
    # Indexer
    "SkillIndexer",
    "IndexedSkill",
    # Router
    "SemanticRouter",
    "FallbackRouter",
    "UnifiedRouter",
    "RouteResult",
    # Hybrid Search
    "HybridSearch",
    "HybridMatch",
    # Hive
    "HiveRouter",
    "MultiHiveRouter",
    # Sniffer
    "IntentSniffer",
    "ContextualSniffer",
    "ActivationRule",
    # Facade
    "OmniRouter",
    "RouterRegistry",
    "get_router",
]
