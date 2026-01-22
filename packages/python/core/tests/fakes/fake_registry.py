"""
Fake Skill Registry for Testing.

A mock skill registry that simulates skill discovery and loading.
"""

from pathlib import Path
from typing import Any


class FakeSkillRegistry:
    """
    Fake skill registry for testing.

    Simulates skill discovery, loading, and manifest retrieval.

    Usage:
        registry = FakeSkillRegistry()
        registry.add_skill("git", manifest)
        skills = registry.list_available_skills()
    """

    def __init__(self):
        self._available_skills: dict[str, Path] = {}
        self._loaded_skills: dict[str, Any] = {}
        self._manifests: dict[str, Any] = {}
        self._load_errors: dict[str, str] = {}

    def add_skill(self, name: str, manifest: dict[str, Any], module: Any = None) -> None:
        """Add a skill to the registry."""
        self._available_skills[name] = Path(f"/fake/skills/{name}")
        self._manifests[name] = manifest
        if module is not None:
            self._loaded_skills[name] = module

    def remove_skill(self, name: str) -> None:
        """Remove a skill from the registry."""
        self._available_skills.pop(name, None)
        self._manifests.pop(name, None)
        self._loaded_skills.pop(name, None)
        self._load_errors.pop(name, None)

    def list_available_skills(self) -> list[str]:
        """List all available skills."""
        return list(self._available_skills.keys())

    def list_loaded_skills(self) -> list[str]:
        """List all loaded skills."""
        return list(self._loaded_skills.keys())

    def get_manifest(self, skill_name: str) -> dict[str, Any] | None:
        """Get manifest for a skill."""
        return self._manifests.get(skill_name)

    def get_skill(self, skill_name: str) -> Any | None:
        """Get loaded skill module."""
        return self._loaded_skills.get(skill_name)

    async def load_skill(self, skill_name: str) -> tuple[bool, str]:
        """Simulate loading a skill."""
        if skill_name not in self._available_skills:
            return False, f"Skill '{skill_name}' not found"

        if skill_name in self._loaded_skills:
            return True, f"Skill '{skill_name}' already loaded"

        # Simulate successful load
        self._loaded_skills[skill_name] = self._manifests.get(skill_name)
        return True, f"Skill '{skill_name}' loaded successfully"

    async def unload_skill(self, skill_name: str) -> tuple[bool, str]:
        """Simulate unloading a skill."""
        if skill_name not in self._loaded_skills:
            return False, f"Skill '{skill_name}' not loaded"

        del self._loaded_skills[skill_name]
        return True, f"Skill '{skill_name}' unloaded"

    def set_load_error(self, skill_name: str, error: str) -> None:
        """Set a load error for a skill."""
        self._load_errors[skill_name] = error

    def clear(self) -> None:
        """Clear all skills."""
        self._available_skills.clear()
        self._loaded_skills.clear()
        self._manifests.clear()
        self._load_errors.clear()


def create_mock_registry() -> FakeSkillRegistry:
    """
    Create a mock skill registry.

    Returns a FakeSkillRegistry instance.

    Usage:
        registry = create_mock_registry()
        registry.add_skill("git", {"name": "git", "version": "1.0.0"})
    """
    return FakeSkillRegistry()
