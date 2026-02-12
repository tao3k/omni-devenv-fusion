# config/directory.py
"""
Configuration Directory Management

Canonical configuration directory helpers built on PRJ dirs.

Usage:
    from omni.foundation.config.directory import get_conf_dir, set_conf_dir
"""

from __future__ import annotations

import os

from .dirs import PRJ_DIRS


def set_conf_dir(path: str) -> None:
    """
    Set the configuration directory.

    Args:
        path: Path to configuration directory (e.g., "./agent")
    """
    os.environ["PRJ_CONFIG_HOME"] = path
    PRJ_DIRS.clear_cache()


def get_conf_dir() -> str:
    """
    Get the configuration directory.

    Returns:
        Configuration directory path
    """
    return str(PRJ_DIRS.config_home / "omni-dev-fusion")


__all__ = [
    "get_conf_dir",
    "set_conf_dir",
]
