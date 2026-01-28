"""
agent/mcp_server/lifespan.py
 Application Lifecycle Management

Handles startup/shutdown using the Kernel.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from omni.foundation.config.logging import get_logger

log = get_logger("omni.agent.lifecycle")


@asynccontextmanager
async def server_lifespan(enable_watcher: bool = True):
    """Manage application lifecycle - startup and shutdown.

    Args:
        enable_watcher: Whether to start the skill watcher. Set to False for
            stdio transport (prevents duplicate watchers in parent/child processes).
    """
    log.info("Starting Omni Agent Runtime via Kernel...")

    # Initialize Kernel (loads all skills)
    from omni.core.kernel import get_kernel

    kernel = get_kernel()

    try:
        await kernel.initialize()
        log.info(f"Kernel ready with {kernel.skill_context.skills_count} skills")
    except Exception as e:
        log.warning(f"Kernel initialization failed: {e}")
        raise

    log.info("Server ready")

    try:
        yield
    finally:
        # Shutdown
        log.info("Shutting down...")


async def _notify_tools_changed(skill_changes: dict[str, str]):
    """Observer callback for skill changes - sends tool list updates to MCP clients.

    Receives a batch of skill changes and sends one tool list update.
    """
    # Note: Tool list notification requires MCP SDK server context
    # This is a placeholder for hot reload tool list updates
    log.info("Skill changes detected (hot reload)", skills=list(skill_changes.keys()))
    # The actual tool list update is handled by the MCP handler's _handle_list_tools


async def _update_search_index(skill_changes: dict[str, str]):
    """Index Sync observer for search index.

    Note: This feature requires the skill discovery service from omni.core.
    """
    log.debug("Index Sync feature pending migration to omni.core")
