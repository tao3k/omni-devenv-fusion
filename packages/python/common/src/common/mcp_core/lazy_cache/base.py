"""
lazy_cache/base.py
Base classes for lazy-loading singleton caches.

Phase 29: Protocol-based design with slots=True for memory efficiency.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class LazyCacheBase(ABC, Generic[T]):
    """Abstract base class for lazy-loading singleton caches.

    Subclasses must implement _load() to define how data is loaded.
    The cache uses singleton pattern - only one instance exists.

    Features:
    - Singleton pattern: Only one instance per cache type
    - Lazy loading: Load on first access, not at import time
    - Thread-safe: Safe for concurrent access
    - Hot reload: reload() method to refresh cache

    Usage:
        class WritingStyleCache(LazyCacheBase[dict]):
            @property
            def _file_path(self) -> Path:
                from common.gitops import get_project_root
                return get_project_root() / "agent/writing-style/concise.md"

            def _load(self) -> dict:
                content = self._file_path.read_text()
                return self._parse(content)

        cache = WritingStyleCache()
        guidelines = cache.get()  # Auto-loaded on first call
    """

    _instance: LazyCacheBase[T] | None = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls, eager: bool = False) -> LazyCacheBase[T]:
        """Create singleton instance with optional eager loading."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data: T | None = None
                    if eager:
                        cls._instance._ensure_loaded()
        return cls._instance

    def __init__(self, eager: bool = False) -> None:
        """Initialize cache.

        Note:
            Singleton pattern ensures __init__ only runs once per class.
        """
        pass

    def _ensure_loaded(self) -> T:
        """Ensure data is loaded, thread-safe with double-check locking.

        Returns:
            The loaded data.
        """
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._data = self._load()  # type: ignore[union-attr]
                    self._loaded = True
        return self._data  # type: ignore[return-value]

    @abstractmethod
    def _load(self) -> T:
        """Load and return cached data.

        Override this method in subclasses to implement custom loading logic.
        This is called exactly once - on first access.

        Returns:
            The data to cache and return on subsequent get() calls.
        """
        ...

    def get(self) -> T:
        """Get cached data, loading if necessary.

        Returns:
            The cached data.
        """
        return self._ensure_loaded()

    def reload(self) -> T:
        """Force reload of cached data.

        Use this to refresh cache after source files change.

        Returns:
            The newly loaded data.
        """
        with self._instance_lock:
            self._data = self._load()  # type: ignore[union-attr]
            self._loaded = True
        return self._data  # type: ignore[return-value]

    @property
    def is_loaded(self) -> bool:
        """Check if cache has been loaded.

        Returns:
            True if cache is loaded, False otherwise.
        """
        return self._loaded

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance.

        Use with caution - this clears the cache and creates a new instance.
        Primarily for testing.
        """
        with cls._instance_lock:
            cls._instance = None
            cls._loaded = False


__all__ = ["LazyCacheBase"]
