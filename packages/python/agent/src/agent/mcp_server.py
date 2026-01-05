"""
src/agent/mcp_server.py
Omni MCP Server - Phase 25 "One Tool" Architecture.

SINGLE ENTRY POINT PHILOSOPHY:
- Only ONE tool registered with MCP: @omni
- All skill operations go through this single gate
- Claude's context stays clean and focused

Architecture:
- SkillManager: Scans skills, loads Python modules, builds command registry
- omni: The only door Claude can see - dispatches to any skill

Usage:
    # Start MCP Server
    python -m agent.mcp_server

    # In Claude CLI (SINGLE tool with @omni prefix):
    @omni("git.status")                    # Execute git status
    @omni("git.commit", {"message": "..."})  # Execute with args
    @omni("help")                          # Show all skills
    @omni("git")                           # Show git commands
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any
import structlog
from pathlib import Path

from common.mcp_core.settings import get_setting, get_project_root

logger = structlog.get_logger()

# Get skills directory from settings
SKILLS_DIR = get_project_root() / get_setting("skills.path", "agent/skills")

# Create MCP Server - Single tool only
mcp = FastMCP("omni-agentic-os")


# =============================================================================
# Omni CLI - The ONE Entry Point Tool
# =============================================================================


@mcp.tool(name="omni")
def omni(input: str, args: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute any skill command or get help.

    This is THE ONLY tool registered with MCP. All operations go through this gate.
    Use @omni in Claude to invoke.

    Usage:
        # Execute a command: @omni("skill.command")
        @omni("git.status")
        @omni("git.commit", {"message": "Fix bug"})
        @omni("file.read", {"path": "README.md"})

        # Get help
        @omni("help")           # List all skills
        @omni("git")            # Show git commands

    Args:
        input: Command like "skill.command", "skill", or "help"
        args: Optional arguments for the command (dict)

    Returns:
        Command result as string (formatted Markdown)
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    # Normalize input
    input = input.strip()
    args = args or {}

    # Handle help cases
    if input == "help" or input == "?":
        return _render_help(manager)

    # Show skill commands if just skill name (no dot)
    if "." not in input:
        skill_name = input
        return _render_skill_help(manager, skill_name)

    # Parse skill.command
    # Format: "skill.command" -> skill_name="git", cmd_name="git_status"
    if "." not in input:
        return f"Invalid format: '{input}'. Use '@omni(\"skill.command\")'"

    parts = input.split(".")
    skill_name = parts[0]
    # Build command name: skill.command -> skill_command (or just command)
    # e.g., "git.status" -> "git_status", "file.read" -> "read_file"
    raw_cmd = "_".join(parts[1:])

    # Try both with and without skill prefix
    cmd_with_prefix = f"{skill_name}_{raw_cmd}" if raw_cmd else raw_cmd
    cmd_without_prefix = raw_cmd

    # First try with prefix (e.g., git_status), then without (e.g., read_file)
    command = manager.get_command(skill_name, cmd_with_prefix)
    if command is None:
        command = manager.get_command(skill_name, cmd_without_prefix)
        cmd_name = cmd_without_prefix
    else:
        cmd_name = cmd_with_prefix

    if command is None:
        return f"Error: Command {skill_name}.{raw_cmd} not found"

    # Execute the command
    result = manager.run(skill_name, cmd_name, args)
    return result


def _render_help(manager) -> str:
    """Render help showing all available skills."""
    skills = manager.list_available_skills()

    if not skills:
        return "🛠️ **No skills available**"

    lines = ["# 🛠️ Available Skills", ""]

    for skill_name in sorted(skills):
        info = manager.get_skill_info(skill_name)
        if info:
            lines.append(f"## {skill_name}")
            lines.append(f"- **Commands**: {info['command_count']}")
            lines.append("")

            # Show first few commands (info["commands"] is a list)
            cmds = sorted(info["commands"])[:5]
            for cmd in cmds:
                lines.append(f"  - `{skill_name}.{cmd}`")
            if len(info["commands"]) > 5:
                lines.append(f"  - ... and {len(info['commands']) - 5} more")
            lines.append("")

    lines.append("---")
    lines.append("**Usage**: `@omni('skill.command', args={})`")
    lines.append("**Help**: `@omni('skill')` or `@omni('help')`")

    return "\n".join(lines)


def _render_skill_help(manager, skill_name: str) -> str:
    """Render help for a specific skill."""
    if skill_name not in manager.skills:
        available = manager.list_available_skills()
        if not available:
            return f"Skill '{skill_name}' not found. No skills available."
        return f"Skill '{skill_name}' not found.\n\n**Available skills:**\n- " + "\n- ".join(
            available
        )

    skill_obj = manager.skills[skill_name]

    # Group commands by category
    by_category: Dict[str, list] = {}
    for cmd_name, cmd in skill_obj.commands.items():
        cat = cmd.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((cmd_name, cmd.description))

    lines = [f"# 🛠️ {skill_name}", ""]

    for category in ["read", "view", "workflow", "write", "evolution", "general"]:
        if category in by_category:
            lines.append(f"## {category.upper()}")
            for cmd_name, description in sorted(by_category[category]):
                lines.append(f"- `{skill_name}.{cmd_name}`: {description}")
            lines.append("")

    lines.append("---")
    lines.append(f"**Usage**: `@omni('{skill_name}.<command>', args={{}})`")
    lines.append(f"**Total**: {len(skill_obj.commands)} commands")

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the Omni MCP Server."""
    import argparse

    parser = argparse.ArgumentParser(description="Omni Agentic OS - MCP Server (Phase 25)")
    parser.add_argument("--port", type=int, default=None, help="Port to run on")
    parser.add_argument("--stdio", action="store_true", default=True, help="Use stdio transport")
    args = parser.parse_args()

    logger.info("🚀 Starting Omni MCP Server (Phase 25: One Tool Architecture)")
    logger.info("📦 Single entry point: omni_run(command, args)")

    # Log available tools (should be exactly 1)
    tools = list(mcp._tool_manager._tools.values())
    logger.info(f"📋 Available tools: {len(tools)} (expected: 1)")
    for tool in tools:
        logger.info(f"  - {tool.name}")

    if args.stdio:
        # Run with stdio transport (for Claude Desktop)
        mcp.run(transport="stdio")
    else:
        # Run with HTTP transport
        mcp.run(host="0.0.0.0", port=args.port or 3000)


if __name__ == "__main__":
    main()
