# memory - Project Memory Persistence Module

"""
Project Memory Persistence Module

Modularized for testability.

Modules:
- base.py: ProjectMemory class and utilities
- core: Core interfaces, types, and utilities
- stores: Storage implementations (LanceDB)

Usage:
    from omni.foundation.services.memory import ProjectMemory

    memory = ProjectMemory()
    memory.add_decision(title="ADR Title", problem="...", solution="...")
    decisions = memory.list_decisions()
"""

from .base import (
    MEMORY_DIR,
    STORAGE_MODE_LANCE,
    ProjectMemory,
    StorageMode,
    format_decision,
    init_memory_dir,
    parse_decision,
)

__all__ = [
    "MEMORY_DIR",
    "STORAGE_MODE_LANCE",
    "ProjectMemory",
    "StorageMode",
    "format_decision",
    "init_memory_dir",
    "parse_decision",
]
