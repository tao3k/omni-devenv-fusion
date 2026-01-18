"""
registry.py - Skill Registry

Manages shared state for all skill services:
- _skills: Skill registry (skill_name -> Skill)
- _command_cache: Command lookup cache (skill.command -> SkillCommand)
- _mtime_cache: Modification time cache (skill_name -> mtime)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..support.models import Skill, SkillCommand


class SkillRegistry:
    """
    Central registry for skill state.

    All sub-managers share state through this registry instead of
    holding their own references.

    Thread-safe for read operations. Write operations should be
    synchronized externally when needed.
    """

    __slots__ = (
        "_skills",
        "_command_cache",
        "_mtime_cache",
    )

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._skills: dict[str, "Skill"] = {}
        self._command_cache: dict[str, "SkillCommand"] = {}
        self._mtime_cache: dict[str, float] = {}

    # =========================================================================
    # Skills Registry
    # =========================================================================

    @property
    def skills(self) -> dict[str, "Skill"]:
        """Get skills registry (read-only dict)."""
        return self._skills

    def get_skill(self, skill_name: str) -> "Skill | None":
        """Get a skill by name."""
        return self._skills.get(skill_name)

    def register_skill(self, skill: "Skill") -> None:
        """Register a skill."""
        self._skills[skill.name] = skill

    def unregister_skill(self, skill_name: str) -> "Skill | None":
        """Unregister a skill."""
        return self._skills.pop(skill_name, None)

    def list_loaded(self) -> list[str]:
        """List all loaded skill names."""
        return list(self._skills.keys())

    # =========================================================================
    # Command Cache
    # =========================================================================

    @property
    def command_cache(self) -> dict[str, "SkillCommand"]:
        """Get command cache (read-only dict)."""
        return self._command_cache

    def get_command(self, skill_name: str, command_name: str) -> "SkillCommand | None":
        """Get a command by skill.command or just command name."""
        cache_key = f"{skill_name}.{command_name}"
        return self._command_cache.get(cache_key) or self._command_cache.get(command_name)

    def register_command(self, skill_name: str, command: "SkillCommand") -> None:
        """Register a command in cache."""
        full_name = f"{skill_name}.{command.name}"
        self._command_cache[full_name] = command
        # Also register without skill prefix if not already present
        if command.name not in self._command_cache:
            self._command_cache[command.name] = command

    def unregister_commands(self, skill_name: str) -> None:
        """Unregister all commands for a skill."""
        keys_to_remove = [k for k in self._command_cache if k.startswith(f"{skill_name}.")]
        for key in keys_to_remove:
            del self._command_cache[key]

    def clear_command_cache(self, skill_name: str, command_name: str) -> None:
        """Clear a specific command cache entry (for hot reload)."""
        cache_key = f"{skill_name}.{command_name}"
        if cache_key in self._command_cache:
            del self._command_cache[cache_key]

    # =========================================================================
    # MTime Cache
    # =========================================================================

    @property
    def mtime_cache(self) -> dict[str, float]:
        """Get mtime cache (read-only dict)."""
        return self._mtime_cache

    def get_mtime(self, skill_name: str) -> float | None:
        """Get mtime for a skill."""
        return self._mtime_cache.get(skill_name)

    def set_mtime(self, skill_name: str, mtime: float) -> None:
        """Set mtime for a skill."""
        self._mtime_cache[skill_name] = mtime

    def clear_mtime(self, skill_name: str) -> None:
        """Clear mtime for a skill."""
        self._mtime_cache.pop(skill_name, None)

    # =========================================================================
    # Utility
    # =========================================================================

    def clear(self) -> None:
        """Clear all state (for testing)."""
        self._skills.clear()
        self._command_cache.clear()
        self._mtime_cache.clear()


# Global registry singleton
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """Get or create the global registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


__all__ = ["SkillRegistry", "get_registry", "reset_registry"]
