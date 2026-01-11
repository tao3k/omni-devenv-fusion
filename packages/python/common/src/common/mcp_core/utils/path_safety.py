"""
utils/path_safety.py
Path safety utilities.

Phase 29: Protocol-based design.

Provides path safety checking for file operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Trusted read-only paths (Nix store paths are immutable and safe)
_TRUSTED_ABSOLUTE_PATHS = {"/nix/store/"}


def is_safe_path(
    path: str,
    project_root: Path | None = None,
    blocked_dirs: set[str] | None = None,
    allow_hidden: bool = True,
    allowed_hidden_files: set[str] | None = None,
    allow_absolute: bool = False,
) -> tuple[bool, str]:
    """Check if a path is safe to access within the project.

    Args:
        path: Path to check
        project_root: Project root directory (defaults to cwd)
        blocked_dirs: Set of blocked directory prefixes
        allow_hidden: Whether to allow hidden files
        allowed_hidden_files: Set of allowed hidden filenames (e.g., {".gitignore"})
        allow_absolute: Allow absolute paths (for trusted paths like /nix/store/*)

    Returns:
        Tuple of (is_safe, error_message)
    """
    if project_root is None:
        project_root = Path.cwd()

    if blocked_dirs is None:
        blocked_dirs = {"/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/"}

    if allowed_hidden_files is None:
        allowed_hidden_files = set()

    # Check for absolute paths
    if path.startswith("/"):
        # Allow trusted absolute paths (e.g., /nix/store/*)
        if allow_absolute or any(path.startswith(trusted) for trusted in _TRUSTED_ABSOLUTE_PATHS):
            return True, ""
        return False, "Absolute paths are not allowed."

    # Check for path traversal
    if ".." in path:
        return False, "Parent directory traversal is not allowed."

    # Check hidden files
    filename = Path(path).name
    if filename.startswith("."):
        if not allow_hidden:
            if filename not in allowed_hidden_files:
                return False, f"Hidden file '{filename}' is not allowed."

    # Check for blocked directories
    for blocked in blocked_dirs:
        if path.startswith(blocked):
            return False, f"Blocked path: {blocked}"

    # Resolve and check if within project
    try:
        full_path = (project_root / path).resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            return False, "Path is outside the project directory"
    except Exception as e:
        return False, f"Error resolving path: {e}"

    return True, ""


def is_safe_command(
    command: str, allowed_commands: dict[str, list[str]] | None = None
) -> tuple[bool, str]:
    """Check if a command is allowed.

    Args:
        command: Command to check
        allowed_commands: Dict of allowed commands

    Returns:
        Tuple of (is_safe, error_message)
    """
    if allowed_commands is None:
        allowed_commands = {}

    if not allowed_commands:
        # Default: only allow well-known safe commands
        allowed_commands = {
            "just": [],
            "nix": [],
            "git": [],
            "echo": [],
            "cat": [],
            "head": [],
            "tail": [],
        }

    if command not in allowed_commands:
        return False, f"Command '{command}' is not in the whitelist"

    return True, ""


__all__ = ["is_safe_path", "is_safe_command"]
