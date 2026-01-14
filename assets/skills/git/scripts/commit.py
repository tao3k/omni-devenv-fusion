"""
git/scripts/commit.py - Git commit operations

This is the CONTROLLER layer - contains all commit logic.
tools.py is the ROUTER layer - only dispatches to this module.
"""

import subprocess
from pathlib import Path
from typing import Optional

from agent.skills.decorators import skill_script


def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[str, str, int]:
    """Run command and return stdout, stderr, returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


@skill_script(
    name="git_commit",
    description="Commit staged changes with a message.",
)
def commit(message: str, project_root: Path = None) -> str:
    """Commit staged changes."""
    stdout, stderr, rc = _run(["git", "commit", "-m", message], cwd=project_root)
    if rc == 0:
        return f"✅ Commit created successfully"
    return f"❌ Commit failed: {stdout} {stderr}"


@skill_script(
    name="git_commit_amend",
    description="Amend the previous commit with a new message.",
)
def commit_with_amend(message: str, project_root: Path = None) -> str:
    """Amend the previous commit with a new message."""
    stdout, stderr, rc = _run(["git", "commit", "--amend", "-m", message], cwd=project_root)
    if rc == 0:
        return f"✅ Commit amended successfully"
    return f"❌ Amend failed: {stdout} {stderr}"


@skill_script(
    name="git_commit_no_verify",
    description="Commit without pre-commit hooks.",
)
def commit_no_verify(message: str, project_root: Path = None) -> str:
    """Commit without pre-commit hooks."""
    stdout, stderr, rc = _run(["git", "commit", "--no-verify", "-m", message], cwd=project_root)
    if rc == 0:
        return f"✅ Commit created (no-verify)"
    return f"❌ Commit failed: {stdout} {stderr}"


@skill_script(
    name="git_last_commit",
    description="Get the last commit hash.",
)
def get_last_commit(project_root: Path = None) -> str:
    """Get the last commit hash."""
    stdout, _, rc = _run(["git", "rev-parse", "HEAD"], cwd=project_root)
    return stdout if rc == 0 else ""


@skill_script(
    name="git_last_commit_msg",
    description="Get the last commit message.",
)
def get_last_commit_msg(project_root: Path = None) -> str:
    """Get the last commit message."""
    stdout, _, _ = _run(["git", "log", "-1", "--pretty=%B"], cwd=project_root)
    return stdout


@skill_script(
    name="git_revert",
    description="Revert a specific commit.",
)
def revert(commit: str, no_commit: bool = False, project_root: Path = None) -> str:
    """Revert a specific commit."""
    cmd = ["git", "revert"]
    if no_commit:
        cmd.append("--no-commit")
    cmd.append(commit)
    stdout, stderr, rc = _run(cmd, cwd=project_root)
    if rc == 0:
        return f"✅ Revert initiated successfully"
    return f"❌ Revert failed: {stdout} {stderr}"
