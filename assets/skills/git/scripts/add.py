"""
git/scripts/add.py - Git add/stage operations
"""

import subprocess
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def add(files: list[str]) -> str:
    """Stage files for commit."""
    return _run(["git", "add"] + files)


def add_all() -> str:
    """Stage all changes."""
    return _run(["git", "add", "."])


def add_all_with_info() -> dict[str, Any]:
    """Stage all changes and return file list and diff.

    Returns:
        Dict with 'staged_files' list and 'diff' string.
    """
    root = Path.cwd()
    _run(["git", "add", "."], cwd=root)

    # Get staged files
    files_out, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    staged_files = [line for line in files_out.splitlines() if line.strip()]

    # Get diff content (full)
    diff_out, _, _ = _run(["git", "--no-pager", "diff", "--cached"], cwd=root)

    return {
        "staged_files": staged_files,
        "diff": diff_out,
    }


def add_pattern(pattern: str) -> str:
    """Stage files matching a pattern."""
    return _run(["git", "add", pattern])


def reset(files: list[str]) -> str:
    """Unstage files."""
    return _run(["git", "reset"] + files)


def reset_all() -> str:
    """Unstage all files."""
    return _run(["git", "reset"])


def reset_soft(commit: str = "HEAD") -> str:
    """Soft reset to a commit."""
    return _run(["git", "reset", "--soft", commit])


# test
