"""
src/agent/core/router/semantic_router.py
Semantic Router - Tool selection with Mission Brief Protocol.

This file is a backward compatibility wrapper.
The actual implementation is now in agent.core.router.semantic package.

Routes user requests to appropriate Skills using:
- Semantic Cortex for fuzzy matching
- Virtual Loading via Vector Discovery (local skills only)
- Adaptive Confidence based on Score Gap
- Wisdom-Aware Routing - Inject past lessons from harvested knowledge
- State-Aware Routing - Inject environment state (Git, active context)

Usage:
    # Old import (still works)
    from agent.core.router.semantic_router import SemanticRouter, get_router

    # New import (recommended)
    from agent.core.router.semantic import SemanticRouter, get_router

    router = get_router()
    result = await router.route("Fix the bug in router.py")
"""

from __future__ import annotations

# Re-export get_skill_registry for backward compatibility with tests
from agent.core.skill_registry import get_skill_registry

# Re-export everything from the semantic package for backward compatibility
from agent.core.router.semantic import (
    # Main classes
    SemanticRouter,
    SemanticCortex,
    _LazySemanticCortex,
    # Singleton accessor
    get_router,
    # Lazy accessors
    _get_inference_client,
    _get_cache,
    _get_semantic_cortex,
    _get_vector_discovery,
    _get_librarian,
    _get_sniffer,
    # Fallback
    try_vector_fallback,
    # Constants
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
    # Backward compatibility
    "get_skill_registry",
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
