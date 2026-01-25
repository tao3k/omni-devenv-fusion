"""
index_loader.py - Rust Index Loader

Loads and indexes Rust-generated skill_index.json for O(1) metadata lookup.

Python 3.12+ Features:
- Native generics for type hints
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.skills.index_loader")


class SkillIndexLoader:
    """Loads and indexes Rust-generated skill metadata for fast lookup."""

    # Default index path: .cache/skill_index.json (set by Rust scanner)
    DEFAULT_INDEX_PATH = ".cache/skill_index.json"

    def __init__(self, index_path: Path | None = None) -> None:
        if index_path is None:
            # Use default path, resolved relative to project root
            from omni.foundation.runtime.gitops import get_project_root

            root = get_project_root()
            index_path = root / self.DEFAULT_INDEX_PATH
        self._index_path = index_path
        self._index: list[dict[str, Any]] | None = None
        self._metadata_map: dict[str, dict[str, Any]] = {}

    def reload(self) -> None:
        """Force reload index (useful for dev hot-reload)."""
        self._index = None
        self._metadata_map = {}
        logger.debug("SkillIndexLoader: Index reloaded")

    def _ensure_loaded(self) -> None:
        """Lazy load index from JSON file."""
        if self._index is not None:
            return

        if not self._index_path.exists():
            logger.warning(f"SkillIndexLoader: Index not found at {self._index_path}")
            self._index = []
            return

        try:
            content = self._index_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self._index = data if isinstance(data, list) else []

            # Build O(1) lookup map
            self._metadata_map = {}
            for skill in self._index:
                name = skill.get("name")
                if name:
                    self._metadata_map[name] = skill

            logger.debug(f"SkillIndexLoader: Indexed {len(self._index)} skills")

        except json.JSONDecodeError as e:
            logger.error(f"SkillIndexLoader: Corrupt JSON at {self._index_path}: {e}")
            self._index = []
        except Exception as e:
            logger.error(f"SkillIndexLoader: Failed to load index: {e}")
            self._index = []

    def get_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """O(1) lookup for skill metadata by name."""
        self._ensure_loaded()
        return self._metadata_map.get(skill_name)

    def list_skills(self) -> list[str]:
        """Get all skill names."""
        self._ensure_loaded()
        return list(self._metadata_map.keys())

    @property
    def is_loaded(self) -> bool:
        """Check if index is loaded."""
        return self._index is not None


__all__ = ["SkillIndexLoader"]
