"""
agent/core/router/__init__.py
Phase 67: Adaptive Context - Intent-Driven Tool Loading

Router for intent-driven tool loading using hybrid search.
"""

from .router import IntentRouter, get_intent_router

# Backward compatibility alias
get_hive_router = get_intent_router

__all__ = ["IntentRouter", "get_intent_router", "get_hive_router"]
