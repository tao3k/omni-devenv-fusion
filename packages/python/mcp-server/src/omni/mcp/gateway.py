"""
gateway.py - MCP Gateway with Live Tool Refresh

Trinity Architecture - MCP Transport Layer

Implements the bridge between:
1. SkillManager (skill registry changes)
2. MCPServer (MCP protocol)
3. Transport (stdio/SSE)

Key Feature: Tool list change notifications via notifications/tools/listChanged

Architecture:
    SkillManager --on_update--> SkillChangeNotifier --send_tool_list_changed--> MCPServer --broadcast--> Client
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from omni.foundation.config.logging import get_logger

from .interfaces import MCPRequestHandler, MCPTransport
from .server import MCPServer

logger = get_logger("omni.mcp.gateway")


class SkillChangeNotifier:
    """
    Bridges SkillManager updates to MCP Server notifications.

    When skills are added/removed/modified, this notifier:
    1. Receives update callback from SkillManager
    2. Triggers MCPServer.send_tool_list_changed()
    3. Clients (Claude/Cursor) automatically refresh their tool cache

    Debouncing: Multiple rapid changes within debounce_seconds are coalesced
    into a single notification to avoid flooding clients.
    """

    def __init__(self, mcp_server: MCPServer, debounce_seconds: float = 1.0):
        """
        Initialize the skill change notifier.

        Args:
            mcp_server: The MCP Server to notify when skills change
            debounce_seconds: Debounce time to avoid notification storms
        """
        self.server = mcp_server
        self.debounce_seconds = debounce_seconds
        self._last_notification: float = 0
        self._debounce_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def on_skills_changed(self) -> None:
        """
        Callback registered with SkillManager.

        Called when skill registry changes (add/remove/modify).
        Debounces notifications to avoid flooding clients.
        """
        async with self._lock:
            now = time.monotonic()
            time_since_last = now - self._last_notification

            # If within debounce window, cancel pending debounce and restart it
            if time_since_last < self.debounce_seconds:
                if self._debounce_task is not None and not self._debounce_task.done():
                    self._debounce_task.cancel()
                logger.debug("Skill change debounced, restarting debounce timer")
            else:
                # Outside debounce window, send immediately
                self._last_notification = now
                await self._send_tool_list_changed()
                return

            # Schedule debounced notification
            self._debounce_task = asyncio.create_task(self._debounced_send())

    async def _debounced_send(self) -> None:
        """Send notification after debounce period."""
        await asyncio.sleep(self.debounce_seconds)
        async with self._lock:
            self._debounce_task = None
        await self._send_tool_list_changed()

    async def _send_tool_list_changed(self) -> None:
        """Actually send the tool list changed notification."""
        try:
            await self.server.send_tool_list_changed()
            logger.info("🔔 Skill change notification sent to MCP clients")
        except Exception as e:
            logger.error(f"Failed to send tool list changed notification: {e}")


class OmniMCPGateway:
    """
    High-level MCP Gateway.

    Orchestrates:
    - MCP Server
    - Transport (stdio/SSE)
    - Skill change notifications

    Usage:
        gateway = OmniMCPGateway(
            skill_manager=skill_manager,  # Optional for notifications
            transport=transport,
        )
        await gateway.start()
    """

    def __init__(
        self,
        transport: MCPTransport,
        skill_manager: Any | None = None,
        handler: MCPRequestHandler | None = None,
    ):
        """
        Initialize the MCP Gateway.

        Args:
            transport: Transport layer (stdio/SSE)
            skill_manager: Optional SkillManager for live tool refresh
            handler: Optional custom request handler (auto-created if None)
        """
        self.transport = transport
        self.skill_manager = skill_manager

        # Create or use provided handler
        self.handler = handler or self._create_default_handler()

        # Create server
        self.server = MCPServer(handler=self.handler, transport=transport)

        # Create notifier if skill_manager provided
        self.notifier: SkillChangeNotifier | None = None
        if skill_manager is not None:
            self.notifier = SkillChangeNotifier(self.server)

    def _create_default_handler(self) -> MCPRequestHandler:
        """Create a default request handler that returns tool discovery info."""

        class DefaultHandler:
            """Default handler for simple tool discovery."""

            async def handle_request(self, request: Any) -> dict:
                return {"status": "ready", "tools": ["skill.discover"]}

            async def handle_notification(self, method: str, params: Any | None) -> None:
                pass

            async def initialize(self) -> None:
                pass

        return DefaultHandler()

    async def start(self) -> None:
        """Start the gateway and register skill change callback if configured."""
        # Register skill change callback if notifier exists
        if self.notifier is not None and self.skill_manager is not None:
            try:
                # Try to register callback with skill manager
                register = getattr(self.skill_manager, "on_registry_update", None)
                if register is not None and callable(register):
                    register(self.notifier.on_skills_changed)
                    logger.info("🔔 Registered skill change notifier with SkillManager")
                else:
                    logger.debug("SkillManager doesn't support on_registry_update callback")
            except Exception as e:
                logger.warning(f"Failed to register skill change callback: {e}")

        # Start the server
        await self.server.start()
        logger.info("Omni MCP Gateway started")

    async def stop(self) -> None:
        """Stop the gateway."""
        await self.server.stop()
        logger.info("Omni MCP Gateway stopped")

    @property
    def is_running(self) -> bool:
        return self.server.is_running


async def create_gateway(
    transport: MCPTransport,
    skill_manager: Any | None = None,
) -> OmniMCPGateway:
    """
    Factory function to create and configure an MCP Gateway.

    Args:
        transport: Transport layer (StdioTransport or SSETransport)
        skill_manager: Optional SkillManager for live tool refresh

    Returns:
        Configured and started gateway
    """
    gateway = OmniMCPGateway(transport=transport, skill_manager=skill_manager)
    await gateway.start()
    return gateway


__all__ = [
    "OmniMCPGateway",
    "SkillChangeNotifier",
    "create_gateway",
]
