"""
jit_loader.py - JIT Skill Loading

Handles Just-In-Time skill loading from the vector index.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..support.models import Skill


def _get_logger():
    from ...protocols import _get_logger

    return _get_logger()


class SkillJITLoader:
    """
    Manages Just-In-Time skill loading from disk or vector index.

    Strategy:
    1. First try direct path lookup (fastest - most common case)
    2. Fall back to semantic search if skill not in expected location
    """

    __slots__ = (
        "_skills_dir",
        "_search_skills",
        "_load_skill",
    )

    def __init__(
        self,
        skills_dir: Path,
        search_skills: Callable[..., Any],
        load_skill: Callable[[Path], "Skill | None"],
    ) -> None:
        self._skills_dir = skills_dir
        self._search_skills = search_skills
        self._load_skill = load_skill

    async def try_load(self, skill_name: str) -> bool:
        """
        Attempt to Just-In-Time load a skill.

        Args:
            skill_name: Name of the skill to load

        Returns:
            True if skill was successfully loaded, False otherwise
        """
        from common.skills_path import SKILLS_DIR

        logger = _get_logger()
        logger.debug("Attempting JIT load", skill=skill_name)

        # Strategy 1: Direct path lookup using SKILLS_DIR (fastest - most common case)
        definition_path = SKILLS_DIR.definition_file(skill_name)
        if definition_path.exists():
            logger.info(
                "JIT loaded skill from disk", skill=skill_name, path=str(definition_path.parent)
            )
            self._load_skill(definition_path.parent)
            return True

        # Strategy 2: Fall back to semantic search (edge case: skill moved)
        results = await self._search_skills(skill_name, limit=10)

        for tool in results:
            meta = tool.get("metadata", {})
            if meta.get("skill_name") == skill_name:
                script_path_str = meta.get("file_path")
                if script_path_str:
                    script_path = Path(script_path_str)
                    try:
                        potential_root = script_path.parent.parent
                        if (potential_root / "SKILL.md").exists():
                            logger.info(
                                "JIT loaded skill from index",
                                skill=skill_name,
                                path=str(potential_root),
                            )
                            self._load_skill(potential_root)
                            return True
                    except Exception:
                        continue

        logger.warning("JIT load failed: Skill not found", skill=skill_name)
        return False


__all__ = ["SkillJITLoader"]
