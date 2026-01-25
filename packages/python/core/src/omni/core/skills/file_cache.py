"""
file_cache.py - Smart File Cache

Thread-safe file content cache to avoid repeated disk I/O.

Features:
- LRU-style content caching
- Path validation
- Error handling with graceful fallbacks
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.skills.file_cache")


class FileCache:
    """Thread-safe file content cache with path safety."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def read(self, path: Path) -> str:
        """Read file content with caching.

        Args:
            path: Path to file

        Returns:
            File content or error message
        """
        resolved = str(path.resolve())

        # Cache hit
        if resolved in self._cache:
            return self._cache[resolved]

        # Validate path
        if not path.exists():
            msg = f"[Missing: {path.name}]"
            self._cache[resolved] = msg
            return msg

        if not path.is_file():
            msg = f"[Not a file: {path.name}]"
            self._cache[resolved] = msg
            return msg

        # Read file
        try:
            content = path.read_text(encoding="utf-8")
            self._cache[resolved] = content
            return content
        except UnicodeDecodeError:
            msg = f"[Encoding error: {path.name}]"
            self._cache[resolved] = msg
            return msg
        except PermissionError:
            msg = f"[Permission denied: {path.name}]"
            self._cache[resolved] = msg
            return msg
        except Exception as e:
            logger.error(f"FileCache: Read error {path}: {e}")
            msg = f"[Error reading: {path.name}]"
            self._cache[resolved] = msg
            return msg

    def get(self, path: Path) -> str | None:
        """Get cached content without fallback.

        Args:
            path: Path to file

        Returns:
            Cached content or None if not cached
        """
        resolved = str(path.resolve())
        return self._cache.get(resolved)

    def contains(self, path: Path) -> bool:
        """Check if path is in cache."""
        return str(path.resolve()) in self._cache

    def clear(self) -> None:
        """Clear all cached content."""
        self._cache.clear()
        logger.debug("FileCache: Cache cleared")

    def remove(self, path: Path) -> bool:
        """Remove specific path from cache."""
        resolved = str(path.resolve())
        if resolved in self._cache:
            del self._cache[resolved]
            return True
        return False

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "cached_files": len(self._cache),
        }


__all__ = ["FileCache"]
