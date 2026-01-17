"""
skill/scripts/ - Skill Management Scripts

Contains atomic implementations for skill-related commands:
- discovery.py: Skill discovery and suggestion
- templates.py: Cascading template management
- list_tools.py: List registered MCP tools
- search_tools.py: Intent-driven tool search
- unload.py: Dynamic skill unload
- reload.py: Dynamic skill reload
"""

from __future__ import annotations

from agent.skills.skill.scripts.discovery import (
    discover,
    suggest,
    jit_install,
    list_index,
)
from agent.skills.skill.scripts.templates import (
    list_templates,
    get_template_info,
    get_template_source,
    eject_template,
    format_template_list,
    format_eject_result,
    format_info_result,
)
from agent.skills.skill.scripts.list_tools import list_tools, format_tools_list
from agent.skills.skill.scripts.search_tools import search_tools, format_search_result
from agent.skills.skill.scripts.unload import unload_skill
from agent.skills.skill.scripts.reload import reload_skill

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
    # Tool list command
    "list_tools",
    # Search commands
    "search_tools",
    "format_search_result",
    # Unload/Reload commands
    "unload_skill",
    "reload_skill",
]
