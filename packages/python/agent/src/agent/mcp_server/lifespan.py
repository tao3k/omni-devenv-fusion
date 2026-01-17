"""
agent/mcp_server/lifespan.py
 Application Lifecycle Management

Handles startup/shutdown, skill loading, and hot-reload observers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import structlog
from .server import server

# Get structlog logger
log = structlog.get_logger(__name__)

# Hot reload state
_index_sync_lock: bool = False
_last_sync_stats: dict | None = None
_last_notification: tuple[str, str] | None = None


@asynccontextmanager
async def server_lifespan():
    """Manage application lifecycle - startup and shutdown."""
    log.info("🚀 [Lifecycle] Starting Omni Agent Runtime...")

    # Load all skills synchronously (safe for stdio mode startup)
    from agent.core.bootstrap import boot_core_skills

    try:
        boot_core_skills(server)
        log.info("✅ [Lifecycle] Skills preloaded")
    except Exception as e:
        log.warning(f"⚠️  [Lifecycle] Skill preload failed: {e}")

    # Register Hot-Reload Observers
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    # Observer 1: MCP tool list update
    manager.subscribe(_notify_tools_changed)
    log.info("👀 [Lifecycle] Hot-reload observer registered (MCP Tools)")

    # Observer 2: Index Sync
    manager.subscribe(_update_search_index)
    log.info("🔍 [Lifecycle] Index Sync observer registered")

    # Start Skill Watcher for auto-sync
    from agent.core.skill_manager.watcher import start_global_watcher

    try:
        start_global_watcher()
        log.info("👀 [Lifecycle] Skill Watcher started (auto-sync)")
    except Exception as e:
        log.warning(f"⚠️  [Lifecycle] Skill Watcher failed to start: {e}")

    log.info("✅ [Lifecycle] Server ready")

    try:
        yield
    finally:
        # Stop Skill Watcher
        from agent.core.skill_manager.watcher import stop_global_watcher

        stop_global_watcher()
        log.info("🛑 [Lifecycle] Shutting down...")


async def _notify_tools_changed(skill_name: str, change_type: str):
    """Observer callback for skill changes - sends tool list updates to MCP clients."""
    global _last_notification

    # Deduplicate notifications
    current = (skill_name, change_type)
    if current == _last_notification:
        return
    _last_notification = current

    try:
        request_ctx = server.request_context
        if request_ctx and request_ctx.session:
            await request_ctx.session.send_tool_list_changed()
            log.info(f"🔔 [{change_type.title()}] Sent tool list update: {skill_name}")
    except Exception as e:
        log.debug(f"⚠️ [Hot Reload] Notification skipped (no session): {e}")


async def _update_search_index(skill_name: str, change_type: str):
    """Index Sync observer for Rust-backed VectorMemory."""
    global _index_sync_lock, _last_sync_stats

    if _index_sync_lock:
        return

    _index_sync_lock = True
    try:
        from agent.core.skill_discovery import reindex_skills_from_manifests

        result = await reindex_skills_from_manifests()
        stats = result.get("stats", {})

        # Deduplicate identical sync results
        if stats == _last_sync_stats:
            return
        _last_sync_stats = stats.copy() if stats else None

        # Only log if there were actual changes
        added = stats.get("added", 0)
        modified = stats.get("modified", 0)
        deleted = stats.get("deleted", 0)

        if added > 0 or modified > 0 or deleted > 0:
            log.info(f"🔄 [Index Sync] Sync completed: {stats}")
        else:
            log.debug(f"🔕 [Index Sync] No changes detected (total={stats.get('total', 0)})")

    except Exception as e:
        log.warning(f"⚠️ [Index Sync] Error: {e}")
    finally:
        _index_sync_lock = False
