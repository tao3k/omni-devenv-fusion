"""commands - CLI Command Definitions"""

from __future__ import annotations

from .ingest import ingest_app, register_ingest_command
from .mcp import register_mcp_command
from .route import register_route_command, route_app
from .run import register_run_command
from .skill import register_skill_command, skill_app

__all__ = [
    "skill_app",
    "register_skill_command",
    "register_mcp_command",
    "route_app",
    "register_route_command",
    "register_run_command",
    "ingest_app",
    "register_ingest_command",
]
