"""
git/scripts/branch.py - Git branch operations
"""

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def list_branches() -> str:
    """List all git branches."""
    return _run(["git", "branch", "-a"])


def current_branch() -> str:
    """Get current branch name."""
    return _run(["git", "branch", "--show-current"]) or "detached"


def create_branch(branch_name: str, checkout: bool = True) -> str:
    """Create a new branch."""
    if checkout:
        return _run(["git", "checkout", "-b", branch_name])
    return _run(["git", "branch", branch_name])


def delete_branch(branch_name: str, force: bool = False) -> str:
    """Delete a branch."""
    cmd = ["git", "branch"]
    if force:
        cmd.append("-D")
    else:
        cmd.append("-d")
    cmd.append(branch_name)
    return _run(cmd)
