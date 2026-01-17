"""
agent/mcp_server/sse.py
 SSE Transport for Claude Code CLI

High-performance SSE server using uvloop and orjson.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
import uvicorn

from .lifespan import server_lifespan
from .server import get_server, get_init_options

log = structlog.get_logger(__name__)


def create_sse_app() -> Starlette:
    """Create SSE Starlette application."""
    server = get_server()

    async def handle_sse(request: Request):
        """Handle SSE connection."""
        sse = SseServerTransport("/sse")
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0],
                streams[1],
                get_init_options(),
            )

    async def handle_messages(request: Request):
        """Handle POST messages for SSE."""
        sse = SseServerTransport("/sse")
        await sse.handle_post_message(request.scope, request.receive, request._send)

    async def handle_health(request: Request):
        """Health check endpoint."""
        return Response(content="OK", media_type="text/plain")

    async def handle_ready(request: Request):
        """Readiness check."""
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        skills_count = len(manager.list_loaded())
        return Response(
            content=f"Omni Agent Ready - {skills_count} skills loaded",
            media_type="text/plain",
        )

    routes = [
        Route("/sse", handle_sse),
        Route("/messages", handle_messages),
        Route("/health", handle_health),
        Route("/ready", handle_ready),
    ]

    return Starlette(routes=routes, lifespan=lambda _: server_lifespan())


async def run_sse(
    host: str = "127.0.0.1",
    port: int = 8765,
    keepalive_interval: int = 15,
) -> None:
    """Run server in SSE mode for Claude Code CLI."""
    import asyncio

    # Performance: uvloop for high performance
    try:
        import uvloop

        uvloop.install()
        log.info("⚡️ uvloop enabled for SSE")
    except ImportError:
        log.info("ℹ️ uvloop not available, using default asyncio")

    app = create_sse_app()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Disable default access log to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    await server.serve()
