"""
server.py - MCP Server Core

Trinity Architecture - MCP Transport Layer

Orchestrates transport and handler. Pure orchestration, no business logic.

Uses MCP SDK types for JSON-RPC compliance (type hints only, no runtime overhead).
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.types import JSONRPCMessage, JSONRPCResponse

from omni.foundation.config.logging import get_logger

from .interfaces import MCPRequestHandler, MCPTransport

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
        self._handlers: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def request(self, method: str):
        """Decorator to register a request handler."""

        def decorator(func: Any) -> Any:
            self._handlers[method] = func
            return func

        return decorator

    async def start(self) -> None:
        """Start the MCP server."""
        self._running = True

        # Set handler on transport if it supports it
        set_handler = getattr(self.transport, "set_handler", None)
        if set_handler is not None:
            set_handler(self.handler)

        await self.transport.start()

    async def stop(self) -> None:
        """Stop the MCP server."""
        self._running = False
        await self.transport.stop()

    async def process_message(self, message: JSONRPCMessage) -> JSONRPCResponse | None:
        """
        Process a single JSON-RPC message.
        """
        if not isinstance(message, dict):
            return self._error_response(None, -32600, "Invalid JSON-RPC message: must be an object")

        method = message.get("method", "")
        msg_id = message.get("id")

        # Handle notifications (no id)
        if msg_id is None:
            if method.startswith("notifications/"):
                asyncio.create_task(self.handler.handle_notification(method, message.get("params")))
                return None
            else:
                # Request without id is invalid
                return self._error_response(
                    None, -32600, "Invalid JSON-RPC message: request must have id"
                )

        # Handle known methods
        if method in self._handlers:
            return await self._handle_request(method, message.get("params"), msg_id)

        # Method not found
        return self._error_response(msg_id, -32601, f"Method not found: {method}")

    async def _handle_request(self, method: str, params: Any, msg_id: str | int) -> JSONRPCResponse:
        """Handle a request with proper parameter unpacking."""
        try:
            handler = self._handlers[method]

            # Unpack params based on type
            if isinstance(params, dict):
                result = await handler(**params)
            elif isinstance(params, list):
                result = await handler(*params)
            else:
                result = await handler()

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            }
        except Exception as e:
            logger.exception(f"Error handling {method}")
            return self._error_response(msg_id, -32603, str(e))

    def _error_response(self, msg_id: str | int | None, code: int, message: str) -> JSONRPCResponse:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def process_batch(self, messages: list[JSONRPCMessage]) -> list[JSONRPCResponse]:
        """
        Process multiple messages concurrently using TaskGroup.

        Args:
            messages: List of messages to process

        Returns:
            List of responses (only for requests, not notifications)
        """
        if not messages:
            return []

        responses: list[JSONRPCResponse] = []

        async def _process_and_collect(msg: JSONRPCMessage) -> JSONRPCResponse | None:
            result = await self.process_message(msg)
            if result is not None:
                responses.append(result)
            return result

        # Process all messages concurrently with TaskGroup
        try:
            async with asyncio.TaskGroup() as tg:
                for msg in messages:
                    tg.create_task(_process_and_collect(msg))
        except ExceptionGroup as e:
            logger.error(f"Batch processing failed with partial errors: {e.exceptions}")

        return responses

    async def run_forever(self) -> None:
        """Run the server main loop."""
        # Check if transport has its own run_loop (like StdioTransport)
        run_loop = getattr(self.transport, "run_loop", None)
        if run_loop is not None and callable(run_loop):
            try:
                await run_loop(self)
            except Exception:
                pass
            return

        # Fallback: use _tick() loop
        try:
            while self._running:
                await self._tick()
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()

    async def _tick(self) -> None:
        """Single tick of the server loop."""
        # Override in subclass for specific transport
        pass


__all__ = ["MCPServer"]
