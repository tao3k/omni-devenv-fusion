"""
execution/executor.py
Safe command execution with security boundaries.

Phase 29: Protocol-based design with slots=True.

Provides unified command execution with security boundaries and sandboxing.
Used by both orchestrator.py and coder.py servers.

Usage:
    from mcp_core.execution import SafeExecutor

    result = await SafeExecutor.run("just", ["test"])
    result = await SafeExecutor.run_sandbox("echo", ["hello"])
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import structlog

from .security import (
    check_dangerous_patterns,
    check_whitelist,
    create_sandbox_env,
    DEFAULT_ALLOWED_COMMANDS,
)

logger = logging.getLogger(__name__)


class SafeExecutor:
    """Provides safe command execution with consistent security boundaries.

    This class ensures both orchestrator.py and coder.py use the same
    security policies for command execution.

    Usage:
        result = await SafeExecutor.run("just", ["test"])
        result = await SafeExecutor.run_sandbox("echo", ["hello"])
    """

    @staticmethod
    async def run(
        command: str,
        args: list[str] | None = None,
        allowed_commands: dict[str, list[str]] | None = None,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Run a command with whitelist validation.

        Args:
            command: Command to run
            args: Command arguments
            allowed_commands: Custom allowed commands dict
            timeout: Max execution time in seconds
            cwd: Working directory

        Returns:
            Dict with keys: success (bool), stdout (str), stderr (str), exit_code (int), error (str)
        """
        if args is None:
            args = []

        # Security checks
        is_safe, error_msg = check_whitelist(command, args, allowed_commands)
        if not is_safe:
            logger.info("execution.blocked", command=command, args=args, reason=error_msg)
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg,
                "exit_code": -1,
                "error": error_msg,
            }

        is_safe, error_msg = check_dangerous_patterns(command, args)
        if not is_safe:
            logger.info("execution.dangerous_pattern", command=command, args=args, reason=error_msg)
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg,
                "exit_code": -1,
                "error": error_msg,
            }

        logger.info("execution.running", command=command, args=args)

        try:
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or str(Path.cwd()),
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode("utf-8")
            error = stderr.decode("utf-8")

            result = {
                "success": process.returncode == 0,
                "stdout": output,
                "stderr": error,
                "exit_code": process.returncode,
                "error": "",
            }

            logger.info(
                "execution.complete",
                command=command,
                returncode=process.returncode,
                success=result["success"],
            )

            return result

        except asyncio.TimeoutExpired:
            logger.info("execution.timeout", command=command, timeout=timeout)
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Timed out after {timeout}s",
            }

        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Command '{command}' not found",
            }

        except Exception as e:
            logger.info("execution.error", command=command, error=str(e))
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

    @staticmethod
    async def run_sandbox(
        command: str,
        args: list[str] | None = None,
        timeout: int = 60,
        read_only: bool = False,
        sandbox_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a command in a sandboxed environment with enhanced safety.

        Args:
            command: Command to run
            args: Command arguments
            timeout: Max execution time in seconds
            read_only: If True, mark as read-only operation
            sandbox_env: Custom sandbox environment

        Returns:
            Dict with keys: success (bool), stdout (str), stderr (str), exit_code (int), error (str)
        """
        if args is None:
            args = []

        # Security checks
        is_safe, error_msg = check_dangerous_patterns(command, args)
        if not is_safe:
            logger.info("sandbox.blocked", command=command, args=args, reason=error_msg)
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg,
                "exit_code": -1,
                "error": error_msg,
            }

        # Create sandbox environment
        env = sandbox_env or create_sandbox_env()
        if read_only:
            env["READ_ONLY_SANDBOX"] = "1"

        logger.info("sandbox.executing", command=command, read_only=read_only)

        try:
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(Path.cwd()),
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode("utf-8")
            error = stderr.decode("utf-8")

            result = {
                "success": process.returncode == 0,
                "stdout": output,
                "stderr": error,
                "exit_code": process.returncode,
                "error": "",
            }

            logger.info(
                "sandbox.complete",
                command=command,
                returncode=process.returncode,
                read_only=read_only,
            )

            return result

        except asyncio.TimeoutExpired:
            logger.info("sandbox.timeout", command=command, timeout=timeout)
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Timed out after {timeout}s",
            }

        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Command '{command}' not found",
            }

        except Exception as e:
            logger.info("sandbox.error", command=command, error=str(e))
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

    @staticmethod
    def format_result(result: dict[str, Any], command: str, args: list[str] | None = None) -> str:
        """Format execution result as a readable string.

        Args:
            result: Result dict from run() or run_sandbox()
            command: The command that was run
            args: Command arguments

        Returns:
            Formatted string representation
        """
        if args is None:
            args = []

        output = f"--- Execution: {command} {' '.join(args)} ---\n"
        output += f"Exit code: {result.get('exit_code', -1)}\n\n"

        if result.get("stdout"):
            output += f"stdout:\n{result['stdout']}\n"

        if result.get("stderr"):
            output += f"stderr:\n{result['stderr']}\n"

        if result.get("error"):
            output += f"Error: {result['error']}\n"

        if result.get("success"):
            output += "\n✅ Execution completed successfully."
        else:
            output += "\n⚠️  Execution failed or was blocked."

        return output.strip()


__all__ = ["SafeExecutor"]
