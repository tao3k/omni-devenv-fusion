"""
execution/security.py
Security utilities for command execution.

Phase 31: Pre-compiled regex patterns for performance.

Provides dangerous pattern detection and command whitelist checking.
"""

from __future__ import annotations

import re
from typing import Any

# Dangerous patterns to block in commands (string list for compatibility)
DANGEROUS_PATTERNS: list[str] = [
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

# Pre-compiled regex patterns for performance (Phase 31 optimization)
_COMPILED_PATTERNS: list[re.Pattern] = [
    re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS
]

# Safe commands whitelist (extendable per project)
DEFAULT_ALLOWED_COMMANDS: dict[str, list[str]] = {
    "just": ["validate", "build", "test", "lint", "fmt", "test-basic", "test-mcp", "agent-commit"],
    "nix": ["fmt", "build", "shell", "flake-check"],
    "git": [
        "status",
        "diff",
        "log",
        "add",
        "checkout",
        "branch",
        "stash",
        "merge",
        "revert",
        "tag",
        "remote",
        "show",
        "reset",
        "clean",
    ],
    "echo": [],  # Safe for testing
    "find": [],  # Read-only exploration
}


def check_dangerous_patterns(command: str, args: list[str]) -> tuple[bool, str]:
    """Check if command contains dangerous patterns.

    Uses pre-compiled regex patterns for O(1) pattern matching per call.

    Args:
        command: The command to check
        args: Command arguments

    Returns:
        Tuple of (is_safe, error_message)
    """
    full_cmd = f"{command} {' '.join(args)}"
    for i, pattern in enumerate(_COMPILED_PATTERNS):
        if pattern.search(full_cmd):
            return False, f"Blocked dangerous pattern: {DANGEROUS_PATTERNS[i]}"
    return True, ""


def check_whitelist(
    command: str, args: list[str], allowed_commands: dict[str, list[str]] | None = None
) -> tuple[bool, str]:
    """Check if command is in the whitelist.

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

    # Git commands accept paths as arguments (not just subcommands)
    if command == "git":
        # Git subcommands (like status, diff, log) are allowed
        # And paths are always allowed for git
        for arg in args:
            if arg.startswith("-"):
                continue  # Allow flags
            # Allow any subcommand that is in allowed_args OR looks like a path
            if arg in allowed_args:
                continue
            # Allow arguments that look like file paths (contain / or start with .)
            if "/" in arg or arg.startswith(".") or arg.startswith("/"):
                continue
            # Allow arguments that are git subcommands
            if arg in allowed_args:
                continue
            return False, f"Argument '{arg}' is not allowed for '{command}'."
        return True, ""

    # For non-git commands, use strict checking
    for arg in args:
        if arg.startswith("-"):
            continue  # Allow flags
        if arg not in allowed_args and not any(arg.startswith(a) for a in allowed_args):
            return False, f"Argument '{arg}' is not allowed for '{command}'."

    return True, ""


def create_sandbox_env(
    redact_keys: list[str] | None = None, restrict_home: bool = True
) -> dict[str, str]:
    """Create a sandboxed environment with restricted variables.

    Args:
        redact_keys: Environment variables to redact
        restrict_home: Whether to restrict HOME directory

    Returns:
        Sandbox environment dict
    """
    import os
    from pathlib import Path

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


__all__ = [
    "DANGEROUS_PATTERNS",
    "DEFAULT_ALLOWED_COMMANDS",
    "check_dangerous_patterns",
    "check_whitelist",
    "create_sandbox_env",
]
