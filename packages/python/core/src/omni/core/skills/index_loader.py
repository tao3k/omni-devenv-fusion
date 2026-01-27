"""
index_loader.py - LanceDB-based Skill Index Loader

Loads and indexes skill metadata from LanceDB for O(1) metadata lookup.

Python 3.12+ Features:
- Native generics for type hints
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.skills.index_loader")


class SkillIndexLoader:
    """Loads and indexes skill metadata from LanceDB for fast lookup."""

    def __init__(self) -> None:
        self._skills: list[dict[str, Any]] | None = None
        self._metadata_map: dict[str, dict[str, Any]] = {}

    def reload(self) -> None:
        """Force reload index from LanceDB."""
        self._skills = None
        self._metadata_map = {}
        logger.debug("SkillIndexLoader: Index reloaded from LanceDB")

    def _ensure_loaded(self) -> None:
        """Lazy load index from LanceDB."""
        if self._skills is not None:
            return

        try:
            import asyncio
            from omni.foundation.bridge import RustVectorStore

            store = RustVectorStore()
            tools = asyncio.run(store.list_all_tools())

            # Group tools by skill_name
            skills_map: dict[str, dict[str, Any]] = {}
            for tool in tools:
                skill_name = tool.get("skill_name", "unknown")
                if skill_name not in skills_map:
                    skills_map[skill_name] = {
                        "name": skill_name,
                        "description": tool.get("description", ""),
                        "tools": [],
                    }
                skills_map[skill_name]["tools"].append(
                    {
                        "name": tool.get("tool_name", ""),
                        "description": tool.get("description", ""),
                    }
                )

            self._skills = list(skills_map.values())
            self._metadata_map = skills_map

            logger.debug(f"SkillIndexLoader: Indexed {len(self._skills)} skills from LanceDB")

        except Exception as e:
            logger.error(f"SkillIndexLoader: Failed to load from LanceDB: {e}")
            self._skills = []
            self._metadata_map = {}

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
        return self._skills is not None


__all__ = ["SkillIndexLoader"]
