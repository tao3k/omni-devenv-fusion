# common/mcp_core/gitops.py
"""
GitOps - Single Source of Truth for Project Path Management

This module provides GitOps-based utilities for project path detection
and management. All path detection in the project should use these functions.

Core Principles:
1. Git is the single source of truth for project structure
2. Deterministic, reproducible paths across environments
3. Fallback mechanisms for non-git environments (testing)

Reference: numtide/prj-spec conventions

Usage:
    from common.mcp_core.gitops import get_project_root, get_spec_dir

    root = get_project_root()
    spec_dir = get_spec_dir()

GitOps Utilities:
    - get_project_root(): Get project root from git toplevel
    - get_git_toplevel(): Direct git toplevel (legacy compatibility)
    - is_git_repo(): Check if path is a git repository
    - get_spec_dir(): Get agent/specs directory
    - get_instructions_dir(): Get agent/instructions directory
    - get_docs_dir(): Get docs directory
    - get_agent_dir(): Get agent directory
    - get_src_dir(): Get src directory
    - run_git_cmd(): Run git command (for commit/push only)
"""

import subprocess
from pathlib import Path
from typing import List, Optional

# Cache for project root (singleton pattern)
_project_root: Optional[Path] = None


def get_project_root() -> Path:
    """
    Get the project root directory using GitOps.

    This is THE single source of truth for project root detection.

    Priority:
    1. Git toplevel (git rev-parse --show-toplevel)
    2. Fallback: Module-based detection (for testing/non-git environments)

    Returns:
        Path to project root

    Raises:
        RuntimeError: If no valid project root can be determined
    """
    global _project_root

    if _project_root is not None:
        return _project_root

    # Method 1: Git toplevel (Primary - GitOps)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            _project_root = Path(result.stdout.strip())
            return _project_root
    except Exception:
        pass

    # Method 2: Current working directory as fallback
    cwd = Path.cwd()
    if (cwd / ".git").exists() or (cwd / "justfile").exists():
        _project_root = cwd
        return _project_root

    # Should never reach here in production
    raise RuntimeError(
        "CRITICAL: Cannot determine project root. "
        "Not in a git repository and no fallback available. "
        f"Current working directory: {Path.cwd()}"
    )


def get_spec_dir() -> Path:
    """
    Get the directory containing feature specs.

    Returns:
        Path to agent/specs/
    """
    return get_project_root() / "agent" / "specs"


def get_instructions_dir() -> Path:
    """
    Get the directory containing LLM instructions.

    Returns:
        Path to agent/instructions/
    """
    return get_project_root() / "agent" / "instructions"


def get_docs_dir() -> Path:
    """
    Get the directory containing documentation.

    Returns:
        Path to docs/
    """
    return get_project_root() / "docs"


def get_agent_dir() -> Path:
    """
    Get the agent directory.

    Returns:
        Path to agent/
    """
    return get_project_root() / "agent"


def get_src_dir() -> Path:
    """
    Get the source directory.

    Returns:
        Path to src/
    """
    return get_project_root() / "src"


def is_git_repo(path: Optional[Path] = None) -> bool:
    """
    Check if a path is a git repository.

    Args:
        path: Path to check (defaults to get_project_root())

    Returns:
        True if the path contains a .git directory
    """
    check_path = path or get_project_root()
    return (check_path / ".git").exists()


def reset_project_root():
    """
    Reset the cached project root (for testing purposes only).

    WARNING: Do not use this in production code.
    """
    global _project_root
    _project_root = None


def is_project_root(path: Path) -> bool:
    """
    Check if a path is the project root.

    Args:
        path: Path to check

    Returns:
        True if this appears to be the project root
    """
    return (
        (path / ".git").exists() or (path / "justfile").exists() or (path / "devenv.nix").exists()
    )


def get_git_toplevel() -> Optional[Path]:
    """
    Get git toplevel directory (legacy function, use get_project_root()).

    Returns:
        Path to git repository root or None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


async def run_git_cmd(args: List[str]) -> str:
    """
    Run a git command and return the output.

    Note: For safe read operations (status, diff, log), use Claude-native bash.
    This function is ONLY for critical operations (commit, push) via MCP.

    Args:
        args: Git command arguments (e.g., ["commit", "-m", "message"])

    Returns:
        Command output string

    Raises:
        Exception: If git command fails
    """
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    return result.stdout


__all__ = [
    "get_project_root",
    "get_spec_dir",
    "get_instructions_dir",
    "get_docs_dir",
    "get_agent_dir",
    "get_src_dir",
    "reset_project_root",
    "is_project_root",
    "is_git_repo",
    "get_git_toplevel",
    "run_git_cmd",
]
