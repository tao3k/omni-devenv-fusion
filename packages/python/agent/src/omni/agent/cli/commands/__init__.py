"""commands - CLI Command Definitions"""

from __future__ import annotations

from .knowledge import register_knowledge_command
from .mcp import register_mcp_command
from .reindex import get_database_path, get_database_paths, register_reindex_command, reindex_app
from .route import register_route_command, route_app
from .run import register_run_command
from .skill import register_skill_command, skill_app
from .sync import register_sync_command, sync_app

__all__ = [
    "get_database_path",
    "get_database_paths",
    "register_knowledge_command",
    "register_mcp_command",
    "register_reindex_command",
    "register_route_command",
    "register_run_command",
    "register_skill_command",
    "register_sync_command",
    "reindex_app",
    "route_app",
    "skill_app",
    "sync_app",
]
