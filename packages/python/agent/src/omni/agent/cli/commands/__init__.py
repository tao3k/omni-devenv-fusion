"""commands - CLI Command Definitions"""

from __future__ import annotations

from .ingest import ingest_app, register_ingest_command
from .mcp import register_mcp_command
from .route import register_route_command, route_app
from .run import register_run_command
from .skill import register_skill_command, skill_app

__all__ = [
    "ingest_app",
    "register_ingest_command",
    "register_mcp_command",
    "register_route_command",
    "register_run_command",
    "register_skill_command",
    "route_app",
    "skill_app",
]
