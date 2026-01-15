"""
src/agent/core/skill_manager/loader.py
Skill loading and command extraction.

Phase 63: Only supports scripts/*.py pattern with @skill_script decorator.
Removes legacy tools.py + @skill_command support.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Callable

from ..module_loader import ModuleLoader
from ..protocols import SkillCategory
from .models import SkillCommand


class SkillLoaderMixin:
    """
    Mixin providing skill loading and command extraction capabilities.

    Phase 63: Only supports scripts/*.py with @skill_script decorator.
    Legacy tools.py + @skill_command support has been removed.
    """

    # These should be defined in the parent class
    _module_loader: ModuleLoader | None
    skills_dir: Path

    def _get_module_loader(self) -> ModuleLoader:
        """Get or create the module loader."""
        if self._module_loader is None:
            self._module_loader = ModuleLoader(self.skills_dir)
            self._module_loader._ensure_parent_packages()
            self._module_loader._preload_decorators()
        return self._module_loader

    def _extract_script_commands(
        self,
        module: Any,
        skill_name: str,
    ) -> dict[str, SkillCommand]:
        """Extract @skill_script decorated functions from a script module.

        Args:
            module: The loaded Python module (from scripts/*.py)
            skill_name: Name of the parent skill (e.g., "git")

        Returns:
            Dict mapping command name -> SkillCommand
        """
        commands: dict[str, SkillCommand] = {}

        for name, obj in inspect.getmembers(module):
            if not inspect.isfunction(obj):
                continue

            # Check for @skill_script marker
            if not hasattr(obj, "_is_skill_script"):
                continue

            # Get config from decorator
            config = getattr(obj, "_script_config", {})
            cmd_name = config.get("name") or name
            description = config.get("description", "") or self._get_docstring(obj)
            category = config.get("category", "general")
            input_schema = config.get("input_schema", {})
            inject_root = config.get("inject_root", False)
            inject_settings = config.get("inject_settings", [])
            retry_on = config.get("retry_on", (ConnectionError, TimeoutError))
            max_attempts = config.get("max_attempts", 3)

            commands[cmd_name] = SkillCommand(
                name=cmd_name,
                func=obj,
                description=description,
                category=SkillCategory(category),
                _skill_name=skill_name,
                input_schema=input_schema,
                _script_mode=True,
                _inject_root=inject_root,
                _inject_settings=inject_settings,
                _retry_on=retry_on,
                _max_attempts=max_attempts,
            )

        return commands

    def _load_script_module(self, skill_name: str, script_file: Path) -> Any:
        """Dynamically load a script module.

        Args:
            skill_name: Name of the skill (e.g., "git")
            script_file: Path to the script file (e.g., commit.py)

        Returns:
            The loaded Python module
        """
        # Create module name: agent.skills.git.scripts.commit
        module_name = f"agent.skills.{skill_name}.scripts.{script_file.stem}"
        package_name = f"agent.skills.{skill_name}.scripts"
        parent_package = f"agent.skills.{skill_name}"

        # Check if already loaded
        if module_name in sys.modules:
            return sys.modules[module_name]

        # Ensure parent package is in sys.modules for relative imports
        if parent_package not in sys.modules:
            parent_spec = importlib.util.spec_from_file_location(
                parent_package,
                self.skills_dir / skill_name / "__init__.py",
            )
            if parent_spec:
                parent_module = importlib.util.module_from_spec(parent_spec)
                sys.modules[parent_package] = parent_module

        # Also ensure scripts package is registered for .utils style imports
        if package_name not in sys.modules:
            scripts_init = self.skills_dir / skill_name / "scripts" / "__init__.py"
            if scripts_init.exists():
                package_spec = importlib.util.spec_from_file_location(
                    package_name,
                    scripts_init,
                )
                if package_spec:
                    package_module = importlib.util.module_from_spec(package_spec)
                    package_module.__path__ = [str(scripts_init.parent)]
                    sys.modules[package_name] = package_module

        # Use importlib to load the module
        spec = importlib.util.spec_from_file_location(
            module_name,
            script_file,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {script_file}")

        module = importlib.util.module_from_spec(spec)

        # Set up package context for relative imports (e.g., from .utils import ...)
        module.__package__ = package_name
        module.__file__ = str(script_file)

        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    def _extract_commands_from_scripts(
        self,
        skill_name: str,
        scripts_dir: Path,
    ) -> dict[str, SkillCommand]:
        """Extract all @skill_script commands from a skill's scripts directory.

        Args:
            skill_name: Name of the skill
            scripts_dir: Path to the scripts directory

        Returns:
            Dict mapping command name -> SkillCommand
        """
        commands: dict[str, SkillCommand] = {}

        if not scripts_dir.exists():
            return commands

        # Find all Python files (excluding __init__.py)
        for script_file in scripts_dir.glob("*.py"):
            if script_file.name.startswith("_"):
                continue

            try:
                module = self._load_script_module(skill_name, script_file)
                script_commands = self._extract_script_commands(module, skill_name)

                # Merge script commands (no prefix - _rebuild_command_cache handles that)
                commands.update(script_commands)

            except Exception as e:
                # Log but continue - one broken script shouldn't fail the whole skill
                import logging

                logging.getLogger(__name__).warning(f"Failed to load script {script_file}: {e}")

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
