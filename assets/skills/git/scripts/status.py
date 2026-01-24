"""
Git Status Command (Modernized)

Demonstrates:
1. @skill_command with autowire=True
2. Dependency Injection (Settings, ConfigPaths)
3. Input Schema hiding (Internal deps are not shown to LLM)
4. Robust Error Handling with CommandResult
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

# Modern Foundation API
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.settings import Settings

logger = get_logger("skill.git")


def _run_git(cmd: list[str], cwd: Path) -> tuple[str, int]:
    """Execute a git command and return output and returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.returncode


@skill_command(
    name="status",
    category="read",
    description="""
    Get detailed status of the git repository including branch, clean/dirty state, and change counts.

    Args:
        - repo_path: Optional[str] - Path to the repository (defaults to project root)

    Returns:
        Dictionary with success, repo_path, branch, is_clean, staged, unstaged, untracked counts.
    """,
    autowire=True,
)
def git_status(
    repo_path: str | None = None,
    # Injected dependencies (Hidden from JSON Schema)
    settings: Settings | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Execute git status on the target repository.

    Args:
        repo_path: Optional path to repo. Defaults to project root.
    """
    # 1. Resolve Target Path (Layer 1 Semantic)
    if paths is None:
        paths = ConfigPaths()
    target_path = Path(repo_path) if repo_path else paths.project_root

    if not target_path.exists():
        return {"success": False, "error": f"Path does not exist: {target_path}"}

    # 2. Resolve Git Executable (Layer 0 Config)
    if settings is None:
        settings = Settings()
    git_exec = settings.get("tools.git.executable", "git")

    # Validation
    if not shutil.which(git_exec):
        return {
            "success": False,
            "error": f"Git executable '{git_exec}' not found. Please install git or check settings.",
        }

    try:
        # 3. Execute Logic
        branch, _ = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], target_path)
        status_output, rc = _run_git(["git", "status", "--porcelain"], target_path)

        lines = status_output.strip().split("\n") if status_output.strip() else []
        is_clean = len(lines) == 0

        logger.debug(f"Git status checked for {target_path}: {'Clean' if is_clean else 'Dirty'}")

        return {
            "success": True,
            "repo_path": str(target_path),
            "branch": branch or "unknown",
            "is_clean": is_clean,
            "staged": sum(1 for l in lines if l.startswith("A ") or l.startswith("M ")),
            "unstaged": sum(1 for l in lines if l.startswith(" M") and not l.startswith("??")),
            "untracked": sum(1 for l in lines if l.startswith("??")),
            "backend": "shell",
        }

    except Exception as e:
        logger.exception("Unexpected error in git_status")
        return {"success": False, "error": str(e)}


@skill_command(
    name="status_short",
    category="view",
    description="""
    Get a short one-line summary of git status with branch and change counts.

    Args:
        - repo_path: Optional[str] - Path to the repository (defaults to project root)

    Returns:
        String summary like "Branch: main | Clean" or "Branch: main | Staged: 2 | Unstaged: 3".
    """,
    autowire=True,
)
def git_status_short(
    repo_path: str | None = None,
    settings: Settings | None = None,
    paths: ConfigPaths | None = None,
) -> str:
    """Get a short git status summary string."""
    result = git_status(repo_path=repo_path, settings=settings, paths=paths)

    if not result.get("success"):
        return f"Error: {result.get('error', 'Unknown error')}"

    branch = result.get("branch", "unknown")
    if result.get("is_clean"):
        return f"Branch: {branch} | Clean"
    return (
        f"Branch: {branch} | "
        f"Staged: {result.get('staged', 0)} | "
        f"Unstaged: {result.get('unstaged', 0)} | "
        f"Untracked: {result.get('untracked', 0)}"
    )


# Backward compatibility aliases
def git_status_detailed(
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Get detailed git status as a dictionary (legacy interface)."""
    return git_status(repo_path=str(project_root) if project_root else None)


def current_branch(
    project_root: Path | None = None,
) -> str:
    """Get current branch name (legacy interface)."""
    path = project_root or ConfigPaths().project_root
    branch, rc = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
    return branch if rc == 0 else ""


def has_staged_files(
    project_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """Check if there are staged files (legacy interface)."""
    path = project_root or ConfigPaths().project_root
    staged, rc = _run_git(["git", "diff", "--cached", "--name-only"], path)
    if rc == 0 and staged:
        return True, staged.split("\n")
    return False, []


def has_unstaged_files(
    project_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """Check if there are unstaged modifications (legacy interface)."""
    path = project_root or ConfigPaths().project_root
    unstaged, rc = _run_git(["git", "diff", "--name-only"], path)
    if rc == 0 and unstaged:
        return True, unstaged.split("\n")
    return False, []


__all__ = [
    "current_branch",
    "git_status",
    "git_status_detailed",
    "git_status_short",
    "has_staged_files",
    "has_unstaged_files",
    "status",  # Alias for backwards compatibility
]

# Alias for backwards compatibility
status = git_status
