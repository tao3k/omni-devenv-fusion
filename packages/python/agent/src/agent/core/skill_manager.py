"""
agent/core/skill_manager.py
Phase 29: Unified Skill Manager (Refactored)

Trinity Architecture with Protocol-based design:
- Code: Hot-reloading via ModuleLoader
- Context: RepomixCache for skill understanding
- State: Protocol-based registry

Key improvements:
- Protocol-based for testability
- Slots on all DTOs
- Consistent structlog logging
- Clean separation of concerns
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar

import structlog
from common.mcp_core.lazy_cache import RepomixCache

from .protocols import (
    ExecutionMode,
    ExecutionResult,
    ISkill,
    ISkillLoader,
    SkillCategory,
    SkillInfo,
)
from .module_loader import ModuleLoader, module_loader

if TYPE_CHECKING:
    from .protocols import SkillManifest

logger = structlog.get_logger(__name__)

# Default skills directory
SKILLS_DIR_PATH: str = "assets/skills"


# =============================================================================
# Command Implementation
# =============================================================================


@dataclass(slots=True)
class SkillCommand:
    """
    A single command exposed by a skill.

    Implements ISkillCommand protocol for type-safe access.
    """

    name: str
    func: Callable[..., Any]
    description: str = ""
    category: str = "general"
    _skill_name: str = ""

    def __post_init__(self) -> None:
        """Normalize category to enum."""
        if isinstance(self.category, str):
            object.__setattr__(self, "category", SkillCategory(self.category))

    async def execute(self, args: dict[str, Any]) -> ExecutionResult:
        """Execute the command with arguments."""
        import time

        t0 = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(**args)
            else:
                result = self.func(**args)

            return ExecutionResult(
                success=True,
                output=str(result),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )


# =============================================================================
# Skill Implementation
# =============================================================================


@dataclass(slots=True)
class Skill(ISkill):
    """
    A loaded skill with commands and context.

    Implements ISkill protocol for interchangeability.
    """

    name: str
    manifest: "SkillManifest"
    commands: dict[str, SkillCommand] = field(default_factory=dict)
    module_name: str = ""
    path: Path | None = None
    mtime: float = 0.0
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY
    context_cache: RepomixCache | None = None
    _module: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.execution_mode, str):
            self.execution_mode = ExecutionMode(self.execution_mode)

    def get_command(self, name: str) -> ISkillCommand | None:
        """Get a specific command by name."""
        return self.commands.get(name)

    async def load(self) -> None:
        """Load is handled by SkillManager during registration."""
        pass

    async def unload(self) -> None:
        """Cleanup resources."""
        self.commands.clear()
        self._module = None


# =============================================================================
# Skill Manager (Facade + Loader)
# =============================================================================


class SkillManager:
    """
    Central skill manager with Trinity Architecture.

    Responsibilities:
    - Discover and load skills
    - Hot-reload on file changes
    - Execute commands
    - Provide skill context

    Design:
    - Protocol-based for testability
    - Uses ModuleLoader for clean imports
    - Slots on all internal state
    """

    __slots__ = (
        "skills_dir",
        "_skills",
        "_module_loader",
        "_loaded",
        "_preload_done",
    )

    # Registry marker for @skill_command decorated functions
    _SKILL_COMMAND_MARKER: ClassVar[str] = "_is_skill_command"

    def __init__(self, skills_dir: Path | None = None) -> None:
        """
        Initialize the skill manager.

        Args:
            skills_dir: Path to skills directory (default: assets/skills)
        """
        from common.config_paths import get_project_root
        from common.settings import get_setting

        if skills_dir is None:
            base = get_project_root()
            skills_path = get_setting("skills.path", SKILLS_DIR_PATH)
            self.skills_dir = base / skills_path
        else:
            self.skills_dir = Path(skills_dir)

        self._skills: dict[str, Skill] = {}
        self._module_loader: ModuleLoader | None = None
        self._loaded = False
        self._preload_done = False

    # =========================================================================
    # Properties (for backward compatibility with tests)
    # =========================================================================

    @property
    def skills(self) -> dict[str, Skill]:
        """Backward-compatible access to skills dict."""
        return self._skills

    # =========================================================================
    # Discovery
    # =========================================================================

    def discover(self) -> list[Path]:
        """Discover all skill directories in the skills folder."""
        if not self.skills_dir.exists():
            logger.warning("Skills directory not found", path=str(self.skills_dir))
            return []

        skills: list[Path] = []
        for entry in self.skills_dir.iterdir():
            if entry.is_dir() and (entry / "manifest.json").exists():
                tools_path = entry / "tools.py"
                if tools_path.exists():
                    skills.append(entry)
                else:
                    logger.debug("Skipping - no tools.py", skill=entry.name)

        logger.info("Discovered skills", count=len(skills))
        return skills

    def _discover_single(self, skill_name: str) -> Path | None:
        """Discover a single skill by name."""
        skill_path = self.skills_dir / skill_name
        if skill_path.exists() and (skill_path / "manifest.json").exists():
            return skill_path
        return None

    # =========================================================================
    # Loading
    # =========================================================================

    def _get_module_loader(self) -> ModuleLoader:
        """Get or create the module loader."""
        if self._module_loader is None:
            self._module_loader = ModuleLoader(self.skills_dir)
            self._module_loader._ensure_parent_packages()
            self._module_loader._preload_decorators()
        return self._module_loader

    def load_skill(self, skill_path: Path, *, reload: bool = False) -> Skill | None:
        """
        Load a skill from a path.

        Args:
            skill_path: Path to the skill directory
            reload: If True, force reload even if already loaded

        Returns:
            Skill instance or None if loading failed
        """
        skill_name = skill_path.name

        # Check if already loaded (skip reload check for initial load)
        if not reload and skill_name in self._skills:
            return self._skills[skill_name]

        # Load manifest
        manifest = self._load_manifest(skill_path)
        if manifest is None:
            logger.error("No manifest found", skill=skill_name)
            return None

        # Check execution mode
        execution_mode = manifest.get("execution_mode", "library")
        if isinstance(execution_mode, str):
            execution_mode = ExecutionMode(execution_mode)

        # Load module
        tools_path = skill_path / "tools.py"
        module_name = f"agent.skills.{skill_name}.tools"

        try:
            # Use ModuleLoader directly
            loader = ModuleLoader(self.skills_dir)
            loader._ensure_parent_packages()
            # Preload decorators for @skill_command support (if available)
            loader._preload_decorators()
            module = loader.load_module(module_name, tools_path, reload=reload)
        except Exception as e:
            logger.error("Failed to load module", skill=skill_name, error=str(e))
            return None

        # Extract commands
        commands = self._extract_commands(module, skill_name)
        if not commands:
            logger.warning("No commands found in skill", skill=skill_name)
            # Not an error - some skills might be pure data

        # Create context cache
        config_path = skill_path / "repomix.json"
        if not config_path.exists():
            config_path = None

        context_cache = RepomixCache(
            target_path=skill_path,
            config_path=config_path,
        )

        # Get mtime for hot-reload
        try:
            mtime = tools_path.stat().st_mtime
        except FileNotFoundError:
            mtime = 0.0

        # Create skill
        skill = Skill(
            name=skill_name,
            manifest=manifest,
            commands=commands,
            module_name=module_name,
            path=tools_path,
            mtime=mtime,
            execution_mode=execution_mode,
            context_cache=context_cache,
            _module=module,
        )

        self._skills[skill_name] = skill
        logger.info(
            "Skill loaded",
            skill=skill_name,
            commands=len(commands),
            mode=execution_mode.value,
        )

        return skill

    def _load_manifest(self, skill_path: Path) -> dict[str, Any] | None:
        """Load manifest.json for a skill."""
        manifest_path = skill_path / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            return json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            logger.error("Invalid manifest", skill=skill_path.name, error=str(e))
            return None

    def _extract_commands(self, module: Any, skill_name: str) -> dict[str, SkillCommand]:
        """Extract @skill_command decorated functions from a module."""
        import inspect

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

    # =========================================================================
    # Hot Reload
    # =========================================================================

    def _ensure_fresh(self, skill_name: str) -> bool:
        """Check and reload skill if modified (hot-reload)."""
        skill_path = self._discover_single(skill_name)
        if skill_path is None:
            logger.debug("Skill not found on disk", skill=skill_name)
            return False

        if skill_name not in self._skills:
            return self.load_skill(skill_path) is not None

        skill = self._skills[skill_name]
        tools_path = skill_path / "tools.py"

        try:
            current_mtime = tools_path.stat().st_mtime
            if current_mtime > skill.mtime:
                logger.info("Hot-reloading skill", skill=skill_name)
                return self.load_skill(skill_path, reload=True) is not None
        except FileNotFoundError:
            logger.warning("Skill file deleted", skill=skill_name)

        return True

    # =========================================================================
    # Execution
    # =========================================================================

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """
        Execute a skill command.

        Args:
            skill_name: Name of the skill
            command_name: Name of the command
            args: Arguments for the command

        Returns:
            Command output as string
        """
        # Handle special "help" command
        if command_name == "help":
            return self._get_skill_context(skill_name)

        # Ensure skill is fresh
        if not self._ensure_fresh(skill_name):
            return f"Error: Skill '{skill_name}' not found"

        skill = self._skills.get(skill_name)
        if skill is None:
            return f"Error: Skill '{skill_name}' not loaded"

        # Get command
        command = skill.commands.get(command_name)
        if command is None:
            # Try alternate naming (skill_command vs just command)
            alt_name = f"{skill_name}_{command_name}"
            command = skill.commands.get(alt_name)

        if command is None:
            available = list(skill.commands.keys())
            return f"Error: Command '{command_name}' not found in '{skill_name}'. Available: {available}"

        # Execute
        args = args or {}
        result = await command.execute(args)

        if result.success:
            return result.output
        else:
            return f"Error: {result.error}"

    def _get_skill_context(self, skill_name: str) -> str:
        """Get skill context via Repomix."""
        if not self._ensure_fresh(skill_name):
            return f"Skill '{skill_name}' not found"

        skill = self._skills.get(skill_name)
        if skill is None:
            return f"Skill '{skill_name}' not found"

        if skill.context_cache is None:
            return f"No context available for '{skill_name}'"

        return skill.context_cache.get() or f"# {skill_name}\n\nNo context available."

    # =========================================================================
    # Query Interface
    # =========================================================================

    def list_available(self) -> list[str]:
        """List all discovered skills."""
        return [p.name for p in self.discover()]

    def list_loaded(self) -> list[str]:
        """List all loaded skills."""
        return list(self._skills.keys())

    def get_info(self, skill_name: str) -> dict[str, Any] | None:
        """Get info about a loaded skill (returns dict for backward compatibility)."""
        if not self._ensure_fresh(skill_name):
            return None

        skill = self._skills.get(skill_name)
        if skill is None:
            return None

        return {
            "name": skill.name,
            "version": skill.manifest.get("version", "unknown"),
            "description": skill.manifest.get("description", ""),
            "command_count": len(skill.commands),
            "execution_mode": skill.execution_mode.value
            if hasattr(skill.execution_mode, "value")
            else skill.execution_mode,
            "commands": list(skill.commands.keys()),
            "loaded": True,
            "manifest": skill.manifest,
        }

    def get_commands(self, skill_name: str) -> list[str]:
        """Get command names for a skill."""
        if not self._ensure_fresh(skill_name):
            return []

        skill = self._skills.get(skill_name)
        if skill is None:
            return []

        return list(skill.commands.keys())

    # =========================================================================
    # Aliases for backward compatibility with tests
    # =========================================================================

    # Aliases for method names used in tests
    list_available_skills = list_available
    list_commands = get_commands
    get_skill_info = get_info

    def get_command(self, skill_name: str, command_name: str) -> "SkillCommand | None":
        """Get a specific command from a skill (for backward compatibility)."""
        if not self._ensure_fresh(skill_name):
            return None

        skill = self._skills.get(skill_name)
        if skill is None:
            return None

        return skill.commands.get(command_name)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def load_all(self, preload: bool = True) -> dict[str, Skill]:
        """
        Load all discovered skills.

        Args:
            preload: If True, load all at once; otherwise lazy load

        Returns:
            Dictionary of loaded skills
        """
        if self._loaded:
            logger.debug("Skills already loaded")
            return self._skills

        skill_paths = self.discover()
        for path in skill_paths:
            self.load_skill(path)

        self._loaded = True
        logger.info("All skills loaded", count=len(self._skills))
        return self._skills

    # Alias for backward compatibility with tests
    load_skills = load_all
    _register_skill = load_skill

    def _execute_in_subprocess(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """
        Phase 28.1: Execute a command in a subprocess (for subprocess mode skills).

        Uses 'uv run' for cross-platform, self-healing environment management.
        """
        import subprocess

        skill_dir = self.skills_dir / skill_name
        manifest = self._load_manifest(skill_dir)

        if not manifest:
            return f"Error: No manifest.json found for skill {skill_name}"

        # Get entry point from manifest
        entry_point = manifest.get("entry_point", "implementation.py")
        entry_path = skill_dir / entry_point

        if not entry_path.exists():
            return f"Error: Entry point not found at {entry_path}\n\nTip: Run 'uv sync' in the skill directory first."

        try:
            # Build command: uv run --directory <skill_dir> -q python <entry_point> <command> <args_json>
            cmd = [
                "uv",
                "run",
                "--directory",
                str(skill_dir),
                "-q",  # Quiet mode
                "python",
                entry_point,
                command_name,
                json.dumps(args or {}),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,  # 2 minute timeout
            )

            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            return f"Error (Exit {e.returncode}):\n{e.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 120 seconds"
        except FileNotFoundError:
            return "Error: 'uv' not found. Please install uv: https://uv.sh"

    def unload(self, skill_name: str) -> bool:
        """Unload a skill by name."""
        skill = self._skills.pop(skill_name, None)
        if skill is None:
            return False

        # Clear from sys.modules
        if self._module_loader:
            self._module_loader.unload_module(skill.module_name)

        logger.info("Skill unloaded", skill=skill_name)
        return True

    def reload(self, skill_name: str) -> Skill | None:
        """Force reload a skill."""
        skill_path = self._discover_single(skill_name)
        if skill_path is None:
            return None

        return self.load_skill(skill_path, reload=True)


# =============================================================================
# Global Singleton
# =============================================================================


_manager: SkillManager | None = None
_skill_manager: SkillManager | None = None  # Alias for backward compatibility


def get_skill_manager() -> SkillManager:
    """Get the global skill manager instance."""
    global _manager, _skill_manager
    if _manager is None:
        _manager = SkillManager()

    # Always ensure decorators are preloaded for @skill_command support
    if "agent.skills.decorators" not in sys.modules:
        loader = ModuleLoader(_manager.skills_dir)
        loader._ensure_parent_packages()
        loader._preload_decorators()

    # Sync the alias
    _skill_manager = _manager
    return _manager


def run_command(
    skill_name: str,
    command_name: str,
    args: dict[str, Any] | None = None,
) -> str:
    """
    Convenience function to run a skill command.

    Usage:
        result = run_command("git", "status", {"project_root": ...})
    """
    manager = get_skill_manager()
    return asyncio.run(manager.run(skill_name, command_name, args))


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SkillManager",
    "SkillCommand",
    "Skill",
    "get_skill_manager",
    "run_command",
]
