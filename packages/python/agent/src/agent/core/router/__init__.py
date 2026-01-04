"""
src/agent/core/router/__init__.py
Router Package - The Cortex for task and agent routing.

Modules:
- models: Data structures (RoutingResult, AgentRoute, etc.)
- cache: LRU cache for routing decisions
- semantic_router: Tool selection routing
- hive_router: Agent delegation routing
- main_router: Utilities and singleton management

Usage:
    from agent.core.router import get_router, get_hive_router, RoutingResult, AgentRoute
"""

from agent.core.router.models import (
    RoutingResult,
    AgentRoute,
    TaskBrief,
    AgentResponse,
    Decision,
    ToolCall,
    AGENT_PERSONAS,
)

from agent.core.router.cache import HiveMindCache, get_cache

from agent.core.router.semantic_router import SemanticRouter, SemanticCortex, get_router

from agent.core.router.hive import HiveRouter, get_hive_router

from agent.core.router.main import clear_routing_cache

__all__ = [
    # Models
    "RoutingResult",
    "AgentRoute",
    "TaskBrief",
    "AgentResponse",
    "Decision",
    "ToolCall",
    "AGENT_PERSONAS",
    # Cache
    "HiveMindCache",
    "get_cache",
    # Routers
    "SemanticRouter",
    "SemanticCortex",
    "get_router",
    "HiveRouter",
    "get_hive_router",
    # Utilities
    "clear_routing_cache",
]
