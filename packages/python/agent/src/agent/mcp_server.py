"""
agent/mcp_server.py
Phase 29: Omni MCP Server (Refactored)

Single Entry Point Architecture with clean protocol-based design.

Usage:
    @omni("git.status")              # Execute git status
    @omni("git.commit", {"message": "..."})  # Execute with args
    @omni("help")                    # Show all skills
    @omni("git")                     # Show git commands
"""

from mcp.server.fastmcp import FastMCP, Context
from typing import Optional, Dict, Any

import structlog

from common.settings import get_setting
from common.config_paths import get_project_root

logger = structlog.get_logger(__name__)

# Get skills directory from settings
SKILLS_DIR = get_project_root() / get_setting("skills.path", "assets/skills")

# Create MCP Server - Single tool only
mcp = FastMCP("omni-agentic-os")


# =============================================================================
# Omni CLI - The ONE Entry Point Tool
# =============================================================================


@mcp.tool(name="omni")
async def omni(
    input: str,
    args: Optional[Dict[str, Any]] = None,
    ctx: Context = None,
) -> str:
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
        ctx: MCP Context for logging and progress reporting

    Returns:
        Command result as string (formatted Markdown)
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    # Normalize input
    input = input.strip()
    args = args or {}

    # Log dispatch info to Claude
    if ctx:
        ctx.info(f"Omni Dispatch: {input} | Args: {len(args)}")

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

    # Handle special "help" macro for individual skills
    # e.g., @omni("git.help") returns Repomix-packed skill context
    if command is None and raw_cmd == "help":
        # This is the skill help macro
        result = await manager.run(skill_name, "help", args)
        return result

    if command is None:
        return f"Error: Command {skill_name}.{raw_cmd} not found"

    # Report progress for potentially long operations
    if ctx:
        await ctx.report_progress(0, 100)

    # Execute the command (async native)
    result = await manager.run(skill_name, cmd_name, args)

    if ctx:
        await ctx.report_progress(100, 100)

    return result


def _render_help(manager) -> str:
    """Render help showing all available skills."""
    skills = manager.list_loaded()

    if not skills:
        return "🛠️ **No skills available**"

    lines = ["# 🛠️ Available Skills", ""]

    for skill_name in sorted(skills):
        info = manager.get_info(skill_name)
        if info:
            lines.append(f"## {skill_name}")
            lines.append(f"- **Commands**: {info['command_count']}")
            lines.append("")

            # Get commands for this skill
            cmds = manager.get_commands(skill_name)
            # Show first few commands
            sorted_cmds = sorted(cmds)[:5]
            for cmd in sorted_cmds:
                lines.append(f"  - `{skill_name}.{cmd}`")
            if len(cmds) > 5:
                lines.append(f"  - ... and {len(cmds) - 5} more")
            lines.append("")

    lines.append("---")
    lines.append("**Usage**: `@omni('skill.command', args={})`")
    lines.append("**Help**: `@omni('skill')` or `@omni('help')`")

    return "\n".join(lines)


def _render_skill_help(manager, skill_name: str) -> str:
    """Render help for a specific skill."""
    if not manager._ensure_fresh(skill_name):
        available = manager.list_loaded()
        if not available:
            return f"Skill '{skill_name}' not found. No skills available."
        return f"Skill '{skill_name}' not found.\n\n**Available skills:**\n- " + "\n- ".join(
            available
        )

    skill = manager._skills.get(skill_name)
    if skill is None:
        return f"Skill '{skill_name}' not loaded"

    # Group commands by category
    from agent.core.protocols import SkillCategory

    by_category: dict[SkillCategory, list] = {}
    for cmd_name, cmd in skill.commands.items():
        cat = cmd.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((cmd_name, cmd.description))

    lines = [f"# 🛠️ {skill_name}", ""]

    # Standard category order
    category_order = [
        SkillCategory.READ,
        SkillCategory.VIEW,
        SkillCategory.WORKFLOW,
        SkillCategory.WRITE,
        SkillCategory.EVOLUTION,
        SkillCategory.GENERAL,
    ]

    for category in category_order:
        if category in by_category:
            lines.append(f"## {category.value.upper()}")
            for cmd_name, description in sorted(by_category[category]):
                lines.append(f"- `{skill_name}.{cmd_name}`: {description}")
            lines.append("")

    lines.append("---")
    lines.append(f"**Usage**: `@omni('{skill_name}.<command>', args={{}})`")
    lines.append(f"**Total**: {len(skill.commands)} commands")

    return "\n".join(lines)


# =============================================================================
# Prompt Templates
# =============================================================================


@mcp.prompt()
def omni_help_prompt() -> str:
    """
    Returns the manual for Omni CLI.

    This prompt is automatically available to Claude when using the Omni MCP Server.
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    skills = manager.list_loaded()

    lines = [
        "# Omni Agentic OS - Quick Reference",
        "",
        "## Single Entry Point",
        "All capabilities are accessed via the SINGLE tool: `omni`.",
        "",
        "## Available Skills:",
    ]

    for skill_name in sorted(skills):
        info = manager.get_info(skill_name)
        if info:
            lines.append(f"- **{skill_name}**: {info.command_count} commands")

    lines.extend(
        [
            "",
            "## Usage Examples:",
            '- `@omni("git.status")` - Check git status',
            '- `@omni("file.read", path="README.md")` - Read a file',
            '- `@omni("help")` - Show all skills',
            '- `@omni("git")` - Show git commands',
            "",
            "## Key Principle",
            "Code is Mechanism, Prompt is Policy.",
            "Brain (prompts.md) -> Muscle (tools.py) -> Guardrails (lefthook).",
        ]
    )

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the Omni MCP Server."""
    import argparse

    parser = argparse.ArgumentParser(description="Omni Agentic OS - MCP Server (Phase 29)")
    parser.add_argument("--port", type=int, default=None, help="Port to run on")
    parser.add_argument("--stdio", action="store_true", default=True, help="Use stdio transport")
    args = parser.parse_args()

    logger.info("🚀 Starting Omni MCP Server (Phase 29: Protocol-based Architecture)")
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
