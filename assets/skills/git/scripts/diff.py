"""
git/scripts/diff.py - Git diff operations
"""

import subprocess
from typing import Optional
from pathlib import Path


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def get_diff(staged: bool = False, filename: Optional[str] = None) -> str:
    """Show working directory or staged changes."""
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    if filename:
        cmd.append(filename)
    return _run(cmd)


def get_diff_stat(staged: bool = False) -> str:
    """Show diff statistics."""
    cmd = ["git", "diff", "--stat"]
    if staged:
        cmd.append("--staged")
    return _run(cmd)


def get_staged_diff() -> str:
    """Get all staged changes."""
    return _run(["git", "diff", "--cached"])


def get_staged_diff_stat() -> str:
    """Get staged diff statistics."""
    return _run(["git", "diff", "--cached", "--stat"])
