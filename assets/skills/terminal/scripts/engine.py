"""
scripts/engine.py - Terminal execution controller

This is an isolated script module - it runs in the same process but with
isolated namespace. Uses subprocess for command execution.

Phase 36: Extracted from tools.py for atomic structure.
"""

import asyncio
import re
import subprocess
from typing import Any


# Whitelist of allowed commands (empty = allow all for development)
ALLOWED_COMMANDS: list[str] = []

# Dangerous patterns that will always be blocked
DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+/", "rm -rf / - Deletes entire filesystem"),
    (r"rm\s+-rf\s+/\w+", "rm -rf /{path} - Dangerous recursive delete"),
    (r":\(\)\s*\{", "Fork bomb definition - recursive function"),
    (r"\{\s*:\s*\|\s*:\s*&\s*\}", "Fork bomb execution pattern"),
    (r"\$\(.*\)", "Command substitution - complex execution"),
    (r"`[^`]+`", "Backtick command substitution - complex execution"),
    (r">\s*/dev/", "Redirect to device - potential DoS"),
    (r"&&\s*", "Conditional execution - may alter logic"),
    (r"\|\|", "Conditional execution - may alter logic"),
    (r";\s*rm", "Chained rm - potential data loss"),
    (r"mkfs", "Format filesystem - destructive"),
    (r"dd\s+if=", "Direct disk access - dangerous"),
    (r"wget\s+.*\|\s*sh", "Pipe to shell - extremely dangerous"),
    (r"curl\s+.*\|\s*sh", "Pipe to shell - extremely dangerous"),
    (r"python.*-c.*\|", "Python one-liner pipe - suspicious"),
    (r"nc\s+-e", "Netcat with execute - reverse shell pattern"),
    (r"/etc/passwd", "Access to password file - privilege escalation risk"),
    (r"~/.ssh", "Access to SSH keys - credential theft risk"),
    (r"chmod\s+\+[xs]", "Add executable permission - privilege escalation"),
    (r"chown", "Change ownership - privilege escalation"),
    (r"sudo\s+rm", "sudo rm - high risk operation"),
]


def check_dangerous_patterns(command: str, args: list[str]) -> tuple[bool, str]:
    """Check if a command contains dangerous patterns."""
    full_command = f"{command} {' '.join(args)}"

    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, full_command, re.IGNORECASE):
            return False, f"Dangerous pattern detected: {description}"

    return True, ""


def run_command(command: str, args: list[str], timeout: int = 60) -> dict[str, Any]:
    """
    Execute a command with safety checks.

    Args:
        command: Command to execute
        args: Command arguments
        timeout: Timeout in seconds

    Returns:
        Dict with exit_code, stdout, stderr, duration_ms
    """
    # Check whitelist if not empty
    if ALLOWED_COMMANDS and command not in ALLOWED_COMMANDS:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Command '{command}' not in whitelist",
            "duration_ms": 0,
            "command": command,
            "args": args,
        }

    try:
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": 0,
            "command": command,
            "args": args,
        }

    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "duration_ms": timeout * 1000,
            "command": command,
            "args": args,
        }
    except FileNotFoundError:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command not found: {command}",
            "duration_ms": 0,
            "command": command,
            "args": args,
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": 0,
            "command": command,
            "args": args,
        }


async def run_command_async(command: str, args: list[str], timeout: int = 60) -> dict[str, Any]:
    """Async version of run_command."""
    if args is None:
        args = []

    # Security check
    is_safe, error_msg = check_dangerous_patterns(command, args)
    if not is_safe:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Blocked: {error_msg}",
            "duration_ms": 0,
            "command": command,
            "args": args,
        }

    try:
        start_time = asyncio.get_event_loop().time()

        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutExpired:
            process.kill()
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "duration_ms": timeout * 1000,
                "command": command,
                "args": args,
            }

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return {
            "exit_code": process.returncode,
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            "duration_ms": duration_ms,
            "command": command,
            "args": args,
        }

    except FileNotFoundError:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command not found: {command}",
            "duration_ms": 0,
            "command": command,
            "args": args,
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": 0,
            "command": command,
            "args": args,
        }


def format_result(result: dict[str, Any], command: str, args: list[str]) -> str:
    """Format execution result for display."""
    output = []

    if result.get("stdout"):
        output.append(result["stdout"])

    if result.get("stderr"):
        output.append(f"STDERR:\n{result['stderr']}")

    if result.get("exit_code", 0) != 0:
        output.append(f"Exit code: {result.get('exit_code')}")

    return "\n".join(output).strip() or "(no output)"
