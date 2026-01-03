"""
Terminal Skill Tools
"""
import asyncio
from mcp.server.fastmcp import FastMCP
from common.mcp_core.execution import SafeExecutor, check_dangerous_patterns
import structlog

logger = structlog.get_logger(__name__)


async def execute_command(command: str, timeout: int = 60) -> str:
    """
    Execute a shell command with whitelist validation.

    Args:
        command: The command string to execute (e.g., "uv sync", "just test").
        timeout: Maximum execution time in seconds (default: 60).
    """
    # Protocol Enforcement: Block direct git commit
    # Forces agent to use smart_commit in git skill
    cmd_lower = command.lower()
    if "git commit" in cmd_lower:
        return (
            "⛔️ PROHIBITED: Direct 'git commit' is disabled in Terminal.\n"
            "👉 You MUST use the 'smart_commit' tool in the 'git' skill.\n"
            "   Reason: Requires 'run just agent-commit' authorization flow."
        )

    # Parse command and args for security checks
    parts = command.strip().split()
    if not parts:
        return "Error: Empty command"

    cmd = parts[0]
    args = parts[1:]

    # Check dangerous patterns
    is_safe, error_msg = check_dangerous_patterns(command, args)
    if not is_safe:
        return f"Blocked: {error_msg}"

    # Execute using SafeExecutor (whitelist-based)
    result = await SafeExecutor.run(cmd, args, timeout=timeout)
    return SafeExecutor.format_result(result, cmd, args)


async def inspect_environment() -> str:
    """Check the current execution environment."""
    import os, platform
    return f"OS: {platform.system()}, CWD: {os.getcwd()}"


def register(mcp: FastMCP):
    """Register Terminal tools."""

    @mcp.tool()
    async def inspect_environment() -> str:
        """Check the current execution environment (read-only, safe)."""
        return await inspect_environment()

    @mcp.tool()
    async def execute_command(command: str, timeout: int = 60) -> str:
        """
        Execute a shell command.
        Security is provided by your MCP client's confirmation dialog.
        """
        return await execute_command(command, timeout)

    logger.info("Terminal skill tools registered")
