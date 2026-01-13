"""
commands - CLI Command Definitions

Phase 35.2: Modular CLI Architecture

Submodules:
- skill.py: Skill management commands
- mcp.py: MCP server management commands
- route.py: Phase 41 Wisdom-Aware Routing commands
"""

from __future__ import annotations

from .skill import skill_app, register_skill_command
from .mcp import register_mcp_command
from .route import route_app, register_route_command

__all__ = [
    "skill_app",
    "register_skill_command",
    "mcp_app",
    "register_mcp_command",
    "route_app",
    "register_route_command",
]
