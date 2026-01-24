"""
loader.py - Modular Sniffer Loader

Scans assets/skills/<skill>/extensions/sniffer/ directory and loads
all sniffer functions marked with @sniffer decorator.

Supports multi-file structure:
    extensions/sniffer/
        __init__.py       (optional)
        venv_check.py     # @sniffer functions
        pyproject.py      # @sniffer functions
        runtime.py        # @sniffer functions

Python 3.12+ Features:
- pathlib.Path.walk() for recursive directory traversal (Section 7.1)
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Iterator

from omni.foundation.config.logging import get_logger

from .decorators import SnifferFunc

logger = get_logger("omni.core.ext.sniffer")


class SnifferLoader:
    """
    Load sniffer functions from extensions/sniffer/ directory.

    Features:
    - Scans all .py files in the directory
    - Auto-discovers @sniffer decorated functions
    - Sorts by priority (highest first)
    - Safe module loading with error handling
    """

    def __init__(self, sniffer_path: str | Path):
        """Initialize loader with path to sniffer directory.

        Args:
            sniffer_path: Path to extensions/sniffer/ directory
        """
        self.path = Path(sniffer_path)
        self._sniffers: list[SnifferFunc] = []
        self._loaded: bool = False

    @property
    def sniffers(self) -> list[SnifferFunc]:
        """Get loaded sniffer functions."""
        return self._sniffers

    def load_all(self) -> list[SnifferFunc]:
        """Load all sniffer functions from the directory.

        Returns:
            List of loaded SnifferFunc, sorted by priority (high to low)
        """
        if self._loaded:
            return self._sniffers

        self._sniffers = []
        self._loaded = True

        if not self.path.exists():
            logger.debug(f"Sniffer path does not exist: {self.path}")
            return self._sniffers

        if not self.path.is_dir():
            logger.warning(f"Sniffer path is not a directory: {self.path}")
            return self._sniffers

        # Add path to sys.path for imports (temporarily)
        path_str = str(self.path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

        try:
            # Method 1: Use Path.walk() (Python 3.12+)
            py_files = list(self.find_py_files(self.path))
            for py_file in sorted(py_files):
                self._load_module(py_file)

            # Sort by priority (highest first)
            self._sniffers.sort(key=lambda f: getattr(f, "_sniffer_priority", 100), reverse=True)

            if self._sniffers:
                logger.debug(f"Loaded {len(self._sniffers)} sniffers from {self.path}")

        finally:
            # Clean up sys.path
            if path_str in sys.path:
                sys.path.remove(path_str)

        return self._sniffers

    @staticmethod
    def find_py_files(root_path: Path) -> Iterator[Path]:
        """Find all Python files recursively using Path.walk() (Python 3.12+).

        Args:
            root_path: Root directory to search

        Yields:
            Path objects for each .py file found
        """
        for root, dirs, files in root_path.walk():
            # Prune unwanted directories in-place
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    yield root / file

    def _load_module(self, path: Path) -> None:
        """Load a single Python module and extract sniffer functions.

        Args:
            path: Path to the .py file
        """
        module_name = path.stem

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                logger.warning(f"Cannot load module spec: {path}")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find all @sniffer decorated functions
            sniffer_count = 0
            for attr_name in dir(module):
                try:
                    obj = getattr(module, attr_name)
                    if inspect.isfunction(obj) and getattr(obj, "_is_sniffer", False) is True:
                        self._sniffers.append(obj)
                        sniffer_name = getattr(obj, "_sniffer_name", attr_name)
                        logger.debug(
                            f"  👃 Loaded sniffer: {sniffer_name} (priority: {getattr(obj, '_sniffer_priority', 100)})"
                        )
                        sniffer_count += 1
                except Exception:
                    # Skip attributes that can't be inspected
                    continue

            if sniffer_count > 0:
                logger.debug(f"   Module {module_name}: {sniffer_count} sniffers loaded")

        except Exception as e:
            logger.error(f"   ❌ Failed to load sniffer module {module_name}: {e}")

    def get_by_name(self, name: str) -> SnifferFunc | None:
        """Get a sniffer function by name.

        Args:
            name: Sniffer name (from @sniffer(name="..."))

        Returns:
            SnifferFunc if found, None otherwise
        """
        for sniffer in self._sniffers:
            if getattr(sniffer, "_sniffer_name", None) == name:
                return sniffer
        return None

    def __len__(self) -> int:
        """Return number of loaded sniffers."""
        return len(self._sniffers)

    def __iter__(self):
        """Iterate over loaded sniffers."""
        return iter(self._sniffers)


def load_sniffers_from_path(sniffer_path: str | Path) -> list[SnifferFunc]:
    """Convenience function to load sniffers from a path.

    Args:
        sniffer_path: Path to extensions/sniffer/ directory

    Returns:
        List of loaded SnifferFunc
    """
    loader = SnifferLoader(sniffer_path)
    return loader.load_all()


__all__ = ["SnifferLoader", "load_sniffers_from_path"]
