"""
path.py - Path Manipulation Utilities

Provides safe sys.path manipulation utilities for dynamic module loading.

Python 3.12+ Features:
- Context manager for safe sys.path manipulation (Section 7.4)
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def temporary_sys_path(path: str | Path) -> Iterator[None]:
    """Safely append path to sys.path and restore it afterwards.

    This context manager ensures that sys.path is restored to its original
    state even if an exception occurs during the context.

    Usage:
        >>> with temporary_sys_path("/some/path"):
        ...     import mymodule
        ...     mymodule.do_something()

    Args:
        path: Path to temporarily add to sys.path

    Example:
        # Loading a module from a specific directory
        with temporary_sys_path("/path/to/custom/modules"):
            import custom_module
    """
    path_str = str(path)
    added = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        added = True
    try:
        yield
    finally:
        if added and path_str in sys.path:
            sys.path.remove(path_str)


__all__ = ["temporary_sys_path"]
