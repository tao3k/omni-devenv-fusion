"""
agent/mcp_server/lifespan.py
 Application Lifecycle Management

Handles startup/shutdown using the Kernel.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from omni.foundation.config.logging import get_logger

if TYPE_CHECKING:
    from mcp.server import Server

    from .server import AgentMCPServer

log = get_logger("omni.agent.lifecycle")

# Global registry for MCP server reference (used by kernel for notifications)
# Stores AgentMCPServer which has send_tool_list_changed() method
_mcp_server: AgentMCPServer | Server | None = None


def set_mcp_server(server: AgentMCPServer | Server | None) -> None:
    """Set the MCP server instance for tool list notifications.

    Args:
        server: AgentMCPServer instance (or None to clear registry).
    """
    global _mcp_server
    _mcp_server = server
    if server is None:
        log.debug("MCP server registration cleared")
        return

    log.debug("MCP server registered for tool notifications")


def get_mcp_server() -> AgentMCPServer | Server | None:
    """Get the current MCP server instance."""
    return _mcp_server


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

        # [NOTE] MCP server should be registered BEFORE calling kernel.start()
        # The caller (stdio.py or sse.py) is responsible for calling set_mcp_server()
        # before entering this context manager.

        # Start kernel to trigger _on_ready which starts SkillManager's Live-Wire Watcher
        await kernel.start()
        log.info(f"Kernel ready with {kernel.skill_context.skills_count} skills")
        # Log Live-Wire status
        if kernel._skill_manager and kernel._skill_manager.watcher:
            log.info("⚡ Live-Wire Skill Watcher is active")

            # Register callback to notify MCP clients when skills change
            # This bridges SkillManager -> kernel -> MCP server notification
            async def on_skills_changed():
                """Callback triggered when skills are added/modified/removed."""
                try:
                    log.info("🔔 on_skills_changed callback triggered - sending MCP notification")
                    await _notify_tools_changed({})
                except Exception as e:
                    log.warning(f"❌ Failed to send skill change notification: {e}")

            kernel.skill_manager.on_registry_update(on_skills_changed)
            log.info("🔔 Registered skill change callback for Live-Wire")

        # Preload validation tool schemas so first MCP tool call is not slow (Rust scanner load)
        try:
            from omni.core.skills.validation import warm_tool_schema_cache

            await asyncio.wait_for(
                asyncio.to_thread(warm_tool_schema_cache),
                timeout=15.0,
            )
            log.debug("Warmed tool schema cache for fast first-call validation")
        except TimeoutError:
            log.warning("Tool schema warm-up timed out (15s); first tool call may be slower")
        except Exception as e:
            log.debug("Tool schema warm-up skipped: %s", e)

        # Note: Embedding warmup is handled by AgentMCPHandler.initialize()
        # This ensures embedding is loaded when first tool call is made

    except Exception as e:
        log.warning(f"Kernel initialization failed: {e}")
        raise

    log.info("Server ready")

    try:
        yield
    finally:
        # Shutdown
        log.info("Shutting down...")


async def _notify_tools_changed(skill_changes: dict[str, str]) -> None:
    """Observer callback for skill changes - sends tool list updates to MCP clients.

    Receives a batch of skill changes and sends one tool list update.
    This enables automatic tool refresh when skills are added/modified/removed.
    """
    global _mcp_server

    if _mcp_server is None:
        # Normal in non-MCP CLI processes (no connected server transport).
        log.debug(
            "Skipping Live-Wire tool notification (no MCP server registered)",
            skills=list(skill_changes.keys()),
        )
        return

    log.info("🔔 Skill changes detected (Live-Wire)", skills=list(skill_changes.keys()))

    try:
        # MCPServer has send_tool_list_changed() method
        send_tool_list_changed = getattr(_mcp_server, "send_tool_list_changed", None)
        if send_tool_list_changed is not None and callable(send_tool_list_changed):
            await send_tool_list_changed()
            log.info("Sent notifications/tools/listChanged to MCP clients")
        else:
            log.warning("MCP server does not have send_tool_list_changed method")
    except Exception as e:
        log.warning(f"Failed to send tool list changed notification: {e}")


async def _update_search_index(skill_changes: dict[str, str]):
    """Index Sync observer for search index.

    Note: This feature requires the skill discovery service from omni.core.
    """
    log.debug("Index Sync feature pending migration to omni.core")
