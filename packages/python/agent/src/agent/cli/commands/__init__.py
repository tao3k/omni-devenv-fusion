"""commands - CLI Command Definitions"""

from __future__ import annotations

from .skill import skill_app, register_skill_command
from .mcp import register_mcp_command
from .route import route_app, register_route_command
from .run import run_app, register_run_command

__all__ = [
    "skill_app",
    "register_skill_command",
    "register_mcp_command",
    "route_app",
    "register_route_command",
    "run_app",
    "register_run_command",
]
