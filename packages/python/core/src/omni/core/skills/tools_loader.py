"""tools_loader.py - Dynamic Skill Tools Loading Strategy

Uses Foundation V2 @skill_command decorator from omni.foundation.api.decorators.

PEP 420 Namespace Package Support:
- Skills use implicit namespace packages (no __init__.py required)
- Scripts can use absolute imports like 'from git.scripts.commit_state import ...'
- Skills root directory is added to sys.path for proper package resolution

Module Structure:
- ToolsLoader: Main class for loading and managing skill commands
- create_tools_loader(): Factory function for creating loaders
- _skill_command_registry: Global registry for decorated commands (populated by @skill_command)
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.tools_loader")

# Storage for decorator registration - populated by framework
_skill_command_registry: dict[str, dict[str, Any]] = {}


class ToolsLoader:
    """Loads scripts and registers skill commands with auto-wiring support.

    Supports variant scanning for multi-implementation commands:
    - scripts/search.py          # Default implementation
    - scripts/variants/local.py  # Local Python implementation
    - scripts/variants/rust.py   # Rust-accelerated implementation
    """

    VARIANTS_DIR = "variants"

    def __init__(self, scripts_path: str | Path, skill_name: str = "unknown"):
        self.scripts_path = Path(scripts_path)
        self.skill_name = skill_name
        self.commands: dict[str, Callable] = {}
        self.variant_commands: dict[str, dict[str, Callable]] = {}  # command -> {variant -> func}
        self.native_functions: dict[str, Callable] = {}  # Native functions without decorator
        self._context: dict[str, Any] = {}

    def inject(self, key: str, value: Any) -> None:
        """Inject a dependency (e.g., Rust accelerator) into script context."""
        self._context[key] = value
        logger.debug(f"[{self.skill_name}] Injected context: {key}")

    def _register_for_validation(self, full_name: str, cmd: Callable) -> None:
        """Register a command's config in the validation registry for fast-fail validation.

        Args:
            full_name: Full command name (e.g., 'knowledge.ingest_document')
            cmd: The command function with _skill_config attached
        """
        try:
            from omni.core.skills.validation import register_skill_command

            config = getattr(cmd, "_skill_config", None)
            if config and isinstance(config, dict):
                register_skill_command(full_name, config)
        except Exception:
            # Validation module may not be available - silent fail is OK
            pass

    def load_all(self) -> None:
        """Load all scripts and register commands.

        Uses PEP 420 namespace packages:
        - Adds skill root to sys.path for proper package resolution
        - Uses importlib.import_module for full module path loading
        - Enables 'from git.scripts.commit_state import ...' style imports

        Loading Strategy:
        - First load all non-underscore modules (excluding _*.py initially)
        - Then load underscore modules (_*.py) to satisfy internal dependencies
        - This ensures modules with external dependencies load first
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

        # Ensure scripts_path is in sys.path for sibling imports
        # This is critical for 'from git.scripts.commit_state import ...' to work
        scripts_path_str = str(self.scripts_path)
        if scripts_path_str not in sys.path:
            sys.path.insert(0, scripts_path_str)
            paths_added.append(scripts_path_str)

        try:
            # Collect all files first
            all_files: list[Path] = []
            for py_file in self.scripts_path.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                all_files.append(py_file)

            # Separate underscore and non-underscore files
            # Load non-underscore files first, then underscore files
            non_underscore_files = [f for f in all_files if not f.stem.startswith("_")]
            underscore_files = [f for f in all_files if f.stem.startswith("_")]

            # Sort by path depth (shallower first) then alphabetically
            # This ensures base modules load before modules that depend on them
            def depth_then_name(p: Path) -> tuple[int, str]:
                return (len(p.relative_to(self.scripts_path).parts), str(p))

            non_underscore_files.sort(key=depth_then_name)
            underscore_files.sort(key=depth_then_name)

            # Load in order: non-underscore first, then underscore
            ordered_files = non_underscore_files + underscore_files

            for py_file in ordered_files:
                # Calculate relative package name for subdirectories
                rel_path = py_file.relative_to(self.scripts_path)
                pkg_parts = list(rel_path.parent.parts)
                pkg_suffix = ".".join(pkg_parts)
                current_pkg = f"{full_scripts_pkg}.{pkg_suffix}" if pkg_suffix else full_scripts_pkg

                self._load_script(py_file, current_pkg)

            logger.debug(f"[{self.skill_name}] {len(self.commands)} commands")

            # Load variant implementations
            self._load_variants(full_scripts_pkg)

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
            scripts_path_str = str(self.scripts_path)

            for i in range(1, len(parts)):
                parent_pkg = ".".join(parts[:i])
                # Calculate the path for this parent package
                # e.g., "code_tools.scripts.smart_ast" -> scripts_path / "smart_ast"
                # Note: parts[1] is 'scripts' which is already in scripts_path_str
                # so we start from parts[2] (the first subdirectory after scripts)
                parent_parts = parts[2:i]  # Skip skill_name and 'scripts'
                if parent_parts:
                    parent_path = scripts_path_str
                    for part in parent_parts:
                        parent_path = str(Path(parent_path) / part)
                else:
                    parent_path = scripts_path_str

                if parent_pkg not in sys.modules:
                    # Create a dummy namespace package with correct path
                    m = types.ModuleType(parent_pkg)
                    m.__path__ = [parent_path]
                    sys.modules[parent_pkg] = m
                else:
                    # Update existing package's __path__ to include the correct directory
                    parent_mod = sys.modules[parent_pkg]
                    if hasattr(parent_mod, "__path__") and parent_path not in parent_mod.__path__:
                        parent_mod.__path__.append(parent_path)

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
        """Get a command by its full name (e.g., 'git.status').

        Also registers the command's config in the validation registry
        for fast-fail parameter validation.
        """
        cmd = self.commands.get(full_name)
        if cmd is not None:
            self._register_for_validation(full_name, cmd)
        return cmd

    def get_command_simple(self, name: str) -> Callable | None:
        """Get a command by simple name (e.g., 'status').

        Also registers the command's config in the validation registry.
        """
        # Try skill.command format first
        full_name = f"{self.skill_name}.{name}"
        if full_name in self.commands:
            cmd = self.commands[full_name]
            self._register_for_validation(full_name, cmd)
            return cmd
        # Fall back to native functions
        if name in self.native_functions:
            return self.native_functions[name]
        # Fall back to direct match in commands
        cmd = self.commands.get(name)
        if cmd is not None:
            self._register_for_validation(name, cmd)
        return cmd

    def list_commands(self) -> list[str]:
        """List all registered commands."""
        return list(self.commands.keys())

    def list_variants(self, command_name: str) -> list[str]:
        """List available variants for a command."""
        if command_name not in self.variant_commands:
            return []
        return list(self.variant_commands[command_name].keys())

    def get_variant(self, command_name: str, variant_name: str) -> Callable | None:
        """Get a specific variant implementation for a command."""
        if command_name not in self.variant_commands:
            return None
        return self.variant_commands[command_name].get(variant_name)

    def _load_variants(self, scripts_pkg: str) -> None:
        """Load variant implementations from variants/ directory.

        Expected structure:
        scripts/
            variants/
                <command_name>/
                    <variant_name>.py

        Example:
        scripts/variants/code_search/rust.py
        scripts/variants/code_search/local.py
        """
        variants_path = self.scripts_path / self.VARIANTS_DIR
        if not variants_path.exists():
            logger.debug(f"[{self.skill_name}] No variants directory found: {variants_path}")
            return

        # Find all variant directories
        for command_dir in variants_path.iterdir():
            if not command_dir.is_dir():
                continue

            command_name = command_dir.name
            if command_name.startswith("_"):
                continue

            # Find variant implementations
            for variant_file in command_dir.glob("*.py"):
                if variant_file.stem.startswith("_"):
                    continue

                variant_name = variant_file.stem
                module_name = f"{command_name}_{variant_name}"
                full_module_name = (
                    f"{scripts_pkg}.{self.VARIANTS_DIR}.{command_dir.name}.{variant_file.stem}"
                )

                try:
                    self._load_variant_script(
                        variant_file,
                        scripts_pkg,
                        command_name,
                        variant_name,
                        module_name,
                        full_module_name,
                    )
                except Exception as e:
                    logger.debug(
                        f"[{self.skill_name}] Failed to load variant {command_name}/{variant_name}: {e}"
                    )

        logger.debug(
            f"[{self.skill_name}] Loaded {sum(len(v) for v in self.variant_commands.values())} variants"
        )

    def _load_variant_script(
        self,
        path: Path,
        scripts_pkg: str,
        command_name: str,
        variant_name: str,
        module_name: str,
        full_module_name: str,
    ) -> None:
        """Load a single variant script."""
        import importlib.util
        import types

        try:
            # Ensure parent package exists
            parent_pkg = f"{scripts_pkg}.{self.VARIANTS_DIR}.{path.parent.name}"
            if parent_pkg not in sys.modules:
                m = types.ModuleType(parent_pkg)
                m.__path__ = [str(path.parent)]
                sys.modules[parent_pkg] = m

            # Load the module
            spec = importlib.util.spec_from_file_location(full_module_name, path)
            if not (spec and spec.loader):
                return

            module = importlib.util.module_from_spec(spec)
            module.__package__ = scripts_pkg

            # Inject context
            for key, value in self._context.items():
                setattr(module, key, value)
            module.skill_name = self.skill_name

            # Execute
            sys.modules[full_module_name] = module
            spec.loader.exec_module(module)

            # Harvest @skill_command functions
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)

                if hasattr(attr, "_is_skill_command") and attr._is_skill_command:
                    config = getattr(attr, "_skill_config", {})
                    config["variant"] = variant_name
                    config["variant_source"] = str(path)

                    # Store in variant_commands
                    if command_name not in self.variant_commands:
                        self.variant_commands[command_name] = {}

                    full_name = f"{self.skill_name}.{command_name}.{variant_name}"
                    self.variant_commands[command_name][variant_name] = attr
                    logger.debug(
                        f"[{self.skill_name}] Loaded variant: {command_name}/{variant_name}"
                    )

        except Exception as e:
            logger.debug(f"[{self.skill_name}] Failed to load variant script {path}: {e}")
            if full_module_name in sys.modules:
                del sys.modules[full_module_name]

    def __len__(self) -> int:
        return len(self.commands)

    def __contains__(self, name: str) -> bool:
        return name in self.commands or f"{self.skill_name}.{name}" in self.commands


def create_tools_loader(scripts_path: str | Path, skill_name: str) -> ToolsLoader:
    """Factory function to create a ToolsLoader with proper initialization."""
    return ToolsLoader(scripts_path, skill_name)
