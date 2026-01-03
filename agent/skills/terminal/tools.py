"""
Terminal Skill Tools
Refactored from src/mcp_server/executor
Provides safe command execution with whitelist validation.
"""
import asyncio
import sys
import os
import platform
from typing import Optional

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
    """
    Check the current execution environment.
    Useful for debugging path issues.
    """
    info = [
        f"OS: {platform.system()} {platform.release()}",
        f"Python: {sys.version.split()[0]}",
        f"CWD: {os.getcwd()}",
        f"User: {os.getenv('USER', 'unknown')}",
        f"Path Separator: {os.path.sep}",
    ]
    return "\n".join(info)


def register(mcp: FastMCP):
    """Register Terminal tools."""

    @mcp.tool()
    async def execute_command_tool(command: str, timeout: int = 60) -> str:
        return await execute_command(command, timeout)

    @mcp.tool()
    async def inspect_environment_tool() -> str:
        return await inspect_environment()

    logger.info("Terminal skill tools registered")
