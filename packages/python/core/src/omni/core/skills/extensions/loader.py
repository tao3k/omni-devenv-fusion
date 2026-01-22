"""loader.py - Skill Extension Loader.

Trinity Architecture - Core Layer

Discovers and loads skill extensions from the filesystem.
Optimized for 1000+ skills - uses silent scanning with summary logging.

Supports:
1. Single-file extensions (e.g., hooks.py)
2. Package extensions (e.g., rust_bridge/__init__.py)

Example output (summary mode):
    Loaded 2 extension sets with 3 total extensions:
    - git: rust_bridge
    - skill: factory
"""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from omni.foundation.config.logging import get_logger

from .wrapper import ExtensionWrapper

logger = get_logger("omni.core.extensions")

# Global registry to track all loaded extensions across all skills
_extension_stats: dict[str, list[str]] = defaultdict(list)
_stats_initialized = False


def _get_stats() -> dict[str, list[str]]:
    """Get global extension statistics."""
    global _extension_stats
    return _extension_stats


def log_extension_summary() -> None:
    """Log a summary of all loaded extensions.

    Call this after all skills have been loaded to print a summary.
    """
    stats = _get_stats()

    # Count skills with extensions
    skills_with_ext = {k: v for k, v in stats.items() if v}
    total_extensions = sum(len(v) for v in stats.values())

    if not skills_with_ext:
        logger.info("No extensions loaded")
        return

    # Log summary header
    logger.info(
        f"Loaded {len(skills_with_ext)} extension sets with {total_extensions} total extensions"
    )

    # Log each skill's extensions
    for skill_name, extensions in sorted(skills_with_ext.items()):
        if extensions:
            logger.info(f"  - {skill_name}: {', '.join(extensions)}")


def reset_extension_stats() -> None:
    """Reset extension statistics (for testing)."""
    global _extension_stats, _stats_initialized
    _extension_stats = defaultdict(list)
    _stats_initialized = False


class SkillExtensionLoader:
    """Extension discovery and loading system.

    Optimized for large skill counts:
    - Silent scanning (no per-skill logging)
    - Summary logging at the end via global registry
    - Extensions are optional and don't block skill loading
    """

    def __init__(
        self,
        extension_path: str | Path,
        skill_name: str = "unknown",
    ) -> None:
        """Initialize loader with extension directory.

        Args:
            extension_path: Path to the extensions directory
            skill_name: Name of the skill (for summary tracking)
        """
        self.extension_path = Path(extension_path)
        self.skill_name = skill_name
        self.extensions: dict[str, ExtensionWrapper] = {}
        self._loaded = False
        self._load_order: list[str] = []

    def load_all(self) -> None:
        """Load all extensions from the directory."""
        if not self.extension_path.exists():
            return

        if self._loaded:
            return

        # Add to sys.path for relative imports within extensions
        path_str = str(self.extension_path)
        sys.path.insert(0, path_str)

        try:
            for item in self.extension_path.iterdir():
                if self._should_skip(item):
                    continue

                if item.is_dir():
                    self._load_package(item.name, item / "__init__.py")
                elif item.is_file() and item.suffix == ".py":
                    self._load_module(item.stem, item)

            self._loaded = True

            # Register extensions in global stats (for summary)
            if self.extensions:
                _extension_stats[self.skill_name] = list(self.extensions.keys())

        finally:
            # Clean up sys.path
            if path_str in sys.path:
                sys.path.remove(path_str)

    def _should_skip(self, item: Path) -> bool:
        """Check if item should be skipped during scanning."""
        # Skip hidden files/directories and cache
        if item.name.startswith("_") or item.name.startswith("."):
            return True
        # Skip __pycache__ directories
        if item.name == "__pycache__":
            return True
        # Skip non-Python files (except __init__.py in directories)
        if item.is_file() and item.suffix != ".py":
            return True
        return False

    def _load_module(self, name: str, path: Path) -> ExtensionWrapper | None:
        """Load a single-file Python module."""
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            wrapper = ExtensionWrapper(module, name)
            self.extensions[name] = wrapper
            self._load_order.append(name)
            return wrapper

        except Exception:
            # Extensions are optional - silently skip on error
            return None

    def _load_package(self, name: str, init_path: Path) -> ExtensionWrapper | None:
        """Load a package-style extension (directory with __init__.py)."""
        try:
            spec = importlib.util.spec_from_file_location(name, init_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)

            # Configure submodule search locations for nested packages
            if spec.submodule_search_locations is None:
                spec.submodule_search_locations = [str(init_path.parent)]

            spec.loader.exec_module(module)

            wrapper = ExtensionWrapper(module, name)
            self.extensions[name] = wrapper
            self._load_order.append(name)
            return wrapper

        except Exception:
            # Extensions are optional - silently skip on error
            return None

    def get(self, name: str) -> ExtensionWrapper | None:
        """Get an extension by name.

        Args:
            name: Extension name (filename or directory name without extension)

        Returns:
            ExtensionWrapper or None if not found
        """
        return self.extensions.get(name)

    def get_or_raise(self, name: str) -> ExtensionWrapper:
        """Get an extension by name, raising if not found.

        Args:
            name: Extension name

        Returns:
            ExtensionWrapper

        Raises:
            KeyError: If extension not found
        """
        if name not in self.extensions:
            raise KeyError(
                f"Extension '{name}' not found. Available: {list(self.extensions.keys())}"
            )
        return self.extensions[name]

    def has(self, name: str) -> bool:
        """Check if an extension exists."""
        return name in self.extensions

    def list_all(self) -> list[str]:
        """List all loaded extension names."""
        return list(self.extensions.keys())

    def __iter__(self) -> Iterator[str]:
        """Iterate over extension names."""
        return iter(self.extensions)

    def __len__(self) -> int:
        """Return number of loaded extensions."""
        return len(self.extensions)

    def __bool__(self) -> bool:
        """Return True if any extensions are loaded."""
        return bool(self.extensions)

    @property
    def is_loaded(self) -> bool:
        """Check if extensions have been loaded."""
        return self._loaded

    @property
    def load_order(self) -> list[str]:
        """Get extensions in the order they were loaded."""
        return list(self._load_order)


def get_extension_loader(
    extension_path: str | Path,
    skill_name: str = "unknown",
) -> SkillExtensionLoader:
    """Factory function to create and load extensions.

    Args:
        extension_path: Path to extensions directory
        skill_name: Name of the skill (for summary tracking)

    Returns:
        Loaded SkillExtensionLoader instance
    """
    loader = SkillExtensionLoader(extension_path, skill_name)
    loader.load_all()
    return loader
