"""
src/agent/core/skill_runtime/
Skill Services - Modular Architecture

No monolithic manager. Independent services for each responsibility:
- SkillContext: Unified entry point (replaces SkillManager)
- SkillRegistry: Central state management
- SkillDiscovery: Skill discovery from filesystem
- SkillMemoryManager: LRU + TTL memory management
- SkillBootManager: O(1) boot via skill_index.json
- SkillQueryManager: Skill listing and info queries
- SkillLoadManager: Skill loading with progress display
- SkillLifecycle: Skill load/unload/reload operations
- SkillExecutor: Command execution
- SkillSearchManager: Semantic search
- SkillJITLoader: JIT loading

Usage:
    from agent.core.skill_runtime import get_skill_context, get_skill_manager
    ctx = get_skill_context()
    ctx.load_skill(path)
    result = await ctx.run("git", "status")
"""

from __future__ import annotations

import asyncio
from typing import Any

# Re-export models
from .support.models import SkillCommand, Skill
from .support.observer import ObserverMixin
from .support.loader import SkillLoaderMixin
from .support.hot_reload import HotReloadMixin

# Re-export registry and context (new unified entry point)
from .context import (
    SkillContext,
    get_skill_context,
    get_skill_manager,  # Backward compatibility
    reset_context,
)
from .core.registry import SkillRegistry, get_registry, reset_registry

# Backward compatibility alias (SkillManager was replaced by SkillContext)
SkillManager = SkillContext

# Re-export core modules
from .core.discovery_core import SkillDiscovery
from .core.memory_core import SkillMemoryManager
from .core.boot_core import SkillBootManager
from .core.query_core import SkillQueryManager
from .core.load_core import SkillLoadManager
from .core.search_core import SkillSearchManager

# Re-export lifecycle modules
from .lifecycle.lifecycle import SkillLifecycle
from .lifecycle.jit_loader import SkillJITLoader

# Re-export executor
from .support.executor import SkillExecutor


# =============================================================================
# Global Singleton (via context)
# =============================================================================


def get_skill_manager(lazy: bool = False, skills_dir: Any = None) -> "SkillContext":
    """Get the global skill context instance.

    Backward compatible alias for get_skill_context().

    Args:
        lazy: If True, don't auto-load all skills (ignored, kept for compatibility).
        skills_dir: Optional skills directory (only used on first call).
    """
    from .context import get_skill_context

    return get_skill_context(skills_dir)


# Backward compatibility alias for internal use
def _get_singleton_manager() -> "SkillContext":
    """Get the global skill context singleton. Internal API."""
    return get_skill_manager()


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
    ctx = get_skill_context()
    return asyncio.run(ctx.run(skill_name, command_name, args))


__all__ = [
    # Models
    "SkillCommand",
    "Skill",
    # Context (main entry point)
    "SkillContext",
    "SkillManager",  # Backward compatibility alias
    "get_skill_context",
    "get_skill_manager",
    "reset_context",
    # Registry
    "SkillRegistry",
    "get_registry",
    "reset_registry",
    # Core modules
    "SkillDiscovery",
    "SkillMemoryManager",
    "SkillBootManager",
    "SkillQueryManager",
    "SkillLoadManager",
    "SkillSearchManager",
    # Lifecycle
    "SkillLifecycle",
    "SkillJITLoader",
    # Executor
    "SkillExecutor",
    # Utility
    "run_command",
    # Mixins
    "ObserverMixin",
    "SkillLoaderMixin",
    "HotReloadMixin",
]
