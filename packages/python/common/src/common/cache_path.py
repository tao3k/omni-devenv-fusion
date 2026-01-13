# cache_path.py
"""
Common Cache Path Utilities - Centralized cache directory handling.

Provides:
- CACHE_DIR: Callable to get cache paths (e.g., CACHE_DIR("memory") -> Path)
- get_cache_dir(): Function form for getting cache paths

Usage:
    from common.cache_path import CACHE_DIR

    # Get cache directory from settings.yaml -> assets.cache_dir
    cache_base = CACHE_DIR()                    # -> /project/root/.cache
    memory_dir = CACHE_DIR("memory")            # -> /project/root/.cache/memory
    feedback_file = CACHE_DIR("memory", "routing_feedback.json")  # -> /project/root/.cache/memory/routing_feedback.json

Settings:
    Reads from settings.yaml:
        assets:
          cache_dir: ".cache"        # Cache base directory
"""

from pathlib import Path
from typing import Optional


class _CacheDirCallable:
    """Callable that returns cache paths based on settings.yaml config.

    Usage:
        CACHE_DIR()                              # -> Path(".cache") (base path)
        CACHE_DIR("memory")                      # -> Path(".cache/memory")
        CACHE_DIR("memory", "routing_feedback.json")  # -> Path(".cache/memory/routing_feedback.json")
    """

    _cached_base_path: Optional[Path] = None

    def _get_base_path(self) -> Path:
        """Get the base cache path from settings.yaml (assets.cache_dir)."""
        if self._cached_base_path is not None:
            return self._cached_base_path

        try:
            from common.config.settings import Settings

            # Use Settings directly to avoid path auto-resolution
            settings = Settings()
            cache_path_str = settings.get("assets.cache_dir")
            if cache_path_str:
                self._cached_base_path = Path(cache_path_str)
                return self._cached_base_path
        except Exception:
            pass

        # Fallback: use default ".cache"
        self._cached_base_path = Path(".cache")
        return self._cached_base_path

    def _resolve_with_root(self, path: Path) -> Path:
        """Resolve path relative to project root using git toplevel."""
        if path.is_absolute():
            return path

        from common.gitops import get_project_root

        project_root = get_project_root()
        return project_root / path

    def __call__(self, *parts: str) -> Path:
        """Get path for cache subdirectory or file.

        Args:
            *parts: Path components to join after cache base

        Returns:
            Absolute path to cache directory or file

        Usage:
            CACHE_DIR()                                  # -> /project/.cache
            CACHE_DIR("memory")                          # -> /project/.cache/memory
            CACHE_DIR("memory", "routing_feedback.json") # -> /project/.cache/memory/routing_feedback.json
        """
        base = self._get_base_path()
        base = self._resolve_with_root(base)

        if not parts:
            return base

        return base.joinpath(*parts)

    def __truediv__(self, other: str) -> Path:
        """Support / operator for path joining.

        Usage:
            CACHE_DIR / "memory" / "file.json"
        """
        return self() / other

    def ensure_dir(self, *parts: str) -> Path:
        """Get path and ensure directory exists.

        Args:
            *parts: Path components (last one can be a file)

        Returns:
            Path to the directory (creates if not exists)

        Usage:
            CACHE_DIR.ensure_dir("memory")  # Creates and returns .cache/memory/
        """
        path = self(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_parent(self, *parts: str) -> Path:
        """Get path and ensure parent directory exists.

        Args:
            *parts: Path components (last one is typically a file)

        Returns:
            Full path (parent directory created if not exists)

        Usage:
            path = CACHE_DIR.ensure_parent("memory", "data.json")
            # Creates .cache/memory/, returns .cache/memory/data.json
        """
        path = self(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def clear_cache(self) -> None:
        """Clear cached base path (useful for testing or reconfiguration)."""
        self._cached_base_path = None


# Global instance
CACHE_DIR: _CacheDirCallable = _CacheDirCallable()


def get_cache_dir(*parts: str) -> Path:
    """Function form of CACHE_DIR for those who prefer functions over callables.

    Args:
        *parts: Path components to join after cache base

    Returns:
        Absolute path to cache directory or file
    """
    return CACHE_DIR(*parts)


__all__ = [
    "CACHE_DIR",
    "get_cache_dir",
]
