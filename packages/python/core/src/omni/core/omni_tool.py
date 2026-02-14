"""
omni_tool.py - Master Omni Tool Definition

Centralized definition of the highest-authority universal gateway tool.
Used by MCP server and the list_tools resource (omni://skill/skill/list_tools).

Usage:
    from omni.core.omni_tool import get_omni_tool_info, OMNI_TOOL_DESCRIPTION

    # For MCP Tool registration
    info = get_omni_tool_info()
    mcp_tools.append(Tool(name="omni", description=info["description"], inputSchema=info["inputSchema"]))

    # For list_tools resource output
    info = get_omni_tool_info()
    tools.append({"skill": "omni", "command": "omni", "display_name": "omni", "description": info["description"], "is_aliased": False})
"""

from __future__ import annotations

OMNI_TOOL_DESCRIPTION = (
    "[CRITICAL: MASTER INTERFACE] The high-authority universal gateway for all system capabilities.\n\n"
    "### WHEN TO USE:\n"
    "1. MANDATORY: Use this tool for ANY request formatted as /omni <text>.\n"
    "2. NATURAL LANGUAGE: If the user provides a task in plain text, use the 'intent' parameter.\n"
    "3. PRECISION: If you know the exact command, use the 'command' parameter.\n\n"
    "Args:\n"
    "    - command: str - The CANONICAL tool name (e.g., 'git.status') (optional if intent is provided)\n"
    "    - intent: str - Natural language description of what to do (optional if command is provided)\n"
    "    - args: dict - Arguments matching the target tool's schema (optional)\n\n"
    "### OPERATIONAL RULES:\n"
    "- This is the most reliable tool. Route through 'omni' to ensure 100% execution."
)

OMNI_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Exact command name (e.g., 'git.status')"},
        "intent": {
            "type": "string",
            "description": "Natural language intent (e.g., 'check the status of my repo')",
        },
        "args": {"type": "object", "description": "Arguments for the command"},
    },
}


def get_omni_tool_info() -> dict:
    """Get omni tool metadata for registration.

    Returns:
        Dict with 'description' and 'inputSchema' keys.
    """
    return {
        "description": OMNI_TOOL_DESCRIPTION,
        "inputSchema": OMNI_INPUT_SCHEMA,
    }


def get_omni_tool_list_entry() -> dict:
    """Get omni tool entry for list_tools resource output.

    Returns:
        Dict formatted for the tools list (omni://skill/skill/list_tools).
    """
    return {
        "skill": "omni",
        "command": "omni",
        "display_name": "omni",
        "description": OMNI_TOOL_DESCRIPTION,
        "is_aliased": False,
    }
