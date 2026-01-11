"""
src/agent/core/skill_manager/loader.py
Skill loading and command extraction.

Contains:
- Command extraction from @skill_command decorated functions
- Module loading utilities
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

from ..module_loader import ModuleLoader
from ..protocols import SkillCategory
from .models import SkillCommand


class SkillLoaderMixin:
    """
    Mixin providing skill loading and command extraction capabilities.

    Used by SkillManager to extract commands from skill modules.
    """

    # These should be defined in the parent class
    _module_loader: ModuleLoader | None
    skills_dir: Path
    _SKILL_COMMAND_MARKER: str

    def _get_module_loader(self) -> ModuleLoader:
        """Get or create the module loader."""
        if self._module_loader is None:
            self._module_loader = ModuleLoader(self.skills_dir)
            self._module_loader._ensure_parent_packages()
            self._module_loader._preload_decorators()
        return self._module_loader

    def _extract_commands(self, module: Any, skill_name: str) -> dict[str, SkillCommand]:
        """Extract @skill_command decorated functions from a module."""
        commands: dict[str, SkillCommand] = {}

        for name, obj in inspect.getmembers(module):
            if not inspect.isfunction(obj):
                continue

            if not hasattr(obj, self._SKILL_COMMAND_MARKER):
                continue

            # Get config from decorator
            config = getattr(obj, "_skill_config", {})
            cmd_name = config.get("name") or name
            description = config.get("description", "") or self._get_docstring(obj)
            category = config.get("category", "general")

            commands[cmd_name] = SkillCommand(
                name=cmd_name,
                func=obj,
                description=description,
                category=SkillCategory(category),
                _skill_name=skill_name,
            )

        return commands

    def _get_docstring(self, func: Callable) -> str:
        """Extract first line of docstring."""
        if func.__doc__:
            first_line = func.__doc__.strip().split("\n")[0]
            return first_line.strip()
        return ""

    def _rebuild_command_cache(self, skill_name: str, commands: dict[str, SkillCommand]) -> None:
        """Rebuild command cache for a skill (O(n) but only on load)."""
        for cmd_name, cmd in commands.items():
            # Register both "skill.command" and "command" formats
            full_name = f"{skill_name}.{cmd_name}"
            self._command_cache[full_name] = cmd

            # Also register without skill prefix (e.g., "read_file" from "file.read")
            self._command_cache[cmd_name] = cmd


__all__ = [
    "SkillLoaderMixin",
]
