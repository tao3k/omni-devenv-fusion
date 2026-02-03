"""
Stdio Transport (High-Performance, orjson-powered)

Trinity Architecture - MCP Transport Layer

Pure stdin/stdout transport for JSON-RPC messages.
No business logic - only message transport.

Uses MCP SDK for JSON-RPC protocol handling.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import orjson

from mcp.server.stdio import stdio_server as mcp_stdio_server
from mcp.types import JSONRPCMessage

from ..interfaces import MCPRequestHandler, MCPTransport
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.mcp.transport.stdio")


class StdioTransport(MCPTransport):
    """
    High-Performance Stdio Transport.

    Key optimizations:
    - Reads raw bytes from stdin.buffer (zero UTF-8 decode)
    - Uses orjson for 10-50x faster serialization
    - Writes raw bytes to stdout.buffer (no encoding overhead)

    Usage:
        transport = StdioTransport()
        server = MCPServer(handler, transport)
        await server.start()
    """

    def __init__(self):
        self._handler: MCPRequestHandler | None = None
        self._reader: asyncio.StreamReader | None = None
        self._running = False
        self._transport = None

    def set_handler(self, handler: MCPRequestHandler) -> None:
        """Set the request handler (called by MCPServer.start())."""
        self._handler = handler

    @property
    def is_connected(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the stdio transport."""
        self._running = True
        self._reader = asyncio.StreamReader()
        loop = asyncio.get_event_loop()
        self._transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(self._reader),
            sys.stdin,
        )

    async def stop(self) -> None:
        """Stop the stdio transport."""
        self._running = False
        if self._reader:
            self._reader.feed_eof()

    async def run_loop(self, server) -> None:
        """
        Run the message processing loop.

        Args:
            server: MCPServer instance to route messages through
        """
        while self._running and self._reader:
            try:
                # Read raw bytes (no UTF-8 decode!)
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    break

                await self._process_message(line_bytes, server)
            except Exception:
                pass

    async def _process_message(self, line_bytes: bytes, server) -> None:
        """Process a single message (bytes -> orjson -> route)."""
        try:
            # orjson.loads directly accepts bytes (no decode overhead!)
            data = orjson.loads(line_bytes)

            # Validate it's a proper JSON-RPC message
            if not isinstance(data, dict):
                await self._send_invalid_request("Message must be a JSON object")
                return

            response = await server.process_message(cast(JSONRPCMessage, data))

            if response:
                self._write_response(response)

        except orjson.JSONDecodeError:
            await self._send_parse_error("Invalid JSON")
        except Exception:
            pass

    async def _send_parse_error(self, error_message: str) -> None:
        """Send a JSON-RPC parse error response."""
        error_resp = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {error_message}",
            },
        }
        self._write_response(error_resp)

    async def _send_invalid_request(self, message: str) -> None:
        """Send a JSON-RPC invalid request error response."""
        error_resp = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32600,
                "message": message,
            },
        }
        self._write_response(error_resp)

    def _write_response(self, response: Any) -> None:
        """Write binary response to stdout.buffer."""
        try:
            # Handle both dict and Pydantic model responses
            if hasattr(response, "model_dump"):
                response_dict: dict[str, Any] = response.model_dump()
            else:
                response_dict = cast(dict[str, Any], response)

            # JSON-RPC 2.0: Response MUST have a non-null id
            msg_id = response_dict.get("id")
            if msg_id is None:
                # Notifications don't have id - use _write_notification instead
                return

            # Build JSON-RPC 2.0 compliant response
            payload: dict[str, Any] = {
                "jsonrpc": response_dict.get("jsonrpc", "2.0"),
                "id": msg_id,
            }

            # JSON-RPC 2.0: response MUST contain either "result" OR "error", never both
            if response_dict.get("error") is not None:
                payload["error"] = response_dict.get("error")
            elif "result" in response_dict:
                payload["result"] = response_dict.get("result")

            # orjson.dumps returns bytes
            json_bytes = orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE)

            # Write directly to stdout.buffer (bypass TextIOWrapper)
            sys.stdout.buffer.write(json_bytes)
            sys.stdout.buffer.flush()

        except Exception:
            pass

    async def broadcast(self, notification: dict[str, Any]) -> None:
        """Broadcast a notification to all connected clients.

        For stdio transport, this writes directly to stdout.
        Notifications are JSON-RPC 2.0 messages without an 'id' field.
        """
        try:
            # JSON-RPC 2.0 notifications must NOT have an 'id' field
            payload = {
                "jsonrpc": "2.0",
                "method": notification.get("method"),
                "params": notification.get("params"),
            }

            json_bytes = orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE)
            sys.stdout.buffer.write(json_bytes)
            sys.stdout.buffer.flush()
            logger.debug(f"Broadcast notification: {payload.get('method')}")
        except Exception as e:
            logger.warning(f"Failed to broadcast notification: {e}")


# =============================================================================
# MCP SDK Compatibility Layer
# =============================================================================


@asynccontextmanager
async def stdio_server() -> AsyncGenerator[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    """
    Async context manager for stdio transport.

    Compatible with mcp.server.stdio.stdio_server API.

    Yields:
        Tuple of (read_stream, write_stream) for use with server.run()
    """
    reader = asyncio.StreamReader()

    async def write_stream():
        return sys.stdout.buffer

    loop = asyncio.get_event_loop()
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin,
    )

    try:
        yield reader, write_stream()
    finally:
        transport.close()
        reader.feed_eof()


__all__ = ["StdioTransport", "stdio_server"]
