"""
boot_core.py - Skill Boot Management

Handles O(1) boot via skill_index.json.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .models import Skill


class SkillBootManager:
    """
    Manages skill boot via skill_index.json for O(1) startup.

    Features:
    - Check index freshness
    - Load skills from index
    - Fallback to filesystem discovery
    """

    __slots__ = (
        "_skills_dir",
        "_index_path",
        "_index_loaded",
        "_skills",
        "_load_skill",
        "_load_all",
        "_get_logger",
    )

    def __init__(
        self,
        skills_dir: Path,
        index_path: Path,
        skills: dict[str, "Skill"],
        load_skill: Callable[[Path], "Skill | None"],
        load_all: Callable[[], dict[str, "Skill"]],
        get_logger: Callable,
    ) -> None:
        self._skills_dir = skills_dir
        self._index_path = index_path
        self._index_loaded = False
        self._skills = skills
        self._load_skill = load_skill
        self._load_all = load_all
        self._get_logger = get_logger

    @property
    def index_path(self) -> Path:
        """Get the skill index file path."""
        return self._index_path

    @property
    def is_index_loaded(self) -> bool:
        """Check if skills were loaded from index."""
        return self._index_loaded

    def is_index_fresh(self) -> bool:
        """
        Check if skill_index.json is fresh (newer than skills directory).

        Returns:
            True if index exists and is up to date
        """
        from common.skills_path import SKILLS_DIR

        index_path = self._index_path
        if not index_path.exists():
            return False

        try:
            index_mtime = index_path.stat().st_mtime
            skills_dir = SKILLS_DIR()

            # Check if any skill directory is newer than index
            for entry in skills_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith("_"):
                    skill_mtime = (entry / "SKILL.md").stat().st_mtime
                    if skill_mtime > index_mtime:
                        self._get_logger().debug(
                            "Index stale - skill newer than index",
                            skill=entry.name,
                        )
                        return False

            return True
        except Exception:
            return False

    def load_from_index(self) -> dict[str, "Skill"]:
        """
        Load all skills from skill_index.json (O(1) boot).

        This method:
        1. Reads assets/skills/skill_index.json
        2. Extracts skill names and paths
        3. Loads full skill data
        4. Falls back to filesystem discovery if index is stale

        Returns:
            Dictionary of loaded skills
        """
        import json

        index_path = self._index_path
        logger = self._get_logger()

        if self._skills:
            logger.debug("Skills already loaded")
            return self._skills

        if not index_path.exists():
            logger.info("Skill index not found, falling back to filesystem discovery")
            return self._load_all()

        try:
            with open(index_path, "r") as f:
                index_data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read skill index: {e}, falling back to filesystem")
            return self._load_all()

        logger.info("Loading skills", count=len(index_data))

        loaded_count = 0
        loaded_skills: list[str] = []
        for entry in index_data:
            skill_name = entry.get("name")
            if not skill_name:
                continue

            skill_path = self._skills_dir / skill_name
            if not skill_path.exists():
                logger.debug("Skill not found on disk", skill=skill_name)
                continue

            # Load full skill (commands, etc.)
            skill = self._load_skill(skill_path)
            if skill:
                loaded_count += 1
                loaded_skills.append(skill_name)

        self._index_loaded = True

        # Compact summary - show first 5 skills + count
        skills_preview = ", ".join(loaded_skills[:5])
        extra = f"... +{len(loaded_skills) - 5}" if len(loaded_skills) > 5 else ""
        logger.info(
            f"Skills loaded: {loaded_count} [{skills_preview}{extra}]",
            count=loaded_count,
            source="skill_index.json",
        )
        return self._skills


__all__ = ["SkillBootManager"]
