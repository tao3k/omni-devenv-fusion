"""
kernel/components/ - Unified Kernel Components

Provides unified implementations for:
- registry.py: Unified skill registry (skill_runtime + skill_registry merged)
- skill_plugin.py: Skill Plugin interface
- skill_loader.py: Skill script loader
- mcp_tool.py: MCP tool adapter

These components replace duplicate code in skill_registry.
"""

from __future__ import annotations

# Re-export MCP tool adapter
from .mcp_tool import MCPToolAdapter

# Re-export unified registry
from .registry import UnifiedRegistry

# Re-export skill loader
from .skill_loader import extract_tool_schema, load_skill_scripts

# Re-export skill plugin interface
from .skill_plugin import ISkillPlugin, SkillPluginWrapper

__all__ = [
    "ISkillPlugin",
    "MCPToolAdapter",
    "SkillPluginWrapper",
    "UnifiedRegistry",
    "extract_tool_schema",
    "load_skill_scripts",
]
