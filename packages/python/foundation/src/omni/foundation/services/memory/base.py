# base.py
"""
Project Memory - Long-term memory storage using ADR pattern.

This module re-exports the unified ProjectMemory interface and utilities
from the modular submodules.

Modules:
- core.project_memory: Main ProjectMemory class
- core.interface: Data types and interfaces
- core.utils: Shared utilities
- stores.lancedb: LanceDB storage implementation
"""

from omni.foundation.services.memory.core.interface import (
    STORAGE_MODE_LANCE,
    StorageMode,
)
from omni.foundation.services.memory.core.project_memory import (
    MEMORY_DIR,
    ProjectMemory,
    init_memory_dir,
)
from omni.foundation.services.memory.core.utils import format_decision, parse_decision

__all__ = [
    "MEMORY_DIR",
    "STORAGE_MODE_LANCE",
    "ProjectMemory",
    "StorageMode",
    "format_decision",
    "init_memory_dir",
    "parse_decision",
]
