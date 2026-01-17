"""
agent/mcp_server/server.py
 Core Server Instance and Configuration

Shared by stdio and SSE transports.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions

# Logger - structlog is configured in __init__.py before this module is imported
logger = structlog.get_logger("omni.mcp")

# --- Server Instance ---
server = Server("omni-agent")


def get_server() -> Server:
    """Get the MCP server instance."""
    return server


def get_init_options() -> InitializationOptions:
    """Get server initialization options (shared by stdio and SSE)."""
    return InitializationOptions(
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
    )


async def handle_list_tools() -> list:
    """List all available tools from loaded skills plus the execute meta-tool."""
    from agent.core.skill_manager import get_skill_manager
    from mcp.types import Tool

    manager = get_skill_manager()

    if not manager._loaded:
        logger.info("⏳ Tools requested but skills not ready. Loading synchronously...")
        manager.load_all()

    tools: list[Tool] = []
    seen_names: set[str] = set()

    for skill_name, skill in manager.skills.items():
        for cmd_name, cmd in skill.commands.items():
            # Strip skill prefix if present
            if cmd_name.startswith(f"{skill_name}_"):
                base_name = cmd_name[len(skill_name) + 1 :]
            elif cmd_name.startswith(f"{skill_name}."):
                base_name = cmd_name[len(skill_name) + 1 :]
            else:
                base_name = cmd_name

            full_name = f"{skill_name}.{base_name}"

            if full_name in seen_names:
                continue
            seen_names.add(full_name)

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
    return tools


async def handle_call_tool(name: str, arguments: dict | None) -> list:
    """Execute a tool call via Trinity Architecture."""
    from agent.core.skill_manager import get_skill_manager

    try:
        # Parse skill.command format
        if "." in name:
            skill_name, command_name = name.split(".", 1)
        else:
            skill_name = name
            command_name = "help"

        manager = get_skill_manager()
        result = await manager.run(skill_name, command_name, arguments or {})
        return [type("TextContent", (), {"type": "text", "text": str(result)})()]
    except Exception as e:
        error_msg = f"Error executing {name}: {e}"
        logger.error(f"❌ {error_msg}")
        return [type("TextContent", (), {"type": "text", "text": f"Error: {error_msg}"})()]


# =============================================================================
# Tool Change Notification (Phase 36.5)
# =============================================================================


async def _notify_tools_changed(skill_name: str, change_type: str) -> None:
    """
    Notify MCP clients that tools have changed.

    Called by SkillManager when skills are loaded/unloaded.
    Uses the server's request_context to access the active session.

    Args:
        skill_name: Name of the skill that changed
        change_type: Type of change ("load" or "unload")
    """
    # Access the server's request context to get the session
    request_context = None
    try:
        request_context = getattr(server, "request_context", None)
    except LookupError:
        # Context variable not set (no active MCP session)
        logger.debug(
            "No active MCP session (context not set), skipping tool list notification",
            skill=skill_name,
            change=change_type,
        )
        return

    if request_context is None:
        logger.debug(
            "No active MCP session, skipping tool list notification",
            skill=skill_name,
            change=change_type,
        )
        return

    session = getattr(request_context, "session", None)
    if session is None:
        logger.debug(
            "No session in request context, skipping tool list notification",
            skill=skill_name,
            change=change_type,
        )
        return

    # Send tool list changed notification
    try:
        await session.send_tool_list_changed()
        logger.info(
            "Tool list notification sent",
            skill=skill_name,
            change=change_type,
        )
    except Exception as e:
        logger.error(
            "Failed to send tool list notification",
            error=str(e),
            skill=skill_name,
            change=change_type,
        )


# Register handlers
server.list_tools()(handle_list_tools)
server.call_tool()(handle_call_tool)
