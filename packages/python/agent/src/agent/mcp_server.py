"""
agent/mcp_server.py
Phase 29: Omni MCP Server (Refactored)

Single Entry Point Architecture with clean protocol-based design.

Usage:
    @omni("git.status")              # Execute git status
    @omni("git.commit", {"message": "..."})  # Execute with args
    @omni("help")                    # Show all skills
    @omni("git")                     # Show git commands

Performance Optimizations:
- Lazy skill loading (only load when command invoked)
- O(1) command lookup via SkillManager._command_cache
- Throttled mtime checks (100ms) for hot-reload
- Lazy logger initialization
"""

from mcp.server.fastmcp import FastMCP, Context
from typing import Optional, Dict, Any

# Lazy logger - defer structlog.get_logger() to avoid import-time overhead
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


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

    # Log dispatch info to Claude (lazy logger)
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
    # Format: "skill.command" -> skill_name="git", cmd_name="git.status"
    if "." not in input:
        return f"Invalid format: '{input}'. Use '@omni(\"skill.command\")'"

    parts = input.split(".")
    skill_name = parts[0]
    # Command name: skill.command -> command (with skill prefix)
    # e.g., "git.status" -> "git.status", "file.read" -> "file.read"
    cmd_name = ".".join(parts[1:])

    # Use cmd_name directly (skill.command format maps to command name directly)
    # LLM calls "@omni('git.status')" -> lookup command "git.status"
    cmd_name = input  # Use full input as command name
    command = manager.get_command(skill_name, cmd_name)

    # Handle special "help" macro for individual skills
    # e.g., @omni("git.help") returns Repomix-packed skill context
    if command is None and cmd_name == "help":
        # This is the skill help macro
        result = await manager.run(skill_name, "help", args)
        return result

    if command is None:
        return f"Error: Command {cmd_name} not found"

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
            lines.append(f"- **{skill_name}**: {info['command_count']} commands")

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
# Server Runner with Transport Support
# =============================================================================


async def run_mcp_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 3000):
    """
    Start the MCP server with the specified transport mode.

    Args:
        transport: Transport mode - "stdio" for Claude Desktop, "sse" for Claude Code CLI
        host: Host to bind to (SSE only, defaults to 127.0.0.1 for security)
        port: Port to listen on (only for SSE mode, use 0 for random available port)
    """
    logger = _get_logger()
    logger.info(f"🚀 Starting Omni MCP Server in {transport.upper()} mode")

    # Log available tools
    tools = list(mcp._tool_manager._tools.values())
    logger.info(f"📋 Available tools: {len(tools)}")
    for tool in tools:
        logger.info(f"  - {tool.name}")

    # Preload core skills at startup
    try:
        from agent.core.bootstrap import boot_core_skills

        boot_core_skills(mcp)
        logger.info("✅ Core skills preloaded")
    except Exception as e:
        logger.warning(f"⚠️  Failed to preload skills: {e}")

    if transport == "stdio":
        # Stdio mode (Claude Desktop)
        logger.info("📡 Running in stdio mode (Claude Desktop)")
        await mcp.run_stdio_async()
    elif transport == "sse":
        # SSE mode (Claude Code CLI / debugging)
        logger.info(f"📡 Running in SSE mode on {host}:{port}")
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.requests import Request
        import uvicorn

        sse = SseServerTransport("/sse")

        async def handle_sse(request: Request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp.run(
                    streams[0],
                    streams[1],
                    mcp.create_initialization_options(),
                )

        async def handle_messages(request: Request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    else:
        raise ValueError(f"Unknown transport mode: {transport}. Use 'stdio' or 'sse'.")
