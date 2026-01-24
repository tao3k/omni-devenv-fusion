"""
agent/mcp_server/stdio.py
 STDIO Transport for Claude Desktop

Minimal, reliable stdio transport with proper Ctrl-C handling.
MCP stdio mode runs directly without multiprocessing - the process
itself communicates via stdin/stdout with the MCP client.

Powered by omni.mcp.transport.stdio (Orjson + Pydantic V2).
"""

from __future__ import annotations

import asyncio
import os
import signal as _signal
import sys

import structlog

from omni.mcp.transport.stdio import stdio_server

from .lifespan import server_lifespan
from .server import get_init_options, get_server

log = structlog.get_logger(__name__)

_shutdown_count = 0


def _setup_signal_handler() -> None:
    """Set up signal handler for graceful shutdown."""
    global _shutdown_count

    def signal_handler(*_args):
        global _shutdown_count
        _shutdown_count += 1

        if _shutdown_count == 1:
            log.info("📡 Shutting down...")
            sys.exit(0)
        else:
            os._exit(1)

    _signal.signal(_signal.SIGINT, signal_handler)
    _signal.signal(_signal.SIGTERM, signal_handler)


async def run_stdio() -> None:
    """Run server in stdio mode for Claude Desktop.

    This runs directly without multiprocessing - the process itself
    communicates via stdin/stdout with the MCP client.

    Performance:
    - Zero-copy reading from stdin.buffer
    - orjson.loads() directly on bytes
    - orjson.dumps() with OPT_APPEND_NEWLINE
    - Binary output to stdout.buffer
    """
    log.info("📡 Starting Omni MCP Server (STDIO - High Performance)")

    # Set up signal handlers
    _setup_signal_handler()

    server = get_server()

    # Lifespan: Run once at startup (load skills)
    # Enable watcher for hot-reload support
    async with server_lifespan(enable_watcher=True):
        # Server run loop: wait for client connection, reconnect on EOF
        while True:
            try:
                # omni.mcp.transport.stdio.stdio_server uses orjson internally
                async with stdio_server() as (read_stream, write_stream):
                    await server.run(
                        read_stream,
                        write_stream,
                        get_init_options(),
                    )
            except asyncio.CancelledError:
                raise
            except BrokenPipeError:
                log.warning("Client disconnected, waiting for new connection...")
                await asyncio.sleep(0.5)
            except ValueError as e:
                if "I/O operation on closed file" in str(e):
                    log.debug("Stdin closed, waiting for client connection...")
                    await asyncio.sleep(0.5)
                else:
                    raise
            except Exception as e:
                log.warning(f"Server run error: {e}, reconnecting...")
                await asyncio.sleep(0.5)


def request_shutdown() -> None:
    """Request the server to shut down."""
    os._exit(0)


def is_shutdown_requested() -> bool:
    """Check if shutdown was requested."""
    return _shutdown_count > 0
