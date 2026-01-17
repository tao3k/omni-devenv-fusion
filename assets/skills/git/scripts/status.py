"""
git/scripts/status.py - Git status implementation

Simple wrappers around native git commands (no skill_command decorator needed).
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


def _run(cmd: list[str], cwd: Optional[Path] = None) -> Tuple[str, int]:
    """Execute a git command and return output and returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.returncode


def status(project_root: Optional[Path] = None) -> str:
    """Checks the git status of the project directory."""
    return _run(["git", "status", "--short"], cwd=project_root)[0] or "Clean working tree"


def git_status_detailed(project_root: Optional[Path] = None) -> str:
    """Gets the full git status output."""
    return _run(["git", "status"], cwd=project_root)[0]


def current_branch(project_root: Optional[Path] = None) -> str:
    """Retrieves the current branch name."""
    branch, rc = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    return branch if rc == 0 else ""


def has_staged_files(project_root: Optional[Path] = None) -> tuple[bool, list[str]]:
    """Checks if there are any staged files."""
    staged, rc = _run(["git", "diff", "--cached", "--name-only"], cwd=project_root)
    if rc == 0 and staged:
        return True, staged.split("\n")
    return False, []


def has_unstaged_files(project_root: Optional[Path] = None) -> tuple[bool, list[str]]:
    """Checks if there are any unstaged modifications."""
    unstaged, rc = _run(["git", "diff", "--name-only"], cwd=project_root)
    if rc == 0 and unstaged:
        return True, unstaged.split("\n")
    return False, []
