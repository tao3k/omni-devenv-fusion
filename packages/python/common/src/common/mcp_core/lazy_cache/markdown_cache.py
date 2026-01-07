"""
lazy_cache/markdown_cache.py
Markdown file parsing with lazy loading.

Extracts title, content, and sections from markdown files.

Phase 29: Protocol-based design with slots=True.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base import LazyCacheBase


class MarkdownCache(LazyCacheBase[dict[str, Any]]):
    """Lazy cache for parsing markdown files into structured data.

    Extracts title, content, and sections from markdown files.

    Example:
        cache = MarkdownCache(
            file_path=Path("/project/agent/writing-style/concise.md")
        )
        data = cache.get()  # {"title": "...", "content": "...", "sections": {...}}
    """

    __slots__ = ("_file_path",)

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize markdown cache.

        Args:
            file_path: Path to the markdown file.
            eager: If True, parse file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> dict[str, Any]:
        """Parse markdown file into structured data.

        Returns:
            Dictionary with title, content, and sections.
        """
        if not self._file_path.exists():
            return {"title": "", "content": "", "sections": {}}

        content = self._file_path.read_text(encoding="utf-8")

        # Extract title (first H1)
        title_match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
        title = title_match.group(1) if title_match else ""

        # Extract sections (H2 headers)
        sections: dict[str, str] = {}
        h2_pattern = r"^##\s+(.+)$"
        h2_matches = list(re.finditer(h2_pattern, content, re.MULTILINE))

        for i, match in enumerate(h2_matches):
            section_name = match.group(1).strip()
            start = match.end()
            end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(content)
            sections[section_name] = content[start:end].strip()

        return {"title": title, "content": content, "sections": sections}

    @property
    def title(self) -> str:
        """Get markdown title.

        Returns:
            The title from the markdown file.
        """
        return self.get().get("title", "")

    @property
    def sections(self) -> dict[str, str]:
        """Get markdown sections.

        Returns:
            Dictionary of section names to content.
        """
        return self.get().get("sections", {})


__all__ = ["MarkdownCache"]
