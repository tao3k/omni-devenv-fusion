"""
skill/scripts/ - Skill Management Scripts

Contains atomic implementations for skill-related commands:
- templates.py: Cascading template management
- list_tools.py: List registered MCP tools
"""

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

__all__ = [
    "list_templates",
    "get_template_info",
    "get_template_source",
    "eject_template",
    "format_template_list",
    "format_eject_result",
    "format_info_result",
    "format_tools_list",
]
