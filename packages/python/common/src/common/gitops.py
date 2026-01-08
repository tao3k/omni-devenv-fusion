"""
common/gitops.py
Lightweight GitOps - Project Path Detection (Infrastructure Layer).

This is a standalone module that can be imported without loading
the entire common.mcp_core package.

Usage:
    from common.gitops import get_project_root

    root = get_project_root()
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

# Cache for project root (singleton pattern)
_project_root: Optional[Path] = None


def get_project_root() -> Path:
    """
    Get the project root directory using GitOps.

    Priority:
    1. PRJ_ROOT environment variable
    2. Git toplevel (git rev-parse --show-toplevel)
    3. Fallback: Current directory if it contains .git

    Returns:
        Path to project root
    """
    global _project_root

    if _project_root is not None:
        return _project_root

    # Method 1: PRJ_ROOT environment variable
    prj_root = os.environ.get("PRJ_ROOT")
    if prj_root:
        _project_root = Path(prj_root)
        return _project_root

    # Method 2: Git toplevel (Primary - GitOps)
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

    # Method 3: Current working directory as fallback (must have .git)
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        _project_root = cwd
        return _project_root

    # Should never reach here in production
    raise RuntimeError(
        "CRITICAL: Cannot determine project root. "
        "Not in a git repository and no fallback available. "
        f"Current working directory: {Path.cwd()}"
    )


def get_spec_dir() -> Path:
    """Get the directory containing feature specs."""
    return get_project_root() / "agent" / "specs"


def get_instructions_dir() -> Path:
    """Get the agent/instructions directory."""
    return get_project_root() / "agent" / "instructions"


def get_docs_dir() -> Path:
    """Get the docs directory."""
    return get_project_root() / "docs"


def get_agent_dir() -> Path:
    """Get the agent directory."""
    return get_project_root() / "agent"


def get_src_dir() -> Path:
    """Get the src directory."""
    return get_project_root() / "src"


def is_git_repo(path: Path | None = None) -> bool:
    """Check if the given path is inside a git repository."""
    if path is None:
        path = Path.cwd()
    return (path / ".git").exists() or any(
        (path / ".git" / d).exists() for d in ["modules", "worktrees"]
    )


def is_project_root(path: Path | None = None) -> bool:
    """Check if the given path appears to be a project root."""
    if path is None:
        path = Path.cwd()
    # Project root indicators
    indicators = [
        ".git",
        "justfile",
        "pyproject.toml",
        "package.json",
        "go.mod",
        "Cargo.toml",
    ]
    return any((path / indicator).exists() for indicator in indicators)


# =============================================================================
# Project Paths Helper (Phase 32)
# =============================================================================


class ProjectPaths:
    """Convenience class for accessing project package paths.

    Usage:
        from common.gitops import PROJECT

        agent_src = PROJECT.agent.src      # packages/python/agent/src
        common_src = PROJECT.common.src    # packages/python/common/src
        agent_pkg = PROJECT.agent          # packages/python/agent
        common_pkg = PROJECT.common        # packages/python/common

        # Add to sys.path
        PROJECT.add_to_path("agent", "common")
    """

    def __init__(self, project_root: Optional[Path] = None):
        self._root = project_root or get_project_root()
        self._packages = self._root / "packages" / "python"

    @property
    def project_root(self) -> Path:
        return self._root

    @property
    def packages(self) -> Path:
        return self._packages

    @property
    def agent(self) -> Path:
        return self._packages / "agent"

    @property
    def common(self) -> Path:
        return self._packages / "common"

    @property
    def agent_src(self) -> Path:
        return self.agent / "src"

    @property
    def common_src(self) -> Path:
        return self.common / "src"

    def __getattr__(self, name: str) -> Path:
        """Access package directories via attributes."""
        pkg_path = self._packages / name
        if pkg_path.exists():
            return pkg_path
        raise AttributeError(f"Package '{name}' not found in packages/")

    def add_to_path(self, *paths: str) -> None:
        """Add project paths to sys.path."""
        import sys

        for path in paths:
            if path == "agent":
                sys.path.insert(0, str(self.agent_src))
            elif path == "common":
                sys.path.insert(0, str(self.common_src))


# Singleton instance for convenience
PROJECT = ProjectPaths()
