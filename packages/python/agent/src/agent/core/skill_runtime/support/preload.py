"""
preload.py - Core Skills Configuration

Handles core skills configuration from settings.yaml.
"""

from pathlib import Path
from typing import Set


class CoreSkillsConfig:
    """
    Configuration for core skills loaded at startup.

    Core skills are:
    - Loaded from settings.yaml skills.preload list
    - Never evicted by LRU + TTL mechanisms
    - Always available in memory
    """

    __slots__ = ("_core_skills", "_ttl_seconds", "_ttl_check_interval", "_max_loaded_skills")

    def __init__(
        self,
        core_skills: Set[str],
        ttl_seconds: float,
        ttl_check_interval: float,
        max_loaded_skills: int,
    ) -> None:
        self._core_skills = core_skills
        self._ttl_seconds = ttl_seconds
        self._ttl_check_interval = ttl_check_interval
        self._max_loaded_skills = max_loaded_skills

    @property
    def core_skills(self) -> Set[str]:
        return self._core_skills

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    @property
    def ttl_check_interval(self) -> float:
        return self._ttl_check_interval

    @property
    def max_loaded_skills(self) -> int:
        return self._max_loaded_skills

    def is_core_skill(self, skill_name: str) -> bool:
        return skill_name in self._core_skills

    @classmethod
    def from_settings(cls, skills_dir: Path) -> "CoreSkillsConfig":
        """Create from settings.yaml configuration."""
        try:
            from common.config.settings import get_setting

            core_skills = set(get_setting("skills.preload", ["knowledge", "memory", "git"]))
            ttl_seconds = float(get_setting("skills.ttl.timeout", 1800))
            ttl_check_interval = float(get_setting("skills.ttl.check_interval", 300))
            max_loaded_skills = int(get_setting("skills.max_loaded", 15))
        except ImportError:
            core_skills = {"knowledge", "memory", "git"}
            ttl_seconds = 1800.0
            ttl_check_interval = 300.0
            max_loaded_skills = 15

        return cls(
            core_skills=core_skills,
            ttl_seconds=ttl_seconds,
            ttl_check_interval=ttl_check_interval,
            max_loaded_skills=max_loaded_skills,
        )


__all__ = ["CoreSkillsConfig"]
