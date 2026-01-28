"""commands - CLI Command Definitions"""

from __future__ import annotations

from .mcp import register_mcp_command
from .route import register_route_command, route_app
from .run import register_run_command
from .skill import register_skill_command, skill_app
from .sync import register_sync_command, sync_app

__all__ = [
    "register_mcp_command",
    "register_route_command",
    "register_run_command",
    "register_skill_command",
    "register_sync_command",
    "route_app",
    "skill_app",
    "sync_app",
]
