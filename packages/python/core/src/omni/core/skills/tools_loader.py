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

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import get_logger

from .tools_loader_index import build_rust_command_index
from .tools_loader_paths import (
    cleanup_namespace_paths,
    iter_script_files,
    prepare_namespace_paths,
    scripts_pkg_for_file,
)
from .tools_loader_script_loading import load_script
from .tools_loader_validation import register_command_for_validation
from .tools_loader_variants import load_variants

logger = get_logger("omni.core.tools_loader")

if TYPE_CHECKING:
    from collections.abc import Callable

# Storage for decorator registration - populated by framework
_skill_command_registry: dict[str, dict[str, Any]] = {}


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        pass


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
        self._command_index: dict[str, list[Path]] | None = None
        self.allow_module_reuse = False

    def inject(self, key: str, value: Any) -> None:
        """Inject a dependency (e.g., Rust accelerator) into script context."""
        self._context[key] = value
        logger.debug(f"[{self.skill_name}] Injected context: {key}")

    def set_allow_module_reuse(self, enabled: bool) -> None:
        """Enable/disable module reuse when scripts are reloaded in same process."""
        self.allow_module_reuse = bool(enabled)

    def _prepare_namespace_paths(self) -> tuple[list[str], str]:
        """Prepare sys.path for namespace-package script loading."""
        return prepare_namespace_paths(self.scripts_path, self.skill_name)

    def _cleanup_namespace_paths(self, paths_added: list[str]) -> None:
        """Remove sys.path entries added by _prepare_namespace_paths()."""
        cleanup_namespace_paths(paths_added)

    def _iter_script_files(self) -> list[Path]:
        """Return all script files in deterministic dependency-friendly order."""
        return iter_script_files(self.scripts_path)

    def _build_command_index(self) -> dict[str, list[Path]]:
        """Build command->script index from Rust scanner (single source of truth)."""
        if self._command_index is not None:
            return self._command_index

        index = build_rust_command_index(self.skill_name, self.scripts_path)
        self._command_index = index
        return index

    def _scripts_pkg_for_file(self, py_file: Path, full_scripts_pkg: str) -> str:
        """Compute scripts package path for one file."""
        return scripts_pkg_for_file(py_file, self.scripts_path, full_scripts_pkg)

    def _register_for_validation(self, full_name: str, cmd: Callable) -> None:
        """Register a command's config in the validation registry for fast-fail validation.

        Args:
            full_name: Full command name (e.g., 'knowledge.ingest_document')
            cmd: The command function with _skill_config attached
        """
        register_command_for_validation(full_name, cmd)

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

        self._command_index = None
        paths_added, full_scripts_pkg = self._prepare_namespace_paths()

        try:
            for py_file in self._iter_script_files():
                load_script(
                    py_file,
                    self._scripts_pkg_for_file(py_file, full_scripts_pkg),
                    skill_name=self.skill_name,
                    scripts_path=self.scripts_path,
                    context=self._context,
                    commands=self.commands,
                    logger=logger,
                    allow_module_reuse=self.allow_module_reuse,
                )

            logger.debug(f"[{self.skill_name}] {len(self.commands)} commands")

            load_variants(
                scripts_path=self.scripts_path,
                scripts_pkg=full_scripts_pkg,
                skill_name=self.skill_name,
                variants_dir=self.VARIANTS_DIR,
                context=self._context,
                variant_commands=self.variant_commands,
                logger=logger,
            )

        finally:
            self._cleanup_namespace_paths(paths_added)

    def load_command(self, command_name: str) -> bool:
        """Load only modules needed by one command (best effort).

        Returns:
            True if the command is available after targeted load, else False.
        """
        if not self.scripts_path.exists():
            logger.debug(f"Scripts path does not exist: {self.scripts_path}")
            return False

        target = command_name.strip()
        skill_prefix = f"{self.skill_name}."
        if target.startswith(skill_prefix):
            target = target[len(skill_prefix) :]
        if not target:
            return False

        self._command_index = None
        paths_added, full_scripts_pkg = self._prepare_namespace_paths()
        loaded_files = 0
        try:
            index = self._build_command_index()
            candidates = index.get(target, [])
            if not candidates:
                logger.debug(
                    f"[{self.skill_name}] Targeted load missed: no Rust record for {target}"
                )
                return False

            seen: set[Path] = set()
            ordered: list[Path] = []
            for py_file in candidates:
                if py_file in seen:
                    continue
                seen.add(py_file)
                ordered.append(py_file)

            for py_file in ordered:
                module_started = time.perf_counter()
                loaded_count, reused = load_script(
                    py_file,
                    self._scripts_pkg_for_file(py_file, full_scripts_pkg),
                    skill_name=self.skill_name,
                    scripts_path=self.scripts_path,
                    context=self._context,
                    commands=self.commands,
                    logger=logger,
                    allow_module_reuse=self.allow_module_reuse,
                )
                _record_phase(
                    "runner.fast.load.module",
                    (time.perf_counter() - module_started) * 1000,
                    skill=self.skill_name,
                    module=str(py_file.name),
                    command_count=loaded_count,
                    reused=reused,
                    target=target,
                )
                loaded_files += 1

            full_name = f"{self.skill_name}.{target}"
            found = full_name in self.commands or target in self.commands
            logger.debug(
                f"[{self.skill_name}] Targeted load {'hit' if found else 'miss'}: "
                f"target={target} files={loaded_files} commands={len(self.commands)}"
            )
            return found
        finally:
            self._cleanup_namespace_paths(paths_added)

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

    def __len__(self) -> int:
        return len(self.commands)

    def __contains__(self, name: str) -> bool:
        return name in self.commands or f"{self.skill_name}.{name}" in self.commands


def create_tools_loader(scripts_path: str | Path, skill_name: str) -> ToolsLoader:
    """Factory function to create a ToolsLoader with proper initialization."""
    return ToolsLoader(scripts_path, skill_name)
