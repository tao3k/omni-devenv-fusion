"""Common path filtering utilities for sync operations.

Provides standardized functions to skip hidden files and directories
across all sync-related operations.

Usage:
    from omni.foundation.runtime.path_filter import should_skip_path, SKIP_DIRS

    # Check if a path should be skipped
    if should_skip_path(path):
        continue

    # Use in file discovery
    for f in directory.rglob("*.py"):
        if should_skip_path(f):
            continue
"""

from pathlib import Path
from typing import Set


# Standard directories to skip in all sync operations
SKIP_DIRS: frozenset[str] = frozenset(
    {
        # Python
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        ".nox",
        "site-packages",
        "Lib",
        # JavaScript/Node
        "node_modules",
        ".npm",
        ".yarn",
        ".pnpm-store",
        # Version control
        ".git",
        ".svn",
        ".hg",
        # Build/Cache
        ".cache",
        "target",
        "build",
        "dist",
        "out",
        ".gradle",
        ".idea",
        ".vscode",
        # Package managers
        "vendor",
        "bower_components",
        # Testing
        ".nyc_output",
        "coverage",
        ".coverage",
        # Other
        ".DS_Store",
        "Thumbs.db",
    }
)


def should_skip_path(
    path: Path,
    *,
    skip_hidden: bool = True,
    skip_dirs: Set[str] | frozenset[str] | None = None,
) -> bool:
    """Check if a path should be skipped based on hidden files/dirs and skip names.

    Args:
        path: The path to check
        skip_hidden: Whether to skip hidden files/directories (starting with '.')
        skip_dirs: Additional directory names to skip (merged with SKIP_DIRS)

    Returns:
        True if the path should be skipped
    """
    if skip_hidden:
        # Skip if any part starts with '.' (hidden files/dirs)
        if any(part.startswith(".") for part in path.parts):
            return True

    skip_set = skip_dirs or SKIP_DIRS
    if skip_set:
        # Skip if any part matches skip directories
        if any(part in skip_set for part in path.parts):
            return True

    return False


__all__ = [
    "should_skip_path",
    "SKIP_DIRS",
]
