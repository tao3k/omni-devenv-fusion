"""
git/scripts/add.py - Git add/stage operations
"""

import subprocess
from typing import Optional, List
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
