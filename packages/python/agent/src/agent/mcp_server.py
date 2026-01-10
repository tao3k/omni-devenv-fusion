"""
agent/mcp_server.py
Phase 35.3: High-Performance MCP Server (Official SDK)

Architecture:
- Pure mcp.server.Server (no FastMCP overhead)
- Stdio mode: Minimal, reliable, no background tasks
- SSE mode: uvloop + orjson for high performance
- Skill execution via Swarm Engine

Usage:
    omni mcp --transport stdio      # Claude Desktop
    omni mcp --transport sse        # Claude Code CLI
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

# Performance Libraries
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

# MCP Core
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

# Web Server (For SSE)
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import uvicorn

# Configure logging (stderr for UNIX philosophy, stdout reserved for data)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("omni.mcp")

# --- Performance Helpers ---


def json_dumps(obj: Any) -> str:
    """Fast JSON serialization using orjson if available."""
    if _HAS_ORJSON:
        return orjson.dumps(obj).decode("utf-8")
    return json.dumps(obj, ensure_ascii=False)


def json_loads(data: str | bytes) -> Any:
    """Fast JSON parsing using orjson if available."""
    if _HAS_ORJSON:
        return orjson.loads(data)
    return json.loads(data)


# --- Server Instance ---
server = Server("omni-agent")


# --- Lifecycle Management --


@asynccontextmanager
async def server_lifespan():
    """Global lifecycle manager for resources."""
    logger.info("🚀 [Lifecycle] Starting Omni Agent Runtime...")

    # Load all skills synchronously (safe for stdio mode startup)
    from agent.core.bootstrap import boot_core_skills

    try:
        boot_core_skills(server)
        logger.info("✅ [Lifecycle] Skills preloaded")
    except Exception as e:
        logger.warning(f"⚠️  [Lifecycle] Skill preload failed: {e}")
        # Continue - skills can be loaded on-demand

    logger.info("✅ [Lifecycle] Server ready")

    try:
        yield
    finally:
        logger.info("🛑 [Lifecycle] Shutting down...")


# --- Tool Call Handler ---


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available tools from loaded skills."""
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    tools = []

    # Get all loaded skills and their commands
    for skill_name in manager.list_loaded():
        skill_info = manager.get_info(skill_name)
        if not skill_info:
            continue

        # Get commands for this skill
        commands = manager.get_commands(skill_name)
        for cmd_name in commands:
            cmd = manager.get_command(skill_name, cmd_name)
            if cmd is None:
                continue

            # Convert to MCP Tool
            tool_name = f"{skill_name}.{cmd_name}"

            # Parse input schema from command config
            input_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            tools.append(
                Tool(
                    name=tool_name,
                    description=cmd.description or f"Execute {skill_name}.{cmd_name}",
                    inputSchema=input_schema,
                )
            )

    logger.info(f"📋 [Tools] Listed {len(tools)} tools")
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Execute a tool via SkillManager."""
    from agent.core.skill_manager import get_skill_manager

    args = arguments or {}
    logger.info(f"🔨 [Tool] Executing: {name}")

    try:
        # Parse skill.command format
        if "." in name:
            parts = name.split(".", 1)
            skill_name = parts[0]
            command_name = parts[1]
        else:
            return [
                TextContent(
                    type="text", text=f"❌ Invalid tool name: {name}. Use 'skill.command' format."
                )
            ]

        # Execute via SkillManager
        manager = get_skill_manager()
        result = await manager.run(skill_name, command_name, args)

        # Return result
        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.exception(f"❌ [Tool] Execution failed: {name}")
        return [TextContent(type="text", text=f"🔥 Error executing {name}: {str(e)}")]


# --- Server Entry Points ---


async def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 3000,
    keepalive_interval: int = 15,
):
    """
    Start the MCP server with specified transport.

    Args:
        transport: "stdio" for Claude Desktop, "sse" for Claude Code CLI
        host: Host to bind (SSE only)
        port: Port to listen (SSE only)
        keepalive_interval: SSE keep-alive heartbeat in seconds
    """
    # Performance info
    logger.info(f"🚀 Starting Omni MCP Server ({transport.upper()})")
    logger.info(
        f"📊 Performance: uvloop={'✅' if _HAS_UVLOOP else '❌'}, "
        f"orjson={'✅' if _HAS_ORJSON else '❌'}"
    )

    if transport == "stdio":
        logger.info("📡 Mode: STDIO (Claude Desktop)")
        await _run_stdio()

    elif transport == "sse":
        logger.info(f"📡 Mode: SSE (http://{host}:{port})")

        # Enable uvloop for SSE mode
        if _HAS_UVLOOP:
            uvloop.install()
            logger.info("⚡️ uvloop enabled for SSE")

        await _run_sse(host, port, keepalive_interval)

    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'sse'.")


async def _run_stdio():
    """Run server in stdio mode for Claude Desktop."""
    async with server_lifespan():
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
            except Exception as e:
                logger.critical(f"💥 Stdio server crashed: {e}", exc_info=True)
                raise


async def _run_sse(host: str, port: int, keepalive_interval: int):
    """Run server in SSE mode for Claude Code CLI."""
    sse = SseServerTransport("/sse")

    async def handle_sse(request: Request):
        """Handle SSE connection."""
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    async def handle_messages(request: Request):
        """Handle POST messages for SSE."""
        await sse.handle_post_message(request.scope, request.receive, request._send)

    async def handle_health(request: Request):
        """Health check endpoint."""
        return Response(content="OK", media_type="text/plain")

    async def handle_ready(request: Request):
        """Readiness check."""
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        skills_count = len(manager.list_loaded())

        status = {
            "status": "ready",
            "skills_loaded": skills_count,
            "performance": {
                "uvloop": _HAS_UVLOOP,
                "orjson": _HAS_ORJSON,
            },
        }
        return Response(
            content=json_dumps(status),
            media_type="application/json",
        )

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/health", endpoint=handle_health),
            Route("/ready", endpoint=handle_ready),
        ],
        lifespan=lambda _: server_lifespan(),
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="error",
        loop="uvloop" if _HAS_UVLOOP else "auto",
        timeout_keep_alive=keepalive_interval if keepalive_interval > 0 else None,
    )
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


# --- Exports ---
__all__ = [
    "server",
    "run_mcp_server",
]
