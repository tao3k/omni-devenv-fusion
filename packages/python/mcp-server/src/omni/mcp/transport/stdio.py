"""
Stdio Transport (High-Performance, orjson-powered)

Trinity Architecture - MCP Transport Layer

Pure stdin/stdout transport for JSON-RPC messages.
No business logic - only message transport.

Performance Optimizations:
1. Zero-copy Reading: Direct bytes from stdin.buffer (no UTF-8 decode overhead)
2. Fast Serialization: orjson for Rust-powered JSON processing
3. Binary Writing: Direct to stdout.buffer (bypass TextIOWrapper)

Logging: Uses Foundation layer (omni.foundation.config.logging)
"""

import sys
import asyncio
import orjson
from typing import Optional, AsyncGenerator, Tuple
from contextlib import asynccontextmanager

from omni.foundation.config.logging import get_logger

from ..types import (
    JSONRPCResponse,
    make_error_response,
    ErrorCode,
)
from ..interfaces import MCPRequestHandler, MCPTransport

logger = get_logger("omni.mcp.stdio")


class StdioTransport(MCPTransport):
    """
    High-Performance Stdio Transport (Powered by orjson)

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
        self._handler: Optional[MCPRequestHandler] = None
        self._reader: Optional[asyncio.StreamReader] = None
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
        logger.info("Starting stdio transport (orjson high-performance mode)...")
        self._running = True
        self._reader = asyncio.StreamReader()
        loop = asyncio.get_event_loop()
        self._transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(self._reader),
            sys.stdin,
        )
        logger.info("Stdio transport started")

    async def stop(self) -> None:
        """Stop the stdio transport."""
        logger.info("Stopping stdio transport...")
        self._running = False
        if self._reader:
            self._reader.feed_eof()
        logger.info("Stdio transport stopped")

    async def run_loop(self, server) -> None:
        """
        Run the message processing loop.

        Args:
            server: MCPServer instance to route messages through
        """
        logger.info("Stdio message loop started (orjson mode)")

        while self._running and self._reader:
            try:
                # Read raw bytes (no UTF-8 decode!)
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    break

                await self._process_message(line_bytes, server)

            except orjson.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                error_resp = make_error_response(
                    id=None,
                    code=ErrorCode.PARSE_ERROR,
                    message=f"Invalid JSON: {e}",
                )
                self._write_response(error_resp)

            except Exception as e:
                logger.error(f"Transport error: {e}")
                break

        logger.info("Stdio message loop ended")

    async def _process_message(self, line_bytes: bytes, server) -> None:
        """Process a single message (bytes -> orjson -> route)."""
        try:
            # orjson.loads directly accepts bytes (no decode overhead!)
            data = orjson.loads(line_bytes)
            response, is_notification = await server._route_message(data)

            if not is_notification and response:
                self._write_response(response)

        except orjson.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            error_resp = make_error_response(
                id=None,
                code=ErrorCode.PARSE_ERROR,
                message=f"Invalid JSON: {e}",
            )
            self._write_response(error_resp)
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    def _write_response(self, response: JSONRPCResponse) -> None:
        """Write binary response to stdout.buffer."""
        try:
            payload: dict = {"jsonrpc": response.jsonrpc, "id": response.id}
            if response.error:
                payload["error"] = response.error
            else:
                payload["result"] = response.result

            # orjson.dumps returns bytes
            # OPT_APPEND_NEWLINE: Let Rust add the newline (faster than Python concat)
            json_bytes = orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE)

            # Write directly to stdout.buffer (bypass TextIOWrapper)
            sys.stdout.buffer.write(json_bytes)
            sys.stdout.buffer.flush()

        except Exception as e:
            logger.error(f"Write error: {e}")


# =============================================================================
# MCP SDK Compatibility Layer
# =============================================================================


class _StdioStreams:
    """Stdio streams compatible with MCP SDK server.run()."""

    def __init__(self):
        self._reader = asyncio.StreamReader()
        self._running = False
        self._transport = None

    async def __aenter__(self):
        """Enter context manager."""
        loop = asyncio.get_event_loop()
        self._running = True
        self._reader = asyncio.StreamReader()
        self._transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(self._reader),
            sys.stdin,
        )
        return self, _WriteStream()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self._running = False
        if self._reader:
            self._reader.feed_eof()

    def read(self) -> asyncio.StreamReader:
        """Get the read stream."""
        return self._reader


class _WriteStream:
    """Write stream that writes directly to stdout.buffer."""

    def __init__(self):
        self._buffer = sys.stdout.buffer

    def write(self, data: bytes) -> None:
        """Write data to stdout.buffer."""
        self._buffer.write(data)
        self._buffer.flush()


@asynccontextmanager
async def stdio_server() -> AsyncGenerator[Tuple[_StdioStreams, _WriteStream], None]:
    """
    Async context manager for stdio transport.

    Compatible with mcp.server.stdio.stdio_server API.

    Yields:
        Tuple of (read_stream, write_stream) for use with server.run()

    Usage:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_options)
    """
    streams = _StdioStreams()
    async with streams:
        yield streams, _WriteStream()
