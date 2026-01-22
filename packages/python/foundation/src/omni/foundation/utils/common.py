# lib.py -> common.py
"""
Library Utility - Replaces ugly Path(__file__).resolve().parents[N] patterns.

Usage:
    from omni.foundation.utils.common import common_src, agent_src, project_root

    common_src()     # Returns Path to packages/python/agent/src
    agent_src()      # Returns Path to packages/python/agent/src
    project_root()   # Returns Path to project root
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root() -> Path:
    """Get project root (where .git lives)."""
    # Import from gitops which already does this correctly
    try:
        from omni.foundation.runtime.gitops import get_project_root

        return get_project_root()
    except ImportError:
        # Fallback: find .git
        path = Path(__file__).resolve()
        for parent in path.parents:
            if (parent / ".git").exists():
                return parent
        return path.parent.parent.parent


@lru_cache(maxsize=1)
def common_src() -> Path:
    """Get common package src directory: packages/python/common/src"""
    return project_root() / "packages" / "python" / "common" / "src"


@lru_cache(maxsize=1)
def agent_src() -> Path:
    """Get agent package src directory: packages/python/agent/src"""
    return project_root() / "packages" / "python" / "agent" / "src"


def setup_import_paths() -> None:
    """
    Setup sys.path for common and agent packages.
    Call this at module import time to enable 'from omni.foundation.xxx import ...' imports.
    """
    import sys

    cs = common_src()
    asrc = agent_src()

    if str(cs) not in sys.path:
        sys.path.insert(0, str(cs))
    if str(asrc) not in sys.path:
        sys.path.insert(0, str(asrc))


# Auto-setup on import
setup_import_paths()


__all__ = [
    "project_root",
    "common_src",
    "agent_src",
    "setup_import_paths",
]
