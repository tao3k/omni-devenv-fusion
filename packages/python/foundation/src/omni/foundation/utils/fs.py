"""fs.py - Filesystem Utilities

Provides filesystem-related utility functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def find_markdown_files(directory: str) -> list[str]:
    """Find all markdown files recursively in a directory.

    Args:
        directory: Root directory to search.

    Returns:
        List of absolute paths to markdown files.
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    files = []
    # Use walk if available (Python 3.12+), else rglob
    if hasattr(path, "walk"):
        for root, _, filenames in path.walk():
            for filename in filenames:
                if filename.endswith((".md", ".markdown")):
                    files.append(str(root / filename))
    else:
        for p in path.rglob("*"):
            if p.suffix in (".md", ".markdown") and p.is_file():
                files.append(str(p))
    return files


def find_files_by_extension(directory: str, extensions: Sequence[str]) -> list[str]:
    """Find all files with given extensions recursively.

    Args:
        directory: Root directory to search.
        extensions: File extensions to match (e.g., ['.py', '.rs']).

    Returns:
        List of absolute paths to matching files.
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    files = []
    ext_tuple = tuple(extensions)
    if hasattr(path, "walk"):
        for root, _, filenames in path.walk():
            for filename in filenames:
                if filename.endswith(ext_tuple):
                    files.append(str(Path(root) / filename))
    else:
        for p in path.rglob("*"):
            if p.suffix in ext_tuple and p.is_file():
                files.append(str(p))
    return files


__all__ = [
    "find_markdown_files",
    "find_files_by_extension",
]
