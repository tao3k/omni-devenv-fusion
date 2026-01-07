# instructions - Project Instructions Loader

"""
Project Instructions Loader

Phase 30: Modularized for testability.

Modules:
- loader.py: Lazy loading implementation

Usage:
    from mcp_core.instructions import get_instructions, get_instruction

    # First call triggers lazy load
    all_instructions = get_instructions()
    project_conventions = get_instruction("project-conventions")
"""

from .loader import (
    get_instructions,
    get_instruction,
    get_all_instructions_merged,
    list_instruction_names,
    reload_instructions,
)

__all__ = [
    "get_instructions",
    "get_instruction",
    "get_all_instructions_merged",
    "list_instruction_names",
    "reload_instructions",
]
