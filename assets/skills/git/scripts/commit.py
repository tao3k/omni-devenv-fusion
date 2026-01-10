"""
git/scripts/commit.py - Git commit operations

This is the CONTROLLER layer - contains all commit logic.
tools.py is the ROUTER layer - only dispatches to this module.
"""

import subprocess
from typing import Optional
from pathlib import Path


def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[str, str, int]:
    """Run command and return stdout, stderr, returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def commit(message: str) -> str:
    """Commit staged changes."""
    stdout, stderr, rc = _run(["git", "commit", "-m", message])
    if rc == 0:
        return f"✅ Commit created successfully"
    return f"❌ Commit failed: {stdout} {stderr}"


def commit_with_amend(message: str) -> str:
    """Amend the previous commit with a new message."""
    stdout, stderr, rc = _run(["git", "commit", "--amend", "-m", message])
    if rc == 0:
        return f"✅ Commit amended successfully"
    return f"❌ Amend failed: {stdout} {stderr}"


def commit_no_verify(message: str) -> str:
    """Commit without pre-commit hooks."""
    stdout, stderr, rc = _run(["git", "commit", "--no-verify", "-m", message])
    if rc == 0:
        return f"✅ Commit created (no-verify)"
    return f"❌ Commit failed: {stdout} {stderr}"


def get_last_commit() -> str:
    """Get the last commit hash."""
    stdout, stderr, rc = _run(["git", "rev-parse", "HEAD"])
    return stdout


def get_last_commit_msg() -> str:
    """Get the last commit message."""
    stdout, stderr, rc = _run(["git", "log", "-1", "--pretty=%B"])
    return stdout


def revert(commit: str, no_commit: bool = False) -> str:
    """Revert a specific commit."""
    cmd = ["git", "revert"]
    if no_commit:
        cmd.append("--no-commit")
    cmd.append(commit)
    stdout, stderr, rc = _run(cmd)
    if rc == 0:
        return f"✅ Revert created"
    return f"❌ Revert failed: {stdout} {stderr}"
