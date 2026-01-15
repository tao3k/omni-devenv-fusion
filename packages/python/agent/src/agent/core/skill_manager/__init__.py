"""
src/agent/core/skill_manager/
 Unified Skill Manager Package

Atomic modules following ODF patterns:
- models.py: SkillCommand, Skill DTOs
- loader.py: Command extraction, module loading
- hot_reload.py: mtime checking, syntax validation
- observer.py: Observer pattern, debounce, GC protection
- manager.py: SkillManager facade (orchestrator)

Usage:
    from agent.core.skill_manager import SkillManager, get_skill_manager, Skill, SkillCommand
"""

from __future__ import annotations

import asyncio
from typing import Any

from .models import SkillCommand, Skill

from .manager import SkillManager

from .observer import ObserverMixin

from .loader import SkillLoaderMixin

from .hot_reload import HotReloadMixin

# =============================================================================
# Global Singleton
# =============================================================================


_manager: SkillManager | None = None
_skill_manager: SkillManager | None = None  # Alias for backward compatibility


def get_skill_manager(lazy: bool = False) -> SkillManager:
    """Get the global skill manager instance.

    Args:
        lazy: If True, don't auto-load all skills. Useful for CLI to avoid
              verbose output. Call load_skill() or load_all() explicitly.
    """
    global _manager, _skill_manager
    if _manager is None:
        _manager = SkillManager()

    # Always ensure decorators are preloaded for @skill_command support
    if "agent.skills.decorators" not in __import__("sys").modules:
        from ..module_loader import ModuleLoader

        loader = ModuleLoader(_manager.skills_dir)
        loader._ensure_parent_packages()
        loader._preload_decorators()

    # Load all skills if not already loaded (default behavior)
    # Set lazy=True to skip auto-loading (for CLI to reduce output)
    if not lazy and not _manager._loaded:
        _manager.load_all()

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


__all__ = [
    # Models
    "SkillCommand",
    "Skill",
    # Manager
    "SkillManager",
    "get_skill_manager",
    "run_command",
    # Mixins (for internal use)
    "ObserverMixin",
    "SkillLoaderMixin",
    "HotReloadMixin",
]
