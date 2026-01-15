"""
skill/scripts/ - Skill Management Scripts

Contains atomic implementations for skill-related commands:
- discovery.py: Skill discovery and suggestion (Phase 63)
- templates.py: Cascading template management
- list_tools.py: List registered MCP tools
- search_tools.py: Intent-driven tool search (Phase 67)
"""

from .discovery import (
    discover,
    suggest,
    jit_install,
    list_index,
)
from .templates import (
    list_templates,
    get_template_info,
    get_template_source,
    eject_template,
    format_template_list,
    format_eject_result,
    format_info_result,
)
from .list_tools import format_tools_list
from .search_tools import search_tools, format_search_result

__all__ = [
    # Discovery commands
    "discover",
    "suggest",
    "jit_install",
    "list_index",
    # Template commands
    "list_templates",
    "get_template_info",
    "get_template_source",
    "eject_template",
    "format_template_list",
    "format_eject_result",
    "format_info_result",
    "format_tools_list",
    # Search commands (Phase 67)
    "search_tools",
    "format_search_result",
]
