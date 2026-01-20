"""
assets/skills/memory/scripts/__init__.py
Export memory commands for external usage (e.g. by NoteTaker).
"""

from __future__ import annotations

from agent.skills.memory.scripts import memory as memory_module

save_memory = memory_module.save_memory
search_memory = memory_module.search_memory
index_memory = memory_module.index_memory
get_memory_stats = memory_module.get_memory_stats
load_skill = memory_module.load_skill

__all__ = [
    "save_memory",
    "search_memory",
    "index_memory",
    "get_memory_stats",
    "load_skill",
]
