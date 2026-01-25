"""
agent/mcp_server/lifespan.py
 Application Lifecycle Management

Handles startup/shutdown using the Kernel.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog

from .server import server

# Get structlog logger
log = structlog.get_logger(__name__)


@asynccontextmanager
async def server_lifespan(enable_watcher: bool = True):
    """Manage application lifecycle - startup and shutdown.

    Args:
        enable_watcher: Whether to start the skill watcher. Set to False for
            stdio transport (watchdog + multiprocessing daemon issues).
    """
    log.info("🚀 [Lifecycle] Starting Omni Agent Runtime via Kernel...")

    # Initialize Kernel (loads all skills)
    from omni.core.kernel import get_kernel

    kernel = get_kernel()

    try:
        await kernel.initialize()
        log.info(f"✅ [Lifecycle] Kernel ready with {kernel.skill_context.skills_count} skills")
    except Exception as e:
        log.warning(f"⚠️  [Lifecycle] Kernel initialization failed: {e}")
        raise

    log.info("✅ [Lifecycle] Server ready")

    try:
        yield
    finally:
        # Shutdown
        log.info("🛑 [Lifecycle] Shutting down...")


async def _notify_tools_changed(skill_changes: dict[str, str]):
    """Observer callback for skill changes - sends tool list updates to MCP clients.

    Receives a batch of skill changes and sends one tool list update.
    """
    try:
        request_ctx = server.request_context
        if request_ctx and request_ctx.session:
            await request_ctx.session.send_tool_list_changed()
            log.info("🔔 [Tools] Sent tool list update", skills=list(skill_changes.keys()))
    except Exception as e:
        log.debug(f"⚠️ [Hot Reload] Notification skipped (no session): {e}")


async def _update_search_index(skill_changes: dict[str, str]):
    """Index Sync observer for search index.

    Note: This feature requires the skill discovery service from omni.core.
    """
    log.debug("⏭ [Index Sync] Feature pending migration to omni.core")
