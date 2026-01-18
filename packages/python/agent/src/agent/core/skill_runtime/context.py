"""
context.py - Skill Context

Unified entry point for all skill services.
Replaces SkillManager by coordinating independent sub-services.

Services:
- registry: Central state management
- discovery: Skill discovery from filesystem
- memory: LRU + TTL memory management
- boot: O(1) boot via skill_index.json
- query: Skill listing and info queries
- load: Skill loading with progress display
- lifecycle: Skill load/unload/reload operations
- executor: Command execution
- search: Semantic search
- jit: JIT loading
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..protocols import SkillManifest
    from ..module_loader import ModuleLoader
    from ..skill_registry.adapter import UnifiedManifestAdapter
    from .registry import SkillRegistry
    from .memory_core import SkillMemoryManager
    from .discovery_core import SkillDiscovery
    from .boot_core import SkillBootManager
    from .query_core import SkillQueryManager
    from .load_core import SkillLoadManager
    from .search_core import SkillSearchManager
    from .lifecycle import SkillLifecycle
    from .jit_loader import SkillJITLoader
    from .executor import SkillExecutor
    from ..support.models import Skill, SkillCommand
    from ..support.preload import CoreSkillsConfig


# Lazy logger
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class SkillContext:
    """
    Unified context for all skill operations.

    This class coordinates independent sub-services without being a
    monolithic manager. Each service is responsible for one thing.

    Usage:
        ctx = get_skill_context()
        ctx.load_skill(path)
        ctx.run("git", "status")
    """

    __slots__ = (
        "skills_dir",
        "registry",
        "_config",
        "_manifest_loader",
        "_module_loader",
        # Services
        "_discovery",
        "_memory",
        "_boot",
        "_query",
        "_load",
        "_lifecycle",
        "_executor",
        "_search",
        "_jit",
    )

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize the skill context and all services."""
        from common.skills_path import SKILLS_DIR
        from .core.registry import SkillRegistry
        from .core.discovery_core import SkillDiscovery
        from .core.memory_core import SkillMemoryManager
        from .core.boot_core import SkillBootManager
        from .core.query_core import SkillQueryManager
        from .core.load_core import SkillLoadManager
        from .core.search_core import SkillSearchManager
        from .lifecycle.lifecycle import SkillLifecycle
        from .lifecycle.jit_loader import SkillJITLoader
        from .support.executor import SkillExecutor
        from .support.preload import CoreSkillsConfig
        from ..skill_registry.adapter import get_unified_adapter
        from ..module_loader import ModuleLoader

        # Skills directory
        if skills_dir is None:
            self.skills_dir = SKILLS_DIR()
        else:
            self.skills_dir = Path(skills_dir)

        # Shared registry
        self.registry = SkillRegistry()

        # Config
        self._config = CoreSkillsConfig.from_settings(self.skills_dir)
        self._manifest_loader = get_unified_adapter()
        self._module_loader: ModuleLoader | None = None

        # Initialize services
        self._discovery = SkillDiscovery(self.skills_dir)
        self._memory = SkillMemoryManager(
            core_skills=self._config.core_skills,
            ttl_seconds=self._config.ttl_seconds,
            ttl_check_interval=self._config.ttl_check_interval,
            max_loaded_skills=self._config.max_loaded_skills,
        )

        self._lifecycle = SkillLifecycle(
            skills_dir=self.skills_dir,
            manifest_loader=self._manifest_loader,
            mtime_cache=self.registry.mtime_cache,
            memory=self._memory,
            notify_change=self._notify_change,
            fire_and_forget=self._fire_and_forget,
        )

        self._boot = SkillBootManager(
            skills_dir=self.skills_dir,
            index_path=self.skills_dir / "skill_index.json",
            skills=self.registry.skills,
            load_skill=self.load_skill,
            load_all=self.load_all,
            get_logger=_get_logger,
        )

        self._query = SkillQueryManager(
            skills_dir=self.skills_dir,
            skills=self.registry.skills,
            discover=self.discover,
            get_logger=_get_logger,
        )

        self._load = SkillLoadManager(
            skills_dir=self.skills_dir,
            skills=self.registry.skills,
            core_skills=self._config.core_skills,
            load_skill=self.load_skill,
            discover=self.discover,
            execute_subprocess=self._lifecycle.execute_in_subprocess,
            get_logger=_get_logger,
        )

        self._search = SkillSearchManager()

        self._jit = SkillJITLoader(
            skills_dir=self.skills_dir,
            search_skills=self._search.search_skills,
            load_skill=self.load_skill,
        )

        self._executor = SkillExecutor(
            command_cache=self.registry.command_cache,
            try_get_cached=self._try_get_cached_result,
            store_cached=self._store_cached_result,
            try_jit_load=self._jit.try_load,
            ensure_fresh=self._ensure_fresh,
        )

    # =========================================================================
    # Observer Pattern (from mixin)
    # =========================================================================

    def _notify_change(self, skill_name: str, change_type: str) -> None:
        """Notify observers of skill change."""
        pass  # Override if needed

    def _fire_and_forget(self, future: asyncio.Future) -> asyncio.Task:
        """Track background task to prevent GC."""
        task = asyncio.create_task(future)
        return task

    # =========================================================================
    # Result Caching (from mixin)
    # =========================================================================

    def _try_get_cached_result(
        self, skill: "Skill", command: "SkillCommand", args: dict[str, Any]
    ) -> str | None:
        """Try to get cached result."""
        return None  # Override with caching logic

    def _store_cached_result(
        self,
        skill: "Skill",
        command: "SkillCommand",
        args: dict[str, Any],
        output: str,
    ) -> None:
        """Store result in cache."""
        pass  # Override with caching logic

    def _ensure_fresh(self, skill_name: str) -> bool:
        """Check if skill is loaded or can be loaded."""
        return skill_name in self.registry.skills

    # =========================================================================
    # Memory Management
    # =========================================================================

    def _touch_skill(self, skill_name: str) -> None:
        """Mark skill as recently used."""
        self._memory.touch(skill_name)

    def _enforce_memory_limit(self) -> None:
        """Enforce memory limit."""
        self._memory.enforce_memory_limit(
            loaded_skills=self.registry.skills,
            pinned_skills=self._config.core_skills,
            unload_skill=self.unload,
        )

    # =========================================================================
    # Discovery
    # =========================================================================

    def discover(self) -> list[Path]:
        """Discover all skills."""
        return self._discovery.discover()

    def _discover_single(self, skill_name: str) -> Path | None:
        """Discover single skill."""
        return self._discovery.discover_single(skill_name)

    # =========================================================================
    # Boot
    # =========================================================================

    def _is_index_fresh(self) -> bool:
        """Check if index is fresh."""
        return self._boot.is_index_fresh()

    def load_from_index(self) -> dict[str, "Skill"]:
        """Load skills from index."""
        return self._boot.load_from_index()

    # =========================================================================
    # Loading
    # =========================================================================

    def load_skill(self, skill_path: Path, *, reload: bool = False) -> "Skill | None":
        """Load a skill."""
        skill = self._lifecycle.load_skill(
            skill_path=skill_path,
            skills=self.registry.skills,
            command_cache=self.registry.command_cache,
            reload=reload,
        )
        if skill:
            self._enforce_memory_limit()
        return skill

    def load_preload_skills(self) -> dict[str, "Skill"]:
        """Load preload skills."""
        return self._load.load_preload_skills()

    def load_all(self) -> dict[str, "Skill"]:
        """Load all skills."""
        return self._load.load_all()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def unload(self, skill_name: str) -> bool:
        """Unload a skill."""
        return self._lifecycle.unload(
            skill_name=skill_name,
            skills=self.registry.skills,
            command_cache=self.registry.command_cache,
        )

    def reload(self, skill_name: str) -> bool | None:
        """Reload a skill."""
        return self._lifecycle.reload(
            skill_name=skill_name,
            discover_single=self._discover_single,
            skills=self.registry.skills,
            command_cache=self.registry.command_cache,
        )

    # =========================================================================
    # Query
    # =========================================================================

    def list_available(self) -> list[str]:
        """List available skills."""
        return self._query.list_available()

    def list_available_from_index(self) -> list[str]:
        """List skills from index."""
        return self._query.list_available_from_index()

    def list_loaded(self) -> list[str]:
        """List loaded skills."""
        return self.registry.list_loaded()

    def get_info(self, skill_name: str) -> dict[str, Any] | None:
        """Get skill info."""
        if not self._ensure_fresh(skill_name):
            return None
        return self._query.get_info(skill_name)

    def get_commands(self, skill_name: str) -> list[str]:
        """Get skill commands."""
        return self._query.get_commands(skill_name)

    def get_command(self, skill_name: str, command_name: str) -> "SkillCommand | None":
        """Get specific command."""
        return self._query.get_command(skill_name, command_name)

    # =========================================================================
    # Execution
    # =========================================================================

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """Execute a skill command."""
        return await self._executor.run(
            skill_name=skill_name,
            command_name=command_name,
            args=args,
            skills=self.registry.skills,
            touch_skill=self._touch_skill,
        )

    # =========================================================================
    # Search
    # =========================================================================

    async def search_skills(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search skills semantically."""
        return await self._search.search_skills(query, limit)

    # =========================================================================
    # Backward Compatibility Aliases
    # =========================================================================

    @property
    def skills(self) -> dict[str, "Skill"]:
        """Backward compatibility alias for registry.skills."""
        return self.registry.skills

    list_available_skills = list_available
    list_commands = get_commands
    get_skill_info = get_info
    load_skills = load_all
    _register_skill = load_skill


# =============================================================================
# Global Singleton
# =============================================================================

_context: SkillContext | None = None


def get_skill_context(skills_dir: Path | None = None) -> SkillContext:
    """
    Get the global skill context instance.

    Args:
        skills_dir: Optional skills directory (only used on first call)

    Returns:
        SkillContext instance
    """
    global _context
    if _context is None:
        _context = SkillContext(skills_dir)
    return _context


def reset_context() -> None:
    """Reset the global context (for testing)."""
    global _context
    _context = None


# Backward compatibility alias
get_skill_manager = get_skill_context


__all__ = [
    "SkillContext",
    "get_skill_context",
    "get_skill_manager",
    "reset_context",
]
