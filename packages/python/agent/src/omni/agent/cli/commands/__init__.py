"""commands - CLI Command Definitions"""

from __future__ import annotations

from omni.foundation.config import get_database_path, get_database_paths

from .completions import register_completions_command
from .dashboard import register_dashboard_command
from .db import db_app, register_db_command
from .gateway_agent import (
    register_agent_command,
    register_channel_command,
    register_gateway_command,
)
from .knowledge import register_knowledge_command
from .mcp import register_mcp_command
from .reindex import register_reindex_command, reindex_app
from .route import register_route_command, route_app
from .skill import register_skill_command, skill_app
from .sync import register_sync_command, sync_app

try:
    from .run import register_run_command
except ModuleNotFoundError as exc:
    if exc.name != "omni.agent.cli.commands.run":
        raise

    def register_run_command(_parent_app) -> None:
        """Keep MCP/other commands usable even if run command module is temporarily missing."""
        from omni.foundation.config.logging import get_logger

        get_logger("omni.agent.cli.commands").warning(
            "Skipping run command registration because module 'omni.agent.cli.commands.run' "
            "is unavailable in current working tree."
        )


__all__ = [
    "db_app",
    "get_database_path",
    "get_database_paths",
    "register_agent_command",
    "register_channel_command",
    "register_completions_command",
    "register_dashboard_command",
    "register_db_command",
    "register_gateway_command",
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
