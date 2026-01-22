"""
Generic MCP Server

Trinity Architecture - MCP Transport Layer

Orchestrates transport and handler. Pure orchestration, no business logic.

Logging: Uses Foundation layer (omni.foundation.config.logging)
"""

import asyncio
from typing import Any, Optional

from omni.foundation.config.logging import get_logger

from .interfaces import MCPRequestHandler, MCPTransport
from .types import JSONRPCRequest, JSONRPCResponse, make_error_response, ErrorCode

logger = get_logger("omni.mcp.server")


class MCPServer:
    """
    High-performance MCP Server.

    Architecture:
        Transport <-> Server <-> Handler (Agent)

    The server only orchestrates message routing.
    It knows neither Skills nor Tools.
    """

    def __init__(
        self,
        handler: MCPRequestHandler,
        transport: MCPTransport,
    ):
        self.handler = handler
        self.transport = transport
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the MCP server."""
        logger.info("Starting MCP server...")
        self._running = True

        # Set handler on transport if it supports it
        set_handler = getattr(self.transport, "set_handler", None)
        if set_handler is not None:
            set_handler(self.handler)

        await self.transport.start()
        logger.info("MCP server started")

    async def stop(self) -> None:
        """Stop the MCP server."""
        logger.info("Stopping MCP server...")
        self._running = False
        await self.transport.stop()
        logger.info("MCP server stopped")

    async def _route_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Route request to handler and handle exceptions."""
        try:
            return await self.handler.handle_request(request)
        except Exception as e:
            logger.error(f"Request handling error: {e}")
            return make_error_response(
                id=request.id,
                code=ErrorCode.INTERNAL_ERROR,
                message=str(e),
            )

    async def _route_notification(self, method: str, params: Optional[Any]) -> None:
        """Route notification to handler."""
        try:
            await self.handler.handle_notification(method, params)
        except Exception as e:
            logger.error(f"Notification handling error: {e}")

    async def _route_message(self, data: dict) -> tuple[Optional[JSONRPCResponse], bool]:
        """
        Route incoming message to appropriate handler.

        Returns:
            Tuple of (response, is_notification)
        """
        request = JSONRPCRequest(**data)

        if request.is_notification:
            # Fire and forget for notifications
            asyncio.create_task(self._route_notification(request.method, request.params))
            return None, True
        else:
            # Wait for response for requests
            response = await self._route_request(request)
            return response, False

    async def run_forever(self) -> None:
        """Run the server main loop. Called by transport."""
        logger.info("MCP server running...")
        try:
            while self._running:
                await self._tick()
        except KeyboardInterrupt:
            logger.info("MCP server interrupted")
        finally:
            await self.stop()

    async def _tick(self) -> None:
        """Single tick of the server loop."""
        # Override in subclass for specific transport
        pass
