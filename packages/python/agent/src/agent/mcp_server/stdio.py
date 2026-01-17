"""
agent/mcp_server/stdio.py
 STDIO Transport for Claude Desktop

Minimal, reliable stdio transport.
"""

from __future__ import annotations

import structlog
from mcp.server.stdio import stdio_server

from .lifespan import server_lifespan
from .server import get_server, get_init_options

log = structlog.get_logger(__name__)


async def run_stdio() -> None:
    """Run server in stdio mode for Claude Desktop."""
    server = get_server()

    async with server_lifespan():
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    get_init_options(),
                )
            except Exception as e:
                log.critical(f"💥 Stdio server crashed: {e}", exc_info=True)
                raise
