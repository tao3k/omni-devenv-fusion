"""
lazy_cache/file_cache.py
File content caching with lazy loading.

Phase 29: Protocol-based design with slots=True.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import LazyCacheBase


class FileCache(LazyCacheBase[str]):
    """Lazy cache for loading and caching file contents.

    Example:
        cache = FileCache(
            file_path=Path("/project/agent/writing-style/concise.md")
        )
        content = cache.get()  # Loaded once, cached forever
    """

    __slots__ = ("_file_path",)

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize file cache.

        Args:
            file_path: Path to the file to cache.
            eager: If True, load file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> str:
        """Load file contents.

        Returns:
            File contents as string, or empty string if file doesn't exist.
        """
        if not self._file_path.exists():
            return ""
        return self._file_path.read_text(encoding="utf-8")

    @property
    def content(self) -> str:
        """Get file content.

        Returns:
            Cached file content.
        """
        return self.get()


__all__ = ["FileCache"]
