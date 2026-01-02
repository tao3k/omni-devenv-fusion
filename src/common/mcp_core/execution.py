# mcp-core/execution.py
"""
Safe Command Execution Module

Provides unified command execution with security boundaries and sandboxing.
This module wraps subprocess calls to ensure safe operation across both
orchestrator.py and coder.py servers.

Features:
- Whitelist-based command validation
- Dangerous pattern blocking
- Environment sanitization
- Timeout protection
- Sandbox environment support
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger("mcp-core.execution")


# =============================================================================
# Security Configuration
# =============================================================================

# Dangerous patterns to block in commands
DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"dd\s+if=",
    r">\s*/dev/",
    r"\|\s*sh",
    r"&&\s*rm",
    r";\s*rm",
    r"chmod\s+777",
    r"chown\s+root:",
    r":\(\)\s*{",
    r"\$\(\s*",
]

# Safe commands whitelist (extendable per project)
DEFAULT_ALLOWED_COMMANDS = {
    "just": ["validate", "build", "test", "lint", "fmt", "test-basic", "test-mcp", "agent-commit"],
    "nix": ["fmt", "build", "shell", "flake-check"],
    "git": ["status", "diff", "log", "add", "checkout", "branch"],
    "echo": [],  # Safe for testing
    "find": [],  # Read-only exploration
}


# =============================================================================
# Security Check Functions
# =============================================================================

def check_dangerous_patterns(command: str, args: List[str]) -> Tuple[bool, str]:
    """
    Check if command contains dangerous patterns.

    Args:
        command: The command to check
        args: Command arguments

    Returns:
        Tuple of (is_safe, error_message)
    """
    full_cmd = f"{command} {' '.join(args)}"
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, full_cmd, re.IGNORECASE):
            return False, f"Blocked dangerous pattern: {pattern}"
    return True, ""


def check_whitelist(
    command: str, args: List[str], allowed_commands: Dict[str, List[str]] = None
) -> Tuple[bool, str]:
    """
    Check if command is in the whitelist.

    Args:
        command: The command to check
        args: Command arguments
        allowed_commands: Dict of allowed commands and their args

    Returns:
        Tuple of (is_safe, error_message)
    """
    if allowed_commands is None:
        allowed_commands = DEFAULT_ALLOWED_COMMANDS

    if command not in allowed_commands:
        return False, f"Command '{command}' is not allowed."

    allowed_args = allowed_commands.get(command, [])
    for arg in args:
        if arg.startswith("-"):
            continue  # Allow flags
        if arg not in allowed_args and not any(arg.startswith(a) for a in allowed_args):
            return False, f"Argument '{arg}' is not allowed for '{command}'."

    return True, ""


def create_sandbox_env(redact_keys: List[str] = None, restrict_home: bool = True) -> Dict[str, str]:
    """
    Create a sandboxed environment with restricted variables.

    Args:
        redact_keys: Environment variables to redact
        restrict_home: Whether to restrict HOME directory

    Returns:
        Sandbox environment dict
    """
    if redact_keys is None:
        redact_keys = ["AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "ANTHROPIC_API_KEY"]

    env = os.environ.copy()

    # Redact sensitive environment variables
    for var in redact_keys:
        if var in env:
            env[var] = "***REDACTED***"

    # Restrict home directory access
    if restrict_home:
        env["HOME"] = str(Path.cwd())

    return env


# =============================================================================
# Execution Classes
# =============================================================================

class SafeExecutor:
    """
    Provides safe command execution with consistent security boundaries.

    This class ensures both orchestrator.py and coder.py use the same
    security policies for command execution.

    Usage:
        result = await SafeExecutor.run("just", ["test"])
        result = await SafeExecutor.run_sandbox("echo", ["hello"])
    """

    @staticmethod
    async def run(
        command: str,
        args: Optional[List[str]] = None,
        allowed_commands: Dict[str, List[str]] = None,
        timeout: int = 60,
        cwd: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Run a command with whitelist validation.

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
            log.info("execution.blocked", command=command, args=args, reason=error_msg)
            return {"success": False, "stdout": "", "stderr": error_msg, "exit_code": -1, "error": error_msg}

        is_safe, error_msg = check_dangerous_patterns(command, args)
        if not is_safe:
            log.info("execution.dangerous_pattern", command=command, args=args, reason=error_msg)
            return {"success": False, "stdout": "", "stderr": error_msg, "exit_code": -1, "error": error_msg}

        log.info("execution.running", command=command, args=args)

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

            log.info(
                "execution.complete",
                command=command,
                returncode=process.returncode,
                success=result["success"],
            )

            return result

        except asyncio.TimeoutExpired:
            log.info("execution.timeout", command=command, timeout=timeout)
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": f"Timed out after {timeout}s"}

        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": f"Command '{command}' not found"}

        except Exception as e:
            log.info("execution.error", command=command, error=str(e))
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

    @staticmethod
    async def run_sandbox(
        command: str,
        args: Optional[List[str]] = None,
        timeout: int = 60,
        read_only: bool = False,
        sandbox_env: Dict[str, str] = None,
    ) -> Dict[str, any]:
        """
        Run a command in a sandboxed environment with enhanced safety.

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
            log.info("sandbox.blocked", command=command, args=args, reason=error_msg)
            return {"success": False, "stdout": "", "stderr": error_msg, "exit_code": -1, "error": error_msg}

        # Create sandbox environment
        env = sandbox_env or create_sandbox_env()
        if read_only:
            env["READ_ONLY_SANDBOX"] = "1"

        log.info("sandbox.executing", command=command, read_only=read_only)

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

            log.info(
                "sandbox.complete",
                command=command,
                returncode=process.returncode,
                read_only=read_only,
            )

            return result

        except asyncio.TimeoutExpired:
            log.info("sandbox.timeout", command=command, timeout=timeout)
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": f"Timed out after {timeout}s"}

        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": f"Command '{command}' not found"}

        except Exception as e:
            log.info("sandbox.error", command=command, error=str(e))
            return {"success": False, "stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

    @staticmethod
    def format_result(result: Dict[str, any], command: str, args: List[str] = None) -> str:
        """
        Format execution result as a readable string.

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
