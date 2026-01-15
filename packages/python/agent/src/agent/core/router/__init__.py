"""
agent/core/router/__init__.py
 Adaptive Context - Intent-Driven Tool Loading

Router for intent-driven tool loading using hybrid search.
"""

# Import from models.py (SSOT for AgentRoute)
from .models import AgentRoute, RoutingResult

# Import from hive.py (SSOT for HiveRouter)
from .hive import HiveRouter, get_hive_router

# Import from semantic_router.py for backward compatibility
from .semantic_router import (
    SemanticRouter,
    get_router,
    SemanticCortex,
)

# Import from router.py (IntentRouter for tool-level routing)
from .router import IntentRouter, get_intent_router

# Import from main.py for backward compatibility
from .main import clear_routing_cache

__all__ = [
    "AgentRoute",
    "IntentRouter",
    "HiveRouter",
    "SemanticRouter",
    "SemanticCortex",
    "RoutingResult",
    "get_intent_router",
    "get_hive_router",
    "get_router",
    "clear_routing_cache",
]
