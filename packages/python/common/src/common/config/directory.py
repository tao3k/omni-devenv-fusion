# config/directory.py
"""
Configuration Directory Management

Manages the configuration directory path with --conf flag support.

Phase 33: Modularized from settings.py

Usage:
    from common.config.directory import get_conf_dir, set_conf_dir
"""

from __future__ import annotations

import sys
import threading


# Global configuration directory (set by --conf flag)
_CONF_DIR: str | None = None
_conf_dir_lock = threading.Lock()


def set_conf_dir(path: str) -> None:
    """
    Set the configuration directory.

    Args:
        path: Path to configuration directory (e.g., "./agent")
    """
    global _CONF_DIR
    with _conf_dir_lock:
        _CONF_DIR = path


def get_conf_dir() -> str:
    """
    Get the configuration directory.

    Returns:
        Configuration directory path
    """
    global _CONF_DIR
    if _CONF_DIR is not None:
        return _CONF_DIR

    # Parse --conf from command line args
    args = sys.argv
    for i, arg in enumerate(args):
        if arg == "--conf" and i + 1 < len(args):
            _CONF_DIR = args[i + 1]
            return _CONF_DIR
        if arg.startswith("--conf="):
            _CONF_DIR = arg.split("=", 1)[1]
            return _CONF_DIR

    # Default to assets/
    _CONF_DIR = "assets"
    return _CONF_DIR


__all__ = [
    "set_conf_dir",
    "get_conf_dir",
]
