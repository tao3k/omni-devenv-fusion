"""
omni.core.skills.registry - Skill Registry

Runtime skill registry surface:
- SkillRegistry / get_skill_registry
- HolographicRegistry exports
"""

from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.registry")


class SkillRegistry:
    """Core skill registry for thin client model."""

    def __init__(self):
        self._skills: dict[str, Any] = {}

    def register(self, name: str, skill: Any) -> None:
        """Register a skill."""
        self._skills[name] = skill
        logger.debug(f"Registered skill: {name}")

    def get(self, name: str) -> Any | None:
        """Get a registered skill."""
        return self._skills.get(name)

    def list_all(self) -> list[str]:
        """List all registered skills."""
        return list(self._skills.keys())


# Global registry singleton
_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


# Import from holographic module for re-export
from .holographic import (
    HolographicRegistry,
    ToolMetadata,
    LazyTool,
)


__all__ = [
    # Core
    "SkillRegistry",
    "get_skill_registry",
    # Holographic Registry
    "HolographicRegistry",
    "ToolMetadata",
    "LazyTool",
]
