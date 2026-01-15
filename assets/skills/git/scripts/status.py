"""
git/scripts/status.py - Git status implementation

This is an isolated script module. It uses relative imports to access
shared utilities within the git/scripts/ namespace.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from agent.skills.decorators import skill_script


def _run(cmd: list[str], cwd: Optional[Path] = None) -> Tuple[str, int]:
    """Execute a git command and return output and returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.returncode


@skill_script(
    name="status",
    description="Check git status in project directory. Returns short status format.",
)
def status(project_root: Path = None) -> str:
    """Check git status in project directory."""
    return _run(["git", "status", "--short"], cwd=project_root)[0] or "Clean working tree"


@skill_script(name="git_status_detailed", description="Get detailed git status with full output.")
def git_status_detailed(project_root: Path = None) -> str:
    """Get detailed git status."""
    return _run(["git", "status"], cwd=project_root)[0]


@skill_script(name="git_current_branch", description="Get the current branch name.")
def current_branch(project_root: Path = None) -> str:
    """Get current branch name."""
    branch, rc = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    return branch if rc == 0 else ""


@skill_script(
    name="git_has_staged", description="Check if there are staged files and return their names."
)
def has_staged_files(project_root: Path = None) -> tuple[bool, list[str]]:
    """Check if there are staged files."""
    staged, rc = _run(["git", "diff", "--cached", "--name-only"], cwd=project_root)
    if rc == 0 and staged:
        return True, staged.split("\n")
    return False, []


@skill_script(
    name="git_has_unstaged", description="Check if there are unstaged files and return their names."
)
def has_unstaged_files(project_root: Path = None) -> tuple[bool, list[str]]:
    """Check if there are unstaged files."""
    unstaged, rc = _run(["git", "diff", "--name-only"], cwd=project_root)
    if rc == 0 and unstaged:
        return True, unstaged.split("\n")
    return False, []
