"""
omni.core.skills.registry - Skill Registry

Modular skill registry with separated concerns:
- core.py: Core registry class
- loader.py: Module loading
- context.py: Context building
- installer.py: Remote installation
- resolver.py: Version resolution
- jit.py: JIT acquisition

Thin client implementation - remote installation deprecated.
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


# Deprecated remote installation functions
def install_remote_skill(name: str, url: str, version: str = "main") -> tuple:
    """Install a skill from a remote repository. [DEPRECATED]"""
    logger.warning("Remote skill installation is deprecated in thin client mode")
    return False, "Remote installation not available. Add skills to assets/skills/ manually."


def update_remote_skill(name: str, version: str = "main") -> tuple:
    """Update an installed skill. [DEPRECATED]"""
    logger.warning("Remote skill update is deprecated in thin client mode")
    return False, "Remote updates not available."


# JIT and discovery functions - deprecated placeholders
def jit_install_skill(skill_id: str) -> dict[str, Any]:
    """JIT install a skill. [DEPRECATED]"""
    return {"success": False, "error": "JIT installation not available in thin client mode"}


def security_scan_skill(skill_path: str) -> dict[str, Any]:
    """Security scan a skill."""
    return {"safe": True, "warnings": []}


def discover_skills(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Discover skills matching query. [DEPRECATED]"""
    return []


def suggest_skills_for_task(task: str) -> list[str]:
    """Suggest skills for a task. [DEPRECATED]"""
    return []


def list_installed_skills() -> list[str]:
    """List installed skills."""
    from omni.foundation.config.skills import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    if skills_dir.exists():
        return [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
    return []


def get_skill_tools(skill_name: str) -> list[dict[str, Any]]:
    """Get tools for a skill."""
    return []


# Legacy re-exports removed (agent.core.skill_registry no longer exists)


__all__ = [
    # Core
    "SkillRegistry",
    "get_skill_registry",
    # Deprecated remote operations
    "install_remote_skill",
    "update_remote_skill",
    # JIT and discovery (deprecated)
    "jit_install_skill",
    "security_scan_skill",
    "discover_skills",
    "suggest_skills_for_task",
    "list_installed_skills",
    "get_skill_tools",
]
