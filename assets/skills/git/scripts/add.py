"""
git/scripts/add.py - Git add/stage operations
"""

import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def add(files: List[str]) -> str:
    """Stage files for commit."""
    return _run(["git", "add"] + files)


def add_all() -> str:
    """Stage all changes."""
    return _run(["git", "add", "."])


def add_all_with_info() -> Dict[str, Any]:
    """Stage all changes and return file list and diff.

    Returns:
        Dict with 'staged_files' list and 'diff' string.
    """
    root = Path.cwd()
    _run(["git", "add", "."], cwd=root)

    # Get staged files
    files_out, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    staged_files = [line for line in files_out.splitlines() if line.strip()]

    # Get diff content (truncated)
    diff_out, _, _ = _run(["git", "--no-pager", "diff", "--cached"], cwd=root)
    if len(diff_out) > 6000:
        diff_out = diff_out[:6000] + "\n... (Diff truncated)"

    return {
        "staged_files": staged_files,
        "diff": diff_out,
    }


def add_pattern(pattern: str) -> str:
    """Stage files matching a pattern."""
    return _run(["git", "add", pattern])


def reset(files: List[str]) -> str:
    """Unstage files."""
    return _run(["git", "reset"] + files)


def reset_all() -> str:
    """Unstage all files."""
    return _run(["git", "reset"])


def reset_soft(commit: str = "HEAD") -> str:
    """Soft reset to a commit."""
    return _run(["git", "reset", "--soft", commit])


# test
