"""
query_core.py - Skill Query Management

Handles skill listing, info retrieval, and command queries.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .models import Skill, SkillCommand


class SkillQueryManager:
    """
    Manages skill queries: listing, info, and command lookups.

    Features:
    - List available/loaded skills
    - Get skill info and commands
    - Command resolution
    """

    __slots__ = (
        "_skills_dir",
        "_skills",
        "_discover",
        "_get_logger",
    )

    def __init__(
        self,
        skills_dir: Path,
        skills: dict[str, "Skill"],
        discover: Callable[[], list[Path]],
        get_logger: Callable,
    ) -> None:
        self._skills_dir = skills_dir
        self._skills = skills
        self._discover = discover
        self._get_logger = get_logger

    # =========================================================================
    # Listing
    # =========================================================================

    def list_available(self) -> list[str]:
        """List all discovered skills (O(N) - filesystem scan)."""
        return [p.name for p in self._discover()]

    def list_available_from_index(self) -> list[str]:
        """
        List all skills from skill_index.json (O(1) - no module loading).

        This is much faster than list_available() when you only need
        the skill names, not the full Skill objects.

        Returns:
            List of skill names from the index
        """
        from common.skills_path import SKILLS_DIR

        index_path = SKILLS_DIR() / "skill_index.json"
        logger = self._get_logger()
        if not index_path.exists():
            logger.debug("Skill index not found, falling back to discover")
            return self.list_available()

        try:
            with open(index_path, "r") as f:
                index_data = json.load(f)
            return [s.get("name") for s in index_data if s.get("name")]
        except Exception as e:
            logger.warning(f"Failed to read skill index: {e}")
            return self.list_available()

    def list_loaded(self) -> list[str]:
        """List all loaded skills."""
        return list(self._skills.keys())

    # =========================================================================
    # Info
    # =========================================================================

    def get_info(self, skill_name: str) -> dict[str, Any] | None:
        """
        Get detailed skill info including manifest and commands.

        Returns dict matching manager.py format for backward compatibility.
        """
        skill = self._skills.get(skill_name)
        if skill is None:
            return None

        # Get execution_mode value safely
        exec_mode = skill.execution_mode
        if hasattr(exec_mode, "value"):
            exec_mode_value = exec_mode.value
        else:
            exec_mode_value = str(exec_mode)

        return {
            "name": skill.name,
            "version": skill.metadata.version if skill.metadata else "unknown",
            "description": skill.metadata.description if skill.metadata else "",
            "command_count": len(skill.commands),
            "execution_mode": exec_mode_value,
            "commands": list(skill.commands.keys()),
            "loaded": True,
            "metadata": skill.metadata,
        }

    def get_commands(self, skill_name: str) -> list[str]:
        """Get list of command names for a skill."""
        skill = self._skills.get(skill_name)
        if skill is None:
            return []
        return list(skill.commands.keys())

    def get_command(self, skill_name: str, command_name: str) -> "SkillCommand | None":
        """Get a specific command from a skill."""
        skill = self._skills.get(skill_name)
        if skill is None:
            return None
        return skill.commands.get(command_name)


__all__ = ["SkillQueryManager"]
