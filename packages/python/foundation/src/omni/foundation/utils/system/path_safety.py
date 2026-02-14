"""
utils/path_safety.py
Path safety utilities.

Protocol-based design.

Provides path safety checking for file operations.
"""

from __future__ import annotations

from pathlib import Path

# Trusted read-only paths (Nix store paths are immutable and safe)
_TRUSTED_ABSOLUTE_PATHS = {"/nix/store/"}


def _default_project_root() -> Path:
    """Project root from git top level; fallback to cwd when not in a repo."""
    try:
        from omni.foundation.runtime.gitops import get_project_root

        return get_project_root()
    except Exception:
        return Path.cwd()


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
        allow_absolute: Allow absolute paths (only /nix/store/* are trusted)

    Returns:
        Tuple of (is_safe, error_message)
    """
    if project_root is None:
        project_root = _default_project_root()

    if blocked_dirs is None:
        blocked_dirs = {"/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/"}

    if allowed_hidden_files is None:
        allowed_hidden_files = set()

    # Check for absolute paths
    if path.startswith("/"):
        # Allow trusted absolute paths (e.g., /nix/store/*)
        if any(path.startswith(trusted) for trusted in _TRUSTED_ABSOLUTE_PATHS):
            return True, ""

        # Other absolute paths require allow_absolute flag
        if not allow_absolute:
            return False, "Absolute paths are not allowed."

        # Convert project-relative absolute paths to relative paths
        if project_root:
            try:
                resolved = Path(path).resolve()
                project_resolved = project_root.resolve()
                if str(resolved).startswith(str(project_resolved)):
                    # Convert to relative path and continue checking
                    path = str(resolved.relative_to(project_resolved))
                else:
                    return False, "Absolute path is outside the project directory"
            except Exception as e:
                return False, f"Error resolving path: {e}"
        else:
            return False, "Absolute paths require a project root to validate"

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


def resolve_project_path(path: str, project_root: Path | None = None) -> str:
    """
    Resolve a path to be relative to project root.

    If path is absolute and within project_root, returns relative path.
    If path is already relative, returns as-is.
    If path is absolute but outside project, returns original path.

    Args:
        path: Path to resolve (absolute or relative)
        project_root: Project root directory (defaults to git top level / cwd)

    Returns:
        Resolved path (relative to project root if possible)
    """
    if project_root is None:
        project_root = _default_project_root()

    path_obj = Path(path)

    # Already relative - return as-is
    if not path_obj.is_absolute():
        return str(path_obj)

    # Check if path is within project
    try:
        resolved = path_obj.resolve()
        project_resolved = project_root.resolve()

        if str(resolved).startswith(str(project_resolved)):
            # Return relative path
            return str(resolved.relative_to(project_resolved))
    except Exception:
        pass

    # Outside project or error - return original
    return str(path_obj)


def get_relative_path(absolute_path: str, project_root: Path | None = None) -> str:
    """
    Convert an absolute path to a relative path from project root.

    Args:
        absolute_path: Absolute path to convert
        project_root: Project root directory (defaults to cwd)

    Returns:
        Relative path from project root, or original if not under project
    """
    return resolve_project_path(absolute_path, project_root)


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


__all__ = [
    "get_relative_path",
    "is_safe_command",
    "is_safe_path",
    "normalize_path",
    "resolve_project_path",
]


def normalize_path(
    path: str,
    project_root: Path | None = None,
    blocked_dirs: set[str] | None = None,
    allow_hidden: bool = True,
    allowed_hidden_files: set[str] | None = None,
) -> tuple[bool, str, str]:
    """Check if a path is safe and convert absolute paths to relative.

    This is like is_safe_path but also:
    - Converts /nix/store/* paths to themselves (trusted)
    - Converts other absolute paths within project to relative paths
    - Returns the normalized (possibly converted) path

    Args:
        path: Path to check
        project_root: Project root directory (defaults to cwd)
        blocked_dirs: Set of blocked directory prefixes
        allow_hidden: Whether to allow hidden files
        allowed_hidden_files: Set of allowed hidden filenames

    Returns:
        Tuple of (is_safe, error_message, normalized_path)
        - normalized_path: The path after normalization (relative for project paths)
    """
    if project_root is None:
        project_root = _default_project_root()

    if blocked_dirs is None:
        blocked_dirs = {"/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/"}

    if allowed_hidden_files is None:
        allowed_hidden_files = set()

    normalized_path = path
    project_resolved = project_root.resolve()

    # Check for absolute paths
    if path.startswith("/"):
        # Allow trusted absolute paths (e.g., /nix/store/*)
        if any(path.startswith(trusted) for trusted in _TRUSTED_ABSOLUTE_PATHS):
            return True, "", path

        # Convert project-relative absolute paths to relative paths
        try:
            resolved = Path(path).resolve()
            if str(resolved).startswith(str(project_resolved)):
                normalized_path = str(resolved.relative_to(project_resolved))
            else:
                return False, "Absolute path is outside the project directory", path
        except Exception as e:
            return False, f"Error resolving path: {e}", path

    # Check for path traversal
    if ".." in normalized_path:
        return False, "Parent directory traversal is not allowed.", normalized_path

    # Check hidden files
    filename = Path(normalized_path).name
    if filename.startswith("."):
        if not allow_hidden:
            if filename not in allowed_hidden_files:
                return False, f"Hidden file '{filename}' is not allowed.", normalized_path

    # Check for blocked directories
    for blocked in blocked_dirs:
        if normalized_path.startswith(blocked):
            return False, f"Blocked path: {blocked}", normalized_path

    # Resolve and check if within project
    try:
        full_path = (project_root / normalized_path).resolve()
        if not str(full_path).startswith(str(project_resolved)):
            return False, "Path is outside the project directory", normalized_path
    except Exception as e:
        return False, f"Error resolving path: {e}", normalized_path

    return True, "", normalized_path
