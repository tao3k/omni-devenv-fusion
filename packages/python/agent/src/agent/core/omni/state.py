"""
state.py - Loop State Management.

Track session state using Set for O(1) lookups:
- visited_files: Files that have been read
- modified_files: Files that have been modified

Used by ActionGuard for redundant read detection.
"""

from __future__ import annotations

from typing import Set


class LoopState:
    """Tracks the dynamic state of the current execution session."""

    def __init__(self) -> None:
        self.visited_files: Set[str] = set()
        self.modified_files: Set[str] = set()

    def mark_read(self, file_path: str) -> None:
        """Record that a file was read."""
        self.visited_files.add(file_path)

    def mark_modified(self, file_path: str) -> None:
        """Record that a file was modified."""
        self.modified_files.add(file_path)

    def is_redundant_read(self, file_path: str) -> bool:
        """
        Check if reading this file again is redundant.

        A read is redundant if:
        1. The file was read before (in visited_files)
        2. AND the file has NOT been modified since (not in modified_files)

        Returns:
            True if this would be a redundant read
        """
        return file_path in self.visited_files and file_path not in self.modified_files

    def should_allow_re_read(self, file_path: str) -> bool:
        """
        Check if re-reading a file should be allowed.

        Re-reading is allowed if the file was modified after the last read.

        Returns:
            True if re-reading is allowed (file was modified)
        """
        return file_path in self.modified_files

    def reset(self) -> None:
        """Reset state for a new session."""
        self.visited_files.clear()
        self.modified_files.clear()

    def get_stats(self) -> dict:
        """Get state statistics for logging."""
        return {
            "visited_files": len(self.visited_files),
            "modified_files": len(self.modified_files),
        }


__all__ = ["LoopState"]
