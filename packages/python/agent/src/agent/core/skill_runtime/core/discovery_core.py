"""
_modules/_discovery/ - Skill Discovery Module

Handles skill discovery from filesystem and skill_index.json.

Features:
- Discover all skill directories in skills folder
- Discover single skill by name
- Index freshness checking
- Load skills from index file
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from agent.core.skill_runtime.models import Skill


class SkillDiscovery:
    """
    Handles skill discovery from filesystem and skill_index.json.

    Features:
    - Discover all skill directories in skills folder
    - Discover single skill by name
    - Index freshness checking
    - Load skills from index file
    """

    __slots__ = ("_skills_dir", "_index_path")

    def __init__(self, skills_dir: Path) -> None:
        """Initialize the discovery manager.

        Args:
            skills_dir: Path to the skills directory
        """
        self._skills_dir = Path(skills_dir)
        self._index_path = self._skills_dir / "skill_index.json"

    # =========================================================================
    # Discovery
    # =========================================================================

    def discover(self) -> list[Path]:
        """
        Discover all skill directories in the skills folder.

        A valid skill directory must:
        - Be a subdirectory of skills_dir
        - Contain a SKILL.md file

        Returns:
            List of skill directory paths, sorted by name
        """
        if not self._skills_dir.exists():
            return []

        skills = []
        for entry in self._skills_dir.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").exists():
                skills.append(entry)
        return sorted(skills, key=lambda p: p.name)

    def discover_single(self, skill_name: str) -> Optional[Path]:
        """
        Discover a single skill by name.

        Args:
            skill_name: Name of the skill to find

        Returns:
            Path to skill directory or None if not found
        """
        skill_path = self._skills_dir / skill_name
        if skill_path.exists() and (skill_path / "SKILL.md").exists():
            return skill_path
        return None

    # =========================================================================
    # Index Management
    # =========================================================================

    def is_index_fresh(self) -> bool:
        """
        Check if skill_index.json is fresh.

        The index is fresh if all skills referenced in it still exist
        on the filesystem.

        Returns:
            True if index exists and all referenced skills exist, False otherwise
        """
        if not self._index_path.exists():
            return False

        try:
            with open(self._index_path, "r") as f:
                index_data = json.load(f)
        except Exception:
            return False

        for entry in index_data:
            skill_name = entry.get("name")
            if skill_name:
                skill_path = self._skills_dir / skill_name
                if not skill_path.exists():
                    return False
        return True

    def load_from_index(
        self,
        load_skill: Callable[[Path], Optional["Skill"]],
        on_loaded: Callable[[str], None],
    ) -> dict[str, "Skill"]:
        """
        Load all skills from skill_index.json.

        Args:
            load_skill: Function to load a skill from path
            on_loaded: Callback when a skill is loaded

        Returns:
            Dictionary mapping skill names to loaded Skill objects
        """
        if not self._index_path.exists():
            return {}

        try:
            with open(self._index_path, "r") as f:
                index_data = json.load(f)
        except Exception:
            return {}

        loaded: dict[str, "Skill"] = {}
        loaded_skills: list[str] = []

        for entry in index_data:
            skill_name = entry.get("name")
            if not skill_name:
                continue

            skill_path = self._skills_dir / skill_name
            if not skill_path.exists():
                continue

            skill = load_skill(skill_path)
            if skill:
                loaded[skill_name] = skill
                loaded_skills.append(skill_name)
                on_loaded(skill_name)

        return loaded

    @property
    def index_path(self) -> Path:
        """Get the path to the skill index file."""
        return self._index_path

    @property
    def skills_dir(self) -> Path:
        """Get the skills directory path."""
        return self._skills_dir


__all__ = ["SkillDiscovery"]
