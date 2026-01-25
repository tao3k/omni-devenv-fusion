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
            for py_file in self.scripts_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                self._load_script(py_file, full_scripts_pkg)

            logger.debug(f"[{self.skill_name}] {len(self.commands)} commands")
        finally:
            # Clean up sys.path
            for path in paths_added:
                if path in sys.path:
                    sys.path.remove(path)

    def _load_script(self, path: Path, scripts_pkg: str) -> None:
        """Load a single script file using importlib.

        Args:
            path: Path to the .py file
            scripts_pkg: Full package path (e.g., "git.scripts")
        """
        module_name = path.stem
        full_module_name = f"{scripts_pkg}.{module_name}"  # e.g., "git.scripts.commit_state"

        # Clear cached module to ensure fresh load (hot reload support)
        if full_module_name in sys.modules:
            del sys.modules[full_module_name]

        try:
            # Try import_module first for PEP 420 namespace packages
            try:
                module = importlib.import_module(full_module_name)
            except ModuleNotFoundError:
                # Fall back to direct file import when skill name conflicts with pip package
                # (e.g., crawl4ai skill vs crawl4ai pip package)
                spec = importlib.util.spec_from_file_location(full_module_name, path)
                if spec is None or spec.loader is None:
                    logger.debug(f"[{self.skill_name}] Cannot load spec for {path}")
                    return
                module = importlib.util.module_from_spec(spec)
                sys.modules[full_module_name] = module
                spec.loader.exec_module(module)

            # Inject context into module globals
            # Scripts can use 'rust' directly without importing
            for key, value in self._context.items():
                setattr(module, key, value)

            # Add skill_name for decorator registration
            module.skill_name = self.skill_name

            # Scan for @skill_command decorated functions AND native functions
            # Only process functions defined in THIS module (not imported from elsewhere)
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(module, attr_name)
                if not inspect.isfunction(attr):
                    continue

                # Skip functions imported from other modules
                # Check if function's __module__ matches current module's name
                func_module = getattr(attr, "__module__", None)
                if func_module is not None and func_module != full_module_name:
                    continue

                if getattr(attr, "_is_skill_command", False):
                    # Registered command with decorator
                    attr._skill_name = self.skill_name
                    # Support both V1 (_command_name) and V2 (_skill_config["name"]) decorators
                    config = getattr(attr, "_skill_config", {})
                    if config and "name" in config:
                        cmd_name = config["name"]
                    else:
                        cmd_name = getattr(attr, "_command_name", attr_name)
                    full_name = f"{self.skill_name}.{cmd_name}"
                    # Only register if not already registered (prevent duplicate from imports)
                    if full_name not in self.commands:
                        self.commands[full_name] = attr
                        logger.debug(f"[{self.skill_name}] Registered command: {full_name}")
                elif not attr_name.startswith("_"):
                    # Native function (no decorator) - still useful for direct routing
                    # Only register if not already registered
                    if attr_name not in self.native_functions:
                        self.native_functions[attr_name] = attr
                        logger.debug(f"[{self.skill_name}] Native function: {attr_name}")

        except Exception as e:
            # Script loading is best-effort - log at debug level
            logger.debug(f"[{self.skill_name}] Failed to load script {full_module_name}: {e}")

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
