# capabilities/learning
"""
Learning Module - The Cycle of Evolution

Phase 32: Modularized subpackage.

Modules:
- harvester.py: Distills wisdom from experience (harvest_session_insight)

Usage:
    # New modular imports (recommended)
    from agent.capabilities.learning.harvester import harvest_session_insight

    # Old imports (still work for backward compatibility)
    from agent.capabilities.learning import harvest_session_insight
"""

from .harvester import (
    harvest_session_insight,
    list_harvested_knowledge,
    get_scratchpad_summary,
    harvest_session_insight_tool,
    list_harvested_knowledge_tool,
    get_scratchpad_summary_tool,
)

# Backward compatibility: Re-export everything
__all__ = [
    "harvest_session_insight",
    "list_harvested_knowledge",
    "get_scratchpad_summary",
    # One Tool compatible aliases
    "harvest_session_insight_tool",
    "list_harvested_knowledge_tool",
    "get_scratchpad_summary_tool",
]
