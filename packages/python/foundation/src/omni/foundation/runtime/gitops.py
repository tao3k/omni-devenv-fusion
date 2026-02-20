"""
common/gitops.py
Lightweight GitOps - Project Path Detection (Infrastructure Layer).

This is a standalone module that can be imported without loading
the entire common.mcp_core package.

Usage:
    from omni.foundation.runtime.gitops import get_project_root

    root = get_project_root()
"""

import os
import subprocess
from pathlib import Path

# Cache for project root (singleton pattern) - module level cache
_project_root: Path | None = None
_project_root_searched: bool = False  # Flag to avoid repeated searches


def _is_project_root(path: Path) -> bool:
    """Check if path is a project root (non-git method)."""
    indicators = [".git", "justfile", "pyproject.toml", "package.json", "go.mod", "Cargo.toml"]
    return any((path / indicator).exists() for indicator in indicators)


def clear_project_root_cache() -> None:
    """Clear the project root cache. Useful for testing."""
    global _project_root, _project_root_searched
    _project_root = None
    _project_root_searched = False


def get_project_root() -> Path:
    """
    Get the project root directory (GitOps: must run from inside the git repo).

    Priority:
    1. PRJ_ROOT environment variable
    2. git rev-parse --show-toplevel (from cwd; any subdir in repo returns same toplevel)

    No fallback: project is required to live in a git repository.
    """
    global _project_root, _project_root_searched

    if _project_root is not None:
        return _project_root

    if _project_root_searched:
        raise RuntimeError(
            "CRITICAL: Cannot determine project root. Set PRJ_ROOT or run from inside the git repo."
        )

    _project_root_searched = True

    prj_root = os.environ.get("PRJ_ROOT")
    if prj_root:
        _project_root = Path(prj_root).resolve()
        return _project_root

    try:
        result = subprocess.run(
            ["git", "-C", str(Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            _project_root = Path(result.stdout.strip()).resolve()
            return _project_root
    except (subprocess.TimeoutExpired, Exception):
        pass

    raise RuntimeError(
        "CRITICAL: Not in a git repository. Run 'omni' from inside the repo or set PRJ_ROOT."
    )


def get_git_toplevel(cwd: Path | None = None) -> Path:
    """Resolve git top-level directory from cwd, ignoring PRJ_ROOT."""
    start = (cwd or Path.cwd()).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, Exception) as e:
        raise RuntimeError(f"CRITICAL: Failed to resolve git top-level from {start}: {e}") from e

    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()

    stderr = (result.stderr or "").strip()
    raise RuntimeError(
        f"CRITICAL: Not in a git repository. Cannot resolve git top-level from {start}. {stderr}"
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
    """Check if the given path appears to be a project root (non-git method)."""
    if path is None:
        path = Path.cwd()
    return _is_project_root(path)


# =============================================================================
# Project Paths Helper
# =============================================================================


class ProjectPaths:
    """Convenience class for accessing project package paths.

    Usage:
        from omni.foundation.runtime.gitops import PROJECT

        agent_src = PROJECT.agent.src      # packages/python/agent/src
        common_src = PROJECT.common.src    # packages/python/common/src
        agent_pkg = PROJECT.agent          # packages/python/agent
        common_pkg = PROJECT.common        # packages/python/common

        # Add to sys.path
        PROJECT.add_to_path("agent", "common")
    """

    def __init__(self, project_root: Path | None = None):
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
    def core_src(self) -> Path:
        """Path to omni.core source directory."""
        return self.project_root / "packages/python/core/src"

    @property
    def foundation_src(self) -> Path:
        """Path to omni.foundation source directory."""
        return self.project_root / "packages/python/foundation/src"

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
