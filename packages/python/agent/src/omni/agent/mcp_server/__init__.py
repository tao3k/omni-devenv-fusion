"""
agent/mcp_server/
 MCP Server Module

Submodules:
- server.py: Core server instance and handlers
- stdio.py: STDIO transport (Claude Desktop)
- sse.py: SSE transport (Claude Code CLI)
- lifespan.py: Application lifecycle management

Usage:
    from omni.agent.mcp_server import run

    await run(transport="stdio")  # Claude Desktop
    await run(transport="sse")    # Claude Code CLI
"""

from __future__ import annotations

import asyncio
import logging
import sys

import structlog

# Get logger - structlog is configured in cli/commands/mcp.py before this module is imported
log = structlog.get_logger(__name__)

# Import submodules
from .lifespan import server_lifespan
from .server import _notify_tools_changed, handle_list_tools
from .sse import run_sse
from .stdio import run_stdio

# Performance detection
try:
    import uvloop

    _HAS_UVLOOP = True
except ImportError:
    _HAS_UVLOOP = False
    uvloop = None

try:
    import orjson

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False
    orjson = None


async def run(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
    keepalive_interval: int = 15,
) -> None:
    """
    Start the MCP server with specified transport.

    Args:
        transport: "stdio" for Claude Desktop, "sse" for Claude Code CLI
        host: Host to bind (SSE only)
        port: Port to listen (SSE only)
        keepalive_interval: SSE keep-alive heartbeat in seconds
    """
    log.info(f"🚀 Starting Omni MCP Server ({transport.upper()})")
    log.info(
        f"📊 Performance: uvloop={'✅' if _HAS_UVLOOP else '❌'}, "
        f"orjson={'✅' if _HAS_ORJSON else '❌'}"
    )

    if transport == "stdio":
        log.info("📡 Mode: STDIO (Claude Desktop)")
        await run_stdio()

    elif transport == "sse":
        log.info(f"📡 Mode: SSE (http://{host}:{port})")
        await run_sse(host, port, keepalive_interval)

    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'sse'.")


__all__ = [
    "_notify_tools_changed",
    "handle_list_tools",
    "run",
    "run_sse",
    "run_stdio",
    "server_lifespan",
]
