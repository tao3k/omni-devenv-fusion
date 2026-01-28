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

from omni.agent.server import create_agent_handler
from omni.foundation.config.logging import configure_logging, get_logger
from omni.mcp.server import MCPServer
from omni.mcp.transport.stdio import StdioTransport

from .lifespan import server_lifespan

log = get_logger("omni.agent.stdio")


def get_init_options() -> dict:
    """Get MCP server initialization options."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
        },
        "serverInfo": {
            "name": "omni-agent",
            "version": "2.0.0",
        },
    }


def get_server(verbose: bool = False) -> MCPServer:
    """Create and return the MCP server instance with handlers registered.

    Args:
        verbose: If True, enable DEBUG logging; otherwise INFO level.
    """
    log_level = "DEBUG" if verbose else "INFO"
    configure_logging(level=log_level)
    handler = create_agent_handler()
    transport = StdioTransport()
    server = MCPServer(handler, transport)

    # MCP init options
    init_options = {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True},
        },
        "serverInfo": {
            "name": "omni-agent",
            "version": "2.0.0",
        },
    }

    # Register MCP protocol handlers
    @server.request("initialize")
    async def handle_initialize(**params) -> dict:
        """Handle MCP initialize request."""
        log.info("[MCP] Responding to initialize request")
        return init_options

    @server.request("tools/list")
    async def handle_list_tools(**params) -> dict:
        """Handle MCP tools/list request."""
        result = await handler.handle_request(
            {"method": "tools/list", "params": params, "id": None}
        )
        log.info(
            f"[MCP] tools/list returned {len(result.get('result', {}).get('tools', []))} tools"
        )
        return result.get("result", {})

    @server.request("tools/call")
    async def handle_call_tool(name: str = "", arguments: dict | None = None, **params) -> dict:
        """Handle MCP tools/call request."""
        request = {
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
            "id": None,
        }
        result = await handler.handle_request(request)
        return result.get("result", {})

    return server


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


async def run_stdio(verbose: bool = False) -> None:
    """Run server in stdio mode for Claude Desktop.

    This runs directly without multiprocessing - the process itself
    communicates via stdin/stdout with the MCP client.

    Args:
        verbose: If True, enable DEBUG logging; otherwise INFO level.

    Performance:
    - Zero-copy reading from stdin.buffer
    - orjson.loads() directly on bytes
    - orjson.dumps() with OPT_APPEND_NEWLINE
    - Binary output to stdout.buffer
    """
    log_level = "DEBUG" if verbose else "INFO"
    log.info(f"📡 Starting Omni MCP Server (STDIO - {log_level} mode)")

    # Set up signal handlers
    _setup_signal_handler()

    server = get_server(verbose=verbose)

    # Lifespan: Run once at startup (load skills)
    # Enable watcher for hot-reload support
    async with server_lifespan(enable_watcher=True):
        try:
            await server.start()
            await server.run_forever()
        except asyncio.CancelledError:
            log.info("Server cancelled")
        except Exception as e:
            log.error(f"Server error: {e}")
            raise


def request_shutdown() -> None:
    """Request the server to shut down."""
    os._exit(0)


def is_shutdown_requested() -> bool:
    """Check if shutdown was requested."""
    return _shutdown_count > 0
