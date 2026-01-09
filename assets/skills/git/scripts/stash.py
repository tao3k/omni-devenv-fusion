"""
git/scripts/stash.py - Git stash operations
"""

import subprocess
from typing import Optional
from pathlib import Path


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def stash_save(msg: Optional[str] = None) -> str:
    """Stash working directory changes."""
    cmd = ["git", "stash", "push"]
    if msg:
        cmd.extend(["-m", msg])
    return _run(cmd)


def stash_pop() -> str:
    """Apply and remove last stash."""
    return _run(["git", "stash", "pop"])


def stash_list() -> str:
    """List all stashes."""
    return _run(["git", "stash", "list"])


def stash_drop(index: int = 0) -> str:
    """Drop a specific stash."""
    return _run(["git", "stash", "drop", f"stash@{index}"])


def stash_show(index: int = 0) -> str:
    """Show stash contents."""
    return _run(["git", "stash", "show", f"stash@{index}"])
