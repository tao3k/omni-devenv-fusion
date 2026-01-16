# agent/core/router/semantic/__init__.py
"""
Semantic Router Package - Tool selection with Mission Brief Protocol.

Routes user requests to appropriate Skills using:
- Semantic Cortex for fuzzy matching
- Virtual Loading via Vector Discovery (local skills only)
- Adaptive Confidence based on Score Gap
- Wisdom-Aware Routing
- State-Aware Routing

Usage:
    from agent.core.router.semantic import get_router, SemanticRouter

    router = get_router()
    result = await router.route("Fix the bug in router.py")
"""

from __future__ import annotations

# Re-export main classes and functions for backward compatibility
from .router import (
    SemanticRouter,
    get_router,
    _get_inference_client,
    _get_cache,
    _get_semantic_cortex,
    _get_vector_discovery,
    _get_librarian,
    _get_sniffer,
)

from .cortex import (
    _LazySemanticCortex,
    SemanticCortex,  # Backward compatibility alias
)

from .fallback import (
    try_vector_fallback,
    CONFIDENCE_HIGH_GAP,
    CONFIDENCE_LOW_GAP,
    CONFIDENCE_MAX_BOOST,
    CONFIDENCE_MAX_PENALTY,
)

__all__ = [
    # Main classes
    "SemanticRouter",
    "SemanticCortex",
    "_LazySemanticCortex",
    # Singleton accessor
    "get_router",
    # Lazy accessors
    "_get_inference_client",
    "_get_cache",
    "_get_semantic_cortex",
    "_get_vector_discovery",
    "_get_librarian",
    "_get_sniffer",
    # Fallback
    "try_vector_fallback",
    # Constants
    "CONFIDENCE_HIGH_GAP",
    "CONFIDENCE_LOW_GAP",
    "CONFIDENCE_MAX_BOOST",
    "CONFIDENCE_MAX_PENALTY",
]
