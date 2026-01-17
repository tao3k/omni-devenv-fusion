"""
git/scripts/commit.py - Git commit operations

Write commands (commit, amend, revert) use @skill_command.
Read commands (get_last_commit, get_last_commit_msg) are simple wrappers.
"""

import subprocess
from pathlib import Path
from typing import Optional

from agent.skills.decorators import skill_command


def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[str, str, int]:
    """Run command and return stdout, stderr, returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


@skill_command(
    name="git_commit",
    category="write",
    description="""
    Commits staged changes with a message.

    Re-stages all modified files before committing to handle lefthook reformatting.
    Skips pre-commit hooks (use git_commit for hook execution).

    Args:
        message: The commit message for the changes.
        project_root: The project root directory. Auto-injected if not provided.

    Returns:
        Success or failure message with commit hash.

    Example:
        @omni("git.git_commit", {"message": "feat(core): add new feature"})
    """,
)
def commit(message: str, project_root: Optional[Path] = None) -> str:
    _run(["git", "add", "-u"], cwd=project_root)

    stdout, stderr, rc = _run(["git", "commit", "-m", message], cwd=project_root)
    if rc == 0:
        return "Commit created successfully"
    return f"Commit failed: {stdout} {stderr}"


@skill_command(
    name="git_commit_amend",
    category="write",
    description="""
    Amends the previous commit with a new message.

    Modifies the most recent commit without changing its content.
    Does not run pre-commit hooks.

    Args:
        message: The new commit message to replace the previous one.
        project_root: The project root directory. Auto-injected if not provided.

    Returns:
        Success or failure message.
    """,
)
def commit_with_amend(message: str, project_root: Optional[Path] = None) -> str:
    stdout, stderr, rc = _run(["git", "commit", "--amend", "-m", message], cwd=project_root)
    if rc == 0:
        return "Commit amended successfully"
    return f"Amend failed: {stdout} {stderr}"


@skill_command(
    name="git_commit_no_verify",
    category="write",
    description="""
    Commits staged changes without running pre-commit hooks.

    Bypasses git hooks (lefthook, etc.) for faster commits.
    Use with caution - skips code quality checks.

    Args:
        message: The commit message for the changes.
        project_root: The project root directory. Auto-injected if not provided.

    Returns:
        Success or failure message.
    """,
)
def commit_no_verify(message: str, project_root: Optional[Path] = None) -> str:
    stdout, stderr, rc = _run(["git", "commit", "--no-verify", "-m", message], cwd=project_root)
    if rc == 0:
        return "Commit created (no-verify)"
    return f"Commit failed: {stdout} {stderr}"


def get_last_commit(project_root: Optional[Path] = None) -> str:
    """Retrieves the hash of the most recent commit."""
    stdout, _, rc = _run(["git", "rev-parse", "HEAD"], cwd=project_root)
    return stdout if rc == 0 else ""


def get_last_commit_msg(project_root: Optional[Path] = None) -> str:
    """Retrieves the message of the most recent commit."""
    stdout, _, _ = _run(["git", "log", "-1", "--pretty=%B"], cwd=project_root)
    return stdout


@skill_command(
    name="git_revert",
    category="write",
    description="""
    Reverts a specific commit by creating a new reverse commit.

    Creates a new commit that undoes the changes from the specified commit.

    Args:
        commit: The commit hash or reference to revert (e.g., `HEAD~1`, `abc1234`).
        no_commit: If `true`, stages the revert but does not commit.
                   Defaults to `false`.
        project_root: The project root directory. Auto-injected if not provided.

    Returns:
        Success or failure message.
    """,
)
def revert(commit: str, no_commit: bool = False, project_root: Optional[Path] = None) -> str:
    cmd = ["git", "revert"]
    if no_commit:
        cmd.append("--no-commit")
    cmd.append(commit)
    stdout, stderr, rc = _run(cmd, cwd=project_root)
    if rc == 0:
        return "Revert initiated successfully"
    return f"Revert failed: {stdout} {stderr}"
