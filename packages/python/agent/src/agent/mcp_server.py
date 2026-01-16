"""
agent/mcp_server.py
 High-Performance MCP Server (Official SDK)

Architecture:
- Pure mcp.server.Server
- Stdio mode: Minimal, reliable, no background tasks
- SSE mode: uvloop + orjson for high performance
- Skill execution via Trinity Architecture

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
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ToolAnnotations

# Web Server (For SSE)
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
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


# --- Execute Tool ( Trinity v2.0) ---


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List all available tools from loaded skills plus the execute meta-tool.

     The execute tool is a meta-tool that allows executing any skill command
    via the pattern execute("skill.command", {"arg": "value"}).
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    if not manager._loaded:
        logger.info("⏳ Tools requested but skills not ready. Loading synchronously...")
        await manager.load_all()

    tools: list[Tool] = []

    # Step 1: Add all skill commands from SkillManager (Phase 73 fix)
    # Format: skill.command (only replace first underscore with dot)
    seen_names: set[str] = set()
    for skill_name, skill in manager.skills.items():
        for cmd_name, cmd in skill.commands.items():
            # Strip skill prefix if present (e.g., "git_commit" -> "commit")
            if cmd_name.startswith(f"{skill_name}_"):
                # Remove skill prefix: "git_commit" -> "commit"
                base_name = cmd_name[len(skill_name) + 1 :]
            elif cmd_name.startswith(f"{skill_name}."):
                # Already has skill prefix with dot: "git.status" -> "status"
                base_name = cmd_name[len(skill_name) + 1 :]
            else:
                # No skill prefix, use as-is
                base_name = cmd_name

            # Only replace first underscore with dot for skill.command format
            # Keep remaining underscores intact: "commit_no_verify" stays as-is
            full_name = f"{skill_name}.{base_name}"

            if full_name in seen_names:
                continue
            seen_names.add(full_name)

            # Build input schema from SkillCommand
            input_schema = cmd.input_schema if isinstance(cmd.input_schema, dict) else {}

            tools.append(
                Tool(
                    name=full_name,
                    description=cmd.description or f"Execute {full_name}",
                    inputSchema=input_schema
                    or {"type": "object", "properties": {}, "required": []},
                )
            )

    logger.info(f"📋 [Tools] Listed {len(tools)} skill commands from {len(manager.skills)} skills")

    # Step 2: Add omni meta-tool for skill command execution
    tools.append(
        Tool(
            name="omni",
            title="Execute Skill Command",
            description="Execute a skill command. Usage: omni(skill_command='git.status', arguments={})",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill_command": {
                        "type": "string",
                        "description": "Skill command in 'skill.command' format (e.g., 'git.status', 'terminal.run_task')",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments for the skill command as a JSON object",
                        "additionalProperties": True,
                    },
                },
                "required": ["skill_command"],
                "additionalProperties": False,
            },
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=False,
            ),
        )
    )

    logger.info(f"📋 [Tools] Listed {len(tools)} tools total")
    return tools


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

    #  Register Hot-Reload Observers
    # This ensures MCP clients receive tool list updates and vector index stays in sync
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    # Observer 1: MCP tool list update
    manager.subscribe(_notify_tools_changed)
    logger.info("👀 [Lifecycle] Hot-reload observer registered (MCP Tools)")

    # Observer 2: Index Sync (Phase 36.5 - Bridge between Vector Discovery and Hot Reload)
    manager.subscribe(_update_search_index)
    logger.info("🔍 [Lifecycle] Index Sync observer registered (ChromaDB)")

    #  Start Skill Watcher for auto-sync
    from agent.core.skill_manager.watcher import start_global_watcher

    try:
        start_global_watcher()
        logger.info("👀 [Lifecycle] Skill Watcher started (auto-sync)")
    except Exception as e:
        logger.warning(f"⚠️  [Lifecycle] Skill Watcher failed to start: {e}")

    logger.info("✅ [Lifecycle] Server ready")

    try:
        yield
    finally:
        #  Stop Skill Watcher
        from agent.core.skill_manager.watcher import stop_global_watcher

        stop_global_watcher()
        logger.info("🛑 [Lifecycle] Shutting down...")


# --- Tool Call Handler ---


# Cached skill overrides from settings (loaded lazily)
_skill_overrides_cache: dict | None = None


def _get_skill_overrides() -> dict:
    """
    Load skill overrides from settings.yaml.

    Returns:
        Dict mapping "skill.command" -> {"alias": "...", "append_doc": "..."}
    """
    global _skill_overrides_cache
    if _skill_overrides_cache is None:
        try:
            from common.config.settings import get_setting

            overrides = get_setting("skills.overrides", {})
            _skill_overrides_cache = overrides
            logger.info(f"📖 [Config] Loaded {len(overrides)} skill overrides from settings.yaml")
        except Exception as e:
            logger.warning(f"⚠️ [Config] Failed to load skill overrides: {e}")
            _skill_overrides_cache = {}
    return _skill_overrides_cache


def _get_alias_reverse_map() -> dict:
    """
    Build reverse mapping: alias_name -> original_name for call resolution.

    Returns:
        Dict mapping "alias" -> "skill.command"
    """
    overrides = _get_skill_overrides()
    reverse_map = {}
    for original_name, config in overrides.items():
        alias = config.get("alias")
        if alias:
            reverse_map[alias] = original_name
    return reverse_map


def _get_tool_name(original_name: str, description: str = "") -> tuple[str, str]:
    """
    Convert skill.command to tool name and inject behavioral guidance.

    Reads from settings.yaml:skills.overrides for configuration.
    Default: Keep "skill.command" format (no conversion).
    Only apply alias if explicitly configured.

    Returns:
        tuple of (tool_name, enhanced_description)
    """
    overrides = _get_skill_overrides()
    config = overrides.get(original_name, {})

    # Apply alias from config if present, otherwise keep original format
    tool_name = config.get("alias", original_name)

    # Inject behavioral guidance from config (Docstring Injection)
    append_doc = config.get("append_doc", "")
    if append_doc:
        enhanced_desc = description + append_doc
    else:
        enhanced_desc = description

    return tool_name, enhanced_desc


async def _notify_tools_changed(skill_name: str, change_type: str):
    """
     Observer callback for skill changes.

    Called when SkillManager loads/unloads/reloads skills.
    Triggers MCP client to refresh tool list via send_tool_list_changed().

    Args:
        skill_name: Name of the skill that changed
        change_type: "load", "unload", or "reload"
    """
    try:
        # We must check if we are currently inside a request context
        # This works because skill changes (like jit_install) are triggered
        # as tool calls within a session scope.
        request_ctx = server.request_context
        if request_ctx and request_ctx.session:
            await request_ctx.session.send_tool_list_changed()
            logger.info(f"🔔 [{change_type.title()}] Sent tool list update to client: {skill_name}")
        else:
            # No active session - this is expected during startup
            logger.debug(
                f"🔕 [{change_type.title()}] Skill changed but no active session: {skill_name}"
            )
    except Exception as e:
        # Log at debug level since this is expected during startup
        logger.debug(f"⚠️ [Hot Reload] Notification skipped (no session): {e}")


# Global lock to prevent overlapping index syncs
_index_sync_lock: bool = False


async def _update_search_index(skill_name: str, change_type: str):
    """
     Index Sync observer for Rust-backed VectorMemory.

    Keeps the vector search index in sync with runtime skill changes.
    Uses Rust-backed sync_skills() for incremental updates based on file hashes.

    Args:
        skill_name: Name of the skill that changed
        change_type: "load", "unload", or "reload"
    """
    global _index_sync_lock

    # Prevent overlapping syncs
    if _index_sync_lock:
        logger.debug("[Index Sync] Skipping - sync already in progress")
        return

    _index_sync_lock = True
    try:
        from agent.core.skill_discovery import reindex_skills_from_manifests

        # With Rust-backed sync_skills, we just trigger incremental sync
        # which uses file hashes to determine what changed
        result = await reindex_skills_from_manifests()
        stats = result.get("stats", {})

        # Only log if there were actual changes
        added = stats.get("added", 0)
        modified = stats.get("modified", 0)
        deleted = stats.get("deleted", 0)

        if added > 0 or modified > 0 or deleted > 0:
            logger.info(f"🔄 [Index Sync] Sync completed: {stats}")
        else:
            logger.debug(f"🔕 [Index Sync] No changes detected (total={stats.get('total', 0)})")

    except Exception as e:
        logger.warning(f"⚠️ [Index Sync] Error updating index for {skill_name}: {e}")
    finally:
        _index_sync_lock = False


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """
    Execute a tool via SkillManager.

    Supports:
    - @omni("skill.command", {"arg": "value"}) - Meta-tool for skill execution
    - Native alias format: "run_command" -> resolves to "terminal.run_task"
    - Original format: "terminal.run_task"
    """
    from agent.core.skill_manager import get_skill_manager

    args = arguments or {}
    logger.info(f"🔨 [Tool] Executing: {name}")

    # Fix common argument serialization issues from MCP clients
    fixed_args = {}
    for key, value in args.items():
        if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            # Try to parse string as JSON array
            try:
                import json

                parsed = json.loads(value)
                if isinstance(parsed, list):
                    fixed_args[key] = parsed
                    continue
            except json.JSONDecodeError:
                pass
        fixed_args[key] = value
    args = fixed_args

    logger.info(f"🔨 [Tool] Executing: {name}, args: {args}")

    try:
        # Handle @omni meta-tool
        if name == "omni":
            skill_command = args.get("skill_command")
            if not skill_command:
                return [
                    TextContent(
                        type="text", text="❌ Missing 'skill_command' argument for @omni tool."
                    )
                ]

            # Extract skill.command from the first argument
            if "." in skill_command:
                parts = skill_command.split(".", 1)
                skill_name = parts[0]
                command_name = parts[1]
            else:
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Invalid skill_command: {skill_command}. Use 'skill.command' format.",
                    )
                ]

            # Get the actual arguments (everything except skill_command)
            # If "arguments" key exists, unpack it to top-level (flatten the structure)
            command_args = {}
            for k, v in args.items():
                if k == "skill_command":
                    continue
                elif k == "arguments" and isinstance(v, dict):
                    # Unpack nested arguments: {"arguments": {"command": "echo", "args": [...]}} -> {"command": "echo", "args": [...]}
                    command_args.update(v)
                else:
                    command_args[k] = v

            # Resolve alias if needed
            alias_reverse = _get_alias_reverse_map()
            original_name = skill_command
            if skill_command in alias_reverse:
                original_name = alias_reverse[skill_command]
                logger.info(f"🔄 [Tool] Resolved alias '{skill_command}' -> '{original_name}'")

            # Re-parse with resolved name
            if "." in original_name:
                parts = original_name.split(".", 1)
                skill_name = parts[0]
                command_name = parts[1]

            logger.info(
                f"🔨 [Tool] Executing {skill_name}.{command_name} with args: {command_args}"
            )

            # Execute via SkillManager
            manager = get_skill_manager()
            result = await manager.run(skill_name, command_name, command_args)
            return [TextContent(type="text", text=result)]

        original_name = name

        # Resolve alias to original name using config-driven reverse map
        alias_reverse = _get_alias_reverse_map()
        if name in alias_reverse:
            original_name = alias_reverse[name]
            logger.info(f"🔄 [Tool] Resolved alias '{name}' -> '{original_name}'")

        # Parse skill.command format
        if "." in original_name:
            parts = original_name.split(".", 1)
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
                    InitializationOptions(
                        server_name="omni-agent",
                        server_version="1.0.0",
                        capabilities=server.get_capabilities(
                            notification_options=NotificationOptions(
                                tools_changed=True,
                                prompts_changed=True,
                                resources_changed=True,
                            ),
                            experimental_capabilities={},
                        ),
                    ),
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
                InitializationOptions(
                    server_name="omni-agent",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(
                            tools_changed=True,
                            prompts_changed=True,
                            resources_changed=True,
                        ),
                        experimental_capabilities={},
                    ),
                ),
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
