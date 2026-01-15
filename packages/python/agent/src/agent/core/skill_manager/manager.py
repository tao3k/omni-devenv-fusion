"""
src/agent/core/skill_manager/manager.py
Phase 29: Skill Manager - Main orchestration class.

Combines all mixins to provide the complete SkillManager facade.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from common.mcp_core.lazy_cache.repomix_cache import RepomixCache

from .hot_reload import HotReloadMixin
from .loader import SkillLoaderMixin
from .models import Skill, SkillCommand
from .observer import ObserverMixin
from .caching import ResultCacheMixin  # Phase 61

from ..module_loader import ModuleLoader, module_loader
from ..protocols import ExecutionMode, SkillCategory
from ...skills.core.skill_manifest_loader import (
    SkillManifestLoader,
    get_manifest_loader,
)
from ...skills.core.skill_manifest import SkillMetadata
from ..registry.adapter import UnifiedManifestAdapter, get_unified_adapter

if TYPE_CHECKING:
    from ..protocols import SkillManifest

# Lazy logger - defer structlog.get_logger() to avoid ~100ms import cost
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# Default skills directory
SKILLS_DIR_PATH: str = "assets/skills"


class SkillManager(HotReloadMixin, SkillLoaderMixin, ObserverMixin, ResultCacheMixin):
    """
    Central skill manager with Trinity Architecture.

    Phase 61: Added ResultCacheMixin for IO optimization.

    Responsibilities:
    - Discover and load skills
    - Hot-reload on file changes
    - Execute commands with caching
    - Provide skill context

    Design:
    - Protocol-based for testability
    - Uses ModuleLoader for clean imports
    - Slots on all internal state
    - O(1) command lookup with caching
    """

    __slots__ = (
        "skills_dir",
        "_skills",
        "_module_loader",
        "_loaded",
        "_preload_done",
        "_command_cache",  # O(1) command lookup cache
        "_mtime_cache",  # Lazy mtime checking
        "_manifest_loader",  # Skill manifest loader
        "_observers",  # Phase 36.4: Observer pattern for change notifications
        "_pending_change_task",  # Phase 36.5: Debounced notification task
        "_pending_changes",  # Phase 36.5: Track pending skill changes for debounce
        "_background_tasks",  # Phase 36.6: Track background tasks to prevent GC
        "_result_cache",  # Phase 61: Result caching from ResultCacheMixin
        # Phase 67 Step 3: Adaptive Unloading (LRU)
        "_lru_order",
        "_pinned_skills",
        "_max_loaded_skills",
    )

    def __init__(self, skills_dir: Path | None = None) -> None:
        """
        Initialize the skill manager.

        Args:
            skills_dir: Path to skills directory (default: assets/skills)
        """
        from common.skills_path import SKILLS_DIR

        if skills_dir is None:
            self.skills_dir = SKILLS_DIR()
        else:
            self.skills_dir = Path(skills_dir)

        # Initialize mixins
        ResultCacheMixin.__init__(self)

        self._skills: dict[str, Skill] = {}
        self._module_loader: ModuleLoader | None = None
        self._loaded = False
        self._preload_done = False

        # O(1) command lookup cache: "skill.command" -> SkillCommand
        self._command_cache: dict[str, SkillCommand] = {}

        # Lazy mtime checking: skill_name -> mtime
        self._mtime_cache: dict[str, float] = {}

        # Unified manifest loader (SKILL.md + manifest.json)
        self._manifest_loader: UnifiedManifestAdapter = get_unified_adapter()

        # Phase 36.4: Observer pattern for hot-reload notifications
        self._observers: list[Callable[[str, str], Any]] = []

        # Phase 36.5: Debounced notification task and pending changes
        self._pending_change_task: asyncio.Task | None = None
        self._pending_changes: list[tuple[str, str]] = []  # [(skill_name, change_type), ...]

        # Phase 36.6: Track background tasks to prevent GC during fire-and-forget
        self._background_tasks: set[asyncio.Task] = set()

        # Phase 67 Step 3: Adaptive Unloading (LRU)
        self._lru_order: list[str] = []
        self._pinned_skills: set[str] = {"filesystem", "terminal", "writer", "git", "note_taker"}
        self._max_loaded_skills: int = 15

    # =========================================================================
    # Phase 67 Step 3: Adaptive Unloading (LRU)
    # =========================================================================

    def _touch_skill(self, skill_name: str) -> None:
        """
        Mark a skill as recently used (moves to end of LRU queue).

        Phase 67: Called on every skill execution to track usage order.
        """
        if skill_name in self._lru_order:
            self._lru_order.remove(skill_name)
        self._lru_order.append(skill_name)

    def _enforce_memory_limit(self) -> None:
        """
        Unload LRU skills if loaded count exceeds limit.

        Phase 67: Prevents memory bloat from JIT loading.
        Pinned skills (core skills) are protected from unloading.
        """
        if len(self._skills) <= self._max_loaded_skills:
            return

        excess = len(self._skills) - self._max_loaded_skills
        unloaded_count = 0

        # Iterate from oldest (front) to newest
        for skill_name in list(self._lru_order):
            if unloaded_count >= excess:
                break

            # Skip pinned skills
            if skill_name in self._pinned_skills:
                continue

            # Skip skills not currently loaded (sanity check)
            if skill_name not in self._skills:
                continue

            _get_logger().info(
                "Adaptive Unloading: Releasing unused skill",
                skill=skill_name,
                loaded_count=len(self._skills),
                limit=self._max_loaded_skills,
            )

            if self.unload(skill_name):
                unloaded_count += 1

        _get_logger().debug(
            "Adaptive Unloading complete",
            unloaded=unloaded_count,
            remaining=len(self._skills),
        )

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
        """Discover all skill directories with SKILL.md.

        Only supports scripts/*.py pattern (Phase 63+).
        """
        if not self.skills_dir.exists():
            _get_logger().warning("Skills directory not found", path=str(self.skills_dir))
            return []

        skills: list[Path] = []
        for entry in self.skills_dir.iterdir():
            if not entry.is_dir():
                continue

            # Check for SKILL.md (required for all skills)
            if not self._manifest_loader.skill_file_exists(entry):
                continue

            # Check for scripts/*.py
            scripts_dir = entry / "scripts"
            has_scripts = scripts_dir.exists() and any(scripts_dir.glob("*.py"))

            if has_scripts:
                skills.append(entry)
            else:
                _get_logger().debug("Skipping - no scripts/*.py", skill=entry.name)

        _get_logger().info("Discovered skills", count=len(skills))
        return skills

    def _discover_single(self, skill_name: str) -> Path | None:
        """Discover a single skill by name."""
        skill_path = self.skills_dir / skill_name
        if skill_path.exists() and self._manifest_loader.skill_file_exists(skill_path):
            return skill_path
        return None

    # =========================================================================
    # Loading
    # =========================================================================

    def load_skill(self, skill_path: Path, *, reload: bool = False) -> Skill | None:
        """
        Load a skill from a path.

        Only supports scripts/*.py pattern (Phase 63+).
        Uses @skill_script decorated functions from scripts/*.py.

        Args:
            skill_path: Path to the skill directory
            reload: If True, force reload even if already loaded

        Returns:
            Skill instance or None if loading failed
        """
        import concurrent.futures

        skill_name = skill_path.name

        # Check if already loaded (skip reload check for initial load)
        if not reload and skill_name in self._skills:
            return self._skills[skill_name]

        # Load manifest from SKILL.md
        loader = self._manifest_loader

        # Run in thread to avoid event loop conflicts with async tests
        def _load():
            return asyncio.run(loader.load_metadata(skill_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            metadata = executor.submit(_load).result()

        if metadata is None:
            _get_logger().error("No SKILL.md found", skill=skill_name)
            return None

        # Build manifest dict for compatibility
        manifest = metadata.to_dict()

        # Check execution mode
        execution_mode = metadata.execution_mode

        # Only load from scripts/*.py
        commands: dict[str, SkillCommand] = {}
        scripts_dir = skill_path / "scripts"
        mtime = 0.0

        # Load from scripts/*.py (Phase 63+)
        if scripts_dir.exists() and any(scripts_dir.glob("*.py")):
            script_commands = self._extract_commands_from_scripts(skill_name, scripts_dir)

            if script_commands:
                commands = script_commands

                # Update mtime based on scripts
                try:
                    script_mtimes = [f.stat().st_mtime for f in scripts_dir.glob("*.py")]
                    if script_mtimes:
                        mtime = max(script_mtimes)
                except FileNotFoundError:
                    pass

        if not commands:
            _get_logger().warning("No commands found in skill", skill=skill_name)
            # Not an error - some skills might be pure data

        # Store context path for lazy creation (avoids get_project_root() call during load)
        config_path = skill_path / "repomix.json"
        if not config_path.exists():
            config_path = None
        context_path = skill_path if config_path else None

        # Create skill with lazy context cache
        skill = Skill(
            name=skill_name,
            manifest=manifest,
            commands=commands,
            module_name=f"agent.skills.{skill_name}",
            path=scripts_dir,
            mtime=mtime,
            execution_mode=execution_mode,
            _context_path=context_path,  # Lazy loaded
            _module=None,
        )

        self._skills[skill_name] = skill

        # Update mtime cache
        self._mtime_cache[skill_name] = mtime

        # Rebuild command cache for this skill
        self._rebuild_command_cache(skill_name, commands)

        _get_logger().info(
            "Skill loaded",
            skill=skill_name,
            commands=len(commands),
            mode=execution_mode.value,
        )

        # Phase 36.5: Notify observers of skill change (triggers MCP tool list update + Index Sync)
        self._notify_change(skill_name, "load")

        # Phase 67 Step 3: Register in LRU and enforce memory limit
        self._touch_skill(skill_name)
        self._enforce_memory_limit()

        return skill

    def _load_manifest(self, skill_path: Path) -> dict[str, Any] | None:
        """Load manifest from SKILL.md.

        This method is kept for compatibility with existing code.
        """
        import concurrent.futures

        loader = self._manifest_loader

        # Run in thread to avoid event loop conflicts with async tests
        def _load():
            return asyncio.run(loader.load_metadata(skill_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            metadata = executor.submit(_load).result()

        if metadata is None:
            return None
        return metadata.to_dict()

    # =========================================================================
    # Phase 67: JIT Loading
    # =========================================================================

    async def _try_jit_load(self, skill_name: str) -> bool:
        """
        Attempt to Just-In-Time load a skill from the vector index.

        Phase 67: When a skill is called but not loaded, search the index
        to find its path and load it automatically.

        Strategy:
        1. First try direct path lookup (fastest)
        2. Then fall back to semantic search if skill not in expected location

        Args:
            skill_name: Name of the skill to load

        Returns:
            True if skill was successfully loaded, False otherwise
        """
        from common.skills_path import SKILLS_DIR

        _get_logger().debug("Attempting JIT load", skill=skill_name)

        # Strategy 1: Direct path lookup using SKILLS_DIR (fastest - most common case)
        definition_path = SKILLS_DIR.definition_file(skill_name)
        if definition_path.exists():
            _get_logger().info(
                "JIT loaded skill from disk", skill=skill_name, path=str(definition_path.parent)
            )
            self.load_skill(definition_path.parent)
            return True

        # Strategy 2: Fall back to semantic search (edge case: skill moved)
        results = await self.search_skills(skill_name, limit=10)

        for tool in results:
            meta = tool.get("metadata", {})
            if meta.get("skill_name") == skill_name:
                script_path_str = meta.get("file_path")
                if script_path_str:
                    script_path = Path(script_path_str)
                    try:
                        potential_root = script_path.parent.parent
                        if (potential_root / "SKILL.md").exists():
                            _get_logger().info(
                                "JIT loaded skill from index",
                                skill=skill_name,
                                path=str(potential_root),
                            )
                            self.load_skill(potential_root)
                            return True
                    except Exception:
                        continue

        _get_logger().warning("JIT load failed: Skill not found", skill=skill_name)
        return False

    # =========================================================================
    # Execution (Optimized with O(1) command lookup)
    # =========================================================================

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """
        Execute a skill command.

        Phase 61: Optimized with result caching.
        Phase 67: JIT loading + LRU tracking.

        Optimizations:
        - O(1) command lookup via cache
        - Try result cache first for cached commands
        - JIT load skill from index if not loaded
        - LRU tracking for memory management

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

        # Phase 67: JIT Loading Check
        # If skill not in memory, try Just-In-Time load from index
        if not self._ensure_fresh(skill_name):
            jit_success = await self._try_jit_load(skill_name)
            if not jit_success:
                return f"Error: Skill '{skill_name}' not found (and JIT load failed)"

        # Phase 67: Update LRU order (mark as recently used)
        self._touch_skill(skill_name)

        # HOT RELOAD FIX: Clear command cache to get fresh function references
        # Even if mtime hasn't changed, cache may have stale function objects
        cache_key = f"{skill_name}.{command_name}"
        if cache_key in self._command_cache:
            del self._command_cache[cache_key]

        # Try O(1) cache lookup first
        command = self._command_cache.get(cache_key)
        skill = None

        # If not in cache, look up directly
        if command is None:
            skill = self._skills.get(skill_name)
            if skill is None:
                return f"Error: Skill '{skill_name}' not loaded"

            # Fallback to direct lookup (also populates cache)
            command = skill.commands.get(command_name)
            if command is None:
                # Try alternate naming (skill_command vs just command)
                alt_name = f"{skill_name}_{command_name}"
                command = skill.commands.get(alt_name)

            if command is None:
                available = list(skill.commands.keys())
                return f"Error: Command '{command_name}' not found in '{skill_name}'. Available: {available}"

        # Get skill reference for caching
        if skill is None:
            skill = self._skills.get(skill_name)

        args = args or {}

        # Phase 61: Check result cache before execution
        if skill is not None:
            cached_output = self._try_get_cached_result(skill, command, args)
            if cached_output is not None:
                _get_logger().debug("Cache hit", skill=skill_name, command=command_name)
                return cached_output

        # Execute command
        result = await command.execute(args)
        output_str = result.output if result.success else f"Error: {result.error}"

        # Phase 61: Store in cache if successful and caching is enabled
        if skill is not None and result.success:
            self._store_cached_result(skill, command, args, output_str)

        return output_str

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
    # Phase 67: Semantic Search (for Ghost Tool Injection)
    # =========================================================================

    async def search_skills(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search for skills matching the query using semantic search.

        Phase 67: Used by Ghost Tool Injection to find relevant unloaded tools.

        Args:
            query: Natural language query describing the task
            limit: Maximum number of results to return

        Returns:
            List of matching skill dicts with id, name, description, score
        """
        from agent.core.vector_store import get_vector_memory

        try:
            vm = get_vector_memory()
            results = await vm.search_tools_hybrid(query, limit=limit)

            # Transform results to match expected format
            transformed: list[dict[str, Any]] = []
            for r in results:
                metadata = r.get("metadata", {})
                transformed.append(
                    {
                        "id": r.get("id", ""),
                        "name": metadata.get("skill_name", r.get("id", "").split(".")[0]),
                        "description": r.get("content", ""),
                        "score": 1.0 - r.get("distance", 1.0),
                        "metadata": metadata,
                    }
                )

            _get_logger().debug(
                "Skill search completed",
                query=query[:50],
                results=len(transformed),
            )
            return transformed
        except Exception as e:
            _get_logger().warning("Skill search failed", error=str(e))
            return []

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

    def load_all(self) -> dict[str, Skill]:
        """
        Load all discovered skills.

        Returns:
            Dictionary of loaded skills
        """
        if self._loaded:
            _get_logger().debug("Skills already loaded")
            return self._skills

        skill_paths = self.discover()
        for path in skill_paths:
            self.load_skill(path)

        self._loaded = True
        _get_logger().info("All skills loaded", count=len(self._skills))
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
            return f"Error: No SKILL.md found for skill {skill_name}"

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
        """
        Unload a skill by name.

        Phase 36.4: Performs surgical cleanup:
        1. Removes skill from internal registry
        2. Clears command cache entries
        3. Recursively cleans sys.modules (removes submodules like scripts/*)
        4. Notifies observers to update MCP tool list

        Phase 67: Also removes from LRU tracking.
        """
        from ..protocols import _get_logger

        skill = self._skills.pop(skill_name, None)
        if skill is None:
            return False

        # Clear command cache entries for this skill
        keys_to_remove = [k for k in self._command_cache if k.startswith(f"{skill_name}.")]
        for key in keys_to_remove:
            del self._command_cache[key]

        # Clear mtime cache
        self._mtime_cache.pop(skill_name, None)

        # Phase 67: Remove from LRU tracking
        if skill_name in self._lru_order:
            self._lru_order.remove(skill_name)

        # Phase 36.4: Recursive sys.modules cleanup
        # This ensures submodules like `agent.skills.git.scripts.log` are also killed
        # Using module_name (e.g., "agent.skills.git.tools") to find and remove all related modules
        if skill.module_name:
            # Remove the main module first
            if skill.module_name in sys.modules:
                del sys.modules[skill.module_name]
                _get_logger().debug("Cleaned main module from memory", module=skill.module_name)

            # Remove submodules (scripts/*, etc.) with same prefix
            prefix = f"agent.skills.{skill_name}."
            modules_to_remove = [m for m in sys.modules if m.startswith(prefix)]
            for module in modules_to_remove:
                del sys.modules[module]
                _get_logger().debug("Cleaned submodule from memory", module=module)

        _get_logger().info("Skill unloaded", skill=skill_name)

        # Phase 36.5: Notify observers of skill change
        self._notify_change(skill_name, "unload")

        return True


__all__ = [
    "SkillManager",
]
