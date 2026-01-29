"""script_loader.py - Dynamic Skill Loading Strategy

Uses Foundation V2 @skill_command decorator from omni.foundation.api.decorators.
V1 decorator has been removed - migrate to V2.

PEP 420 Namespace Package Support:
- Skills use implicit namespace packages (no __init__.py required)
- Scripts can use absolute imports like 'from git.scripts.commit_state import ...'
- Skills root directory is added to sys.path for proper package resolution
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.script_loader")

# Storage for decorator registration - populated by framework
_skill_command_registry: dict[str, dict[str, Any]] = {}


class ScriptLoader:
    """Loads scripts and registers skill commands with auto-wiring support."""

    def __init__(self, scripts_path: str | Path, skill_name: str = "unknown"):
        self.scripts_path = Path(scripts_path)
        self.skill_name = skill_name
        self.commands: dict[str, Callable] = {}
        self.native_functions: dict[str, Callable] = {}  # Native functions without decorator
        self._context: dict[str, Any] = {}

    def inject(self, key: str, value: Any) -> None:
        """Inject a dependency (e.g., Rust accelerator) into script context."""
        self._context[key] = value
        logger.debug(f"[{self.skill_name}] Injected context: {key}")

    def load_all(self) -> None:
        """Load all scripts and register commands.

        Uses PEP 420 namespace packages:
        - Adds skill root to sys.path for proper package resolution
        - Uses importlib.import_module for full module path loading
        - Enables 'from git.scripts.commit_state import ...' style imports
        """
        if not self.scripts_path.exists():
            logger.debug(f"Scripts path does not exist: {self.scripts_path}")
            return

        # PEP 420: Add parent of skill root to sys.path for namespace package resolution
        # This allows 'from git.scripts.commit_state import ...' to work
        # For real skills: assets/skills/git/scripts -> parent is assets/skills
        # For tests: tmp/scripted_skill/scripts -> parent is tmp
        skill_root = self.scripts_path.parent
        parent_of_skill = str(skill_root.parent)

        paths_added: list[str] = []
        if parent_of_skill not in sys.path:
            sys.path.insert(0, parent_of_skill)
            paths_added.append(parent_of_skill)

        # Also ensure the skill_root itself is accessible
        if str(skill_root) not in sys.path:
            sys.path.insert(0, str(skill_root))
            paths_added.append(str(skill_root))

        # Full module path for this skill's scripts (e.g., "git.scripts")
        full_scripts_pkg = f"{self.skill_name}.scripts"

        try:
            # Recursive scan for all .py files in scripts/ and subdirectories
            for py_file in self.scripts_path.rglob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                # Calculate relative package name for subdirectories
                rel_path = py_file.relative_to(self.scripts_path)
                pkg_parts = list(rel_path.parent.parts)
                pkg_suffix = ".".join(pkg_parts)
                current_pkg = f"{full_scripts_pkg}.{pkg_suffix}" if pkg_suffix else full_scripts_pkg

                self._load_script(py_file, current_pkg)

            logger.debug(f"[{self.skill_name}] {len(self.commands)} commands")
        finally:
            # Clean up sys.path
            for path in paths_added:
                if path in sys.path:
                    sys.path.remove(path)

    def _load_script(self, path: Path, scripts_pkg: str) -> None:
        """Load a single script file using a robust modular strategy."""
        import importlib.util
        import types

        module_name = path.stem
        # Construct the full internal package path, e.g. "skill.scripts.subdir.module"
        full_module_name = f"{scripts_pkg}.{module_name}"

        try:
            # 1. Ensure the parent packages exist in sys.modules (Fundamental Fix)
            # This is required for relative imports to work in PEP 420 namespace packages.
            parts = full_module_name.split(".")
            for i in range(1, len(parts)):
                parent_pkg = ".".join(parts[:i])
                if parent_pkg not in sys.modules:
                    # Create a dummy namespace package
                    m = types.ModuleType(parent_pkg)
                    m.__path__ = []  # Mark as package
                    sys.modules[parent_pkg] = m

            # 2. Load the actual module
            spec = importlib.util.spec_from_file_location(full_module_name, path)
            if not (spec and spec.loader):
                return

            module = importlib.util.module_from_spec(spec)

            # 3. Critical Metadata for Relative Imports
            module.__package__ = ".".join(parts[:-1])

            # 4. Inject Search Path for sibling discovery
            script_dir = str(path.parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            sys.modules[full_module_name] = module

            # 5. Inject Foundation Context
            for key, value in self._context.items():
                setattr(module, key, value)
            module.skill_name = self.skill_name

            # 6. Execute
            spec.loader.exec_module(module)

            # 7. Harvest @skill_command functions
            count = 0
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)

                if hasattr(attr, "_is_skill_command") and attr._is_skill_command:
                    config = getattr(attr, "_skill_config", {})
                    cmd_name = (
                        config.get("name") if config else getattr(attr, "_command_name", attr_name)
                    )

                    full_name = f"{self.skill_name}.{cmd_name}"
                    self.commands[full_name] = attr
                    count += 1

            if count > 0:
                logger.debug(f"[{self.skill_name}] Modular load success: {full_name}")

        except Exception as e:
            logger.debug(f"[{self.skill_name}] Modular load failed for {path}: {e}")
            # Clean up if failed to prevent poisoned imports
            if full_module_name in sys.modules:
                del sys.modules[full_module_name]

    def get_command(self, full_name: str) -> Callable | None:
        """Get a command by its full name (e.g., 'git.status')."""
        return self.commands.get(full_name)

    def get_command_simple(self, name: str) -> Callable | None:
        """Get a command by simple name (e.g., 'status')."""
        # Try skill.command format first
        full_name = f"{self.skill_name}.{name}"
        if full_name in self.commands:
            return self.commands[full_name]
        # Fall back to native functions
        if name in self.native_functions:
            return self.native_functions[name]
        # Fall back to direct match in commands
        return self.commands.get(name)

    def list_commands(self) -> list[str]:
        """List all registered commands."""
        return list(self.commands.keys())

    def __len__(self) -> int:
        return len(self.commands)

    def __contains__(self, name: str) -> bool:
        return name in self.commands or f"{self.skill_name}.{name}" in self.commands


class SkillScriptLoader(ScriptLoader):
    """Backward-compatible alias for ScriptLoader."""

    @override
    def __init__(self, scripts_path: str | Path):
        # Will be initialized with skill_name later
        super().__init__(scripts_path, skill_name="unknown")


def create_script_loader(scripts_path: str | Path, skill_name: str) -> ScriptLoader:
    """Factory function to create a ScriptLoader with proper initialization."""
    loader = ScriptLoader(scripts_path, skill_name)
    return loader
