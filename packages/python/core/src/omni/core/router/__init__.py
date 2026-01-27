"""
omni.core.router - Semantic Routing Module

High-performance intent-to-action mapping using vector search.
Migrated from: src/agent/core/router/

Modules:
- cache: Search result caching (LRU with TTL)
- indexer: Build semantic index from skills
- router: Route natural language to commands
- hive: The Hive Mind (advanced routing strategy)
- sniffer: Context-aware skill suggestions
- main: Unified router facade

Usage:
    from omni.core.router import OmniRouter, HiveRouter, IntentSniffer

    # Use unified router
    router = OmniRouter()
    await router.initialize(skills)
    result = await router.route("帮我提交代码")

    # Or use components directly
    hive = HiveRouter(semantic_router)
    sniffer = IntentSniffer()
    suggestions = sniffer.sniff("/path/to/project")
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
