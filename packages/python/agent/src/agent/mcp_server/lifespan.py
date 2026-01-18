"""
agent/mcp_server/lifespan.py
 Application Lifecycle Management

Handles startup/shutdown, skill loading, and hot-reload observers.
"""

from __future__ import annotations

import asyncio
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
    from agent.core.skill_runtime import get_skill_context

    manager = get_skill_context()

    # Observer 1: MCP tool list update
    manager.subscribe(_notify_tools_changed)
    log.info("👀 [Lifecycle] Hot-reload observer registered (MCP Tools)")

    # Observer 2: Index Sync
    manager.subscribe(_update_search_index)
    log.info("🔍 [Lifecycle] Index Sync observer registered")

    # Start Skill Watcher for auto-sync
    from agent.core.skill_runtime.watcher import start_global_watcher

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
        from agent.core.skill_runtime.watcher import stop_global_watcher

        stop_global_watcher()
        log.info("🛑 [Lifecycle] Shutting down...")


async def _notify_tools_changed(skill_changes: dict[str, str]):
    """Observer callback for skill changes - sends tool list updates to MCP clients.

    Receives a batch of skill changes and sends one tool list update.
    """
    global _last_notification

    # Deduplicate: only send update if we haven't just sent one
    if _last_notification is not None:
        return

    try:
        request_ctx = server.request_context
        if request_ctx and request_ctx.session:
            await request_ctx.session.send_tool_list_changed()
            _last_notification = ("batch", "update") if skill_changes else None
            log.info(f"🔔 [Tools] Sent tool list update", skills=list(skill_changes.keys()))
    except Exception as e:
        log.debug(f"⚠️ [Hot Reload] Notification skipped (no session): {e}")


async def _update_search_index(skill_changes: dict[str, str]):
    """Index Sync observer for Rust-backed VectorMemory.

    Receives a batch of skill changes and syncs once for all changes.
    """
    global _index_sync_lock, _last_sync_stats

    # Skip if sync already in progress
    if _index_sync_lock:
        log.debug("⏭ [Index Sync] Skipped (sync in progress)")
        return

    _index_sync_lock = True
    try:
        from agent.core.skill_discovery import reindex_skills_from_manifests

        log.info(
            f"🔄 [Index Sync] Syncing after {len(skill_changes)} changes",
            skills=list(skill_changes.keys()),
        )

        result = await reindex_skills_from_manifests()
        stats = result.get("stats", {})

        # Deduplicate identical sync results
        if stats == _last_sync_stats:
            log.debug("🔕 [Index Sync] Skipped (no changes from last sync)")
            return
        _last_sync_stats = stats.copy() if stats else None

        # Only log if there were actual changes
        added = stats.get("added", 0)
        modified = stats.get("modified", 0)
        deleted = stats.get("deleted", 0)

        if added > 0 or modified > 0 or deleted > 0:
            log.info(
                f"✅ [Index Sync] Sync completed: +{added} ~{modified} -{deleted} (total={stats.get('total', 0)})"
            )
        else:
            log.debug(f"🔕 [Index Sync] No changes detected (total={stats.get('total', 0)})")

    except Exception as e:
        log.warning(f"⚠️ [Index Sync] Error: {e}")
    finally:
        _index_sync_lock = False
