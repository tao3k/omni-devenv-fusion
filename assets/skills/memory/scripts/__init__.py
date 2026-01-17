"""
assets/skills/memory/scripts/__init__.py
Export memory commands for external usage (e.g. by NoteTaker).
"""

from __future__ import annotations

from agent.skills.memory.scripts.memory import (
    save_memory,
    search_memory,
    index_memory,
    get_memory_stats,
    load_skill,
)

__all__ = [
    "save_memory",
    "search_memory",
    "index_memory",
    "get_memory_stats",
    "load_skill",
]
