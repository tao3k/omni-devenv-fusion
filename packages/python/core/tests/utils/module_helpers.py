"""
Module Loading and Cleanup Helpers.

This module provides utilities for loading modules in tests
and ensuring clean module state between tests.

Usage:
    from tests.utils.module_helpers import load_module_from_file, cleanup_module
"""

import importlib
import importlib.util
import sys
from pathlib import Path


def load_module_from_file(module_name: str, file_path: Path):
    """Load a Python module directly from a file path.

    Args:
        module_name: Unique name for the module
        file_path: Path to the .py file

    Returns:
        The loaded module

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Module file not found: {file_path}")

    # Clean up existing module if present
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def cleanup_module(module_name: str) -> None:
    """Remove a module from sys.modules if present.

    Args:
        module_name: Name of the module to remove
    """
    if module_name in sys.modules:
        del sys.modules[module_name]


def cleanup_modules(prefix: str) -> None:
    """Remove all modules with given prefix from sys.modules.

    Args:
        prefix: Module name prefix to match
    """
    modules_to_remove = [name for name in sys.modules if name.startswith(prefix)]
    for name in modules_to_remove:
        del sys.modules[name]


class ModuleCache:
    """Context manager for caching and restoring modules."""

    def __init__(self):
        self._cache: dict[str, object] = {}

    def __enter__(self):
        # Store current state of modules
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore cached modules
        for name, module in self._cache.items():
            sys.modules[name] = module
        return False

    def cache_module(self, module_name: str) -> None:
        """Cache a module if it exists in sys.modules."""
        if module_name in sys.modules:
            self._cache[module_name] = sys.modules[module_name]
            del sys.modules[module_name]
