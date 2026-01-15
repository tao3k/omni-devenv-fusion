"""
src/agent/core/skill_manager/hot_reload.py
Phase 29: Hot Reload Mixin.
Phase 67: Simplified for JIT/Meta-Agent Era (Removed syntax validation).

Simplified hot reload that relies on:
- Python's native import mechanism for error handling
- Meta-Agent's self-repair capabilities for recovery
- JIT loading for on-demand code updates
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

# Lazy logger - defer structlog.get_logger() to avoid ~100ms import cost
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class HotReloadMixin:
    """
    Mixin for checking and reloading skills when files change.

    Simplified in Phase 67:
    - Removed _validate_syntax() - Python import will catch errors
    - Simplified _reload_skill() - direct reload, failures propagate up
    - Keep _ensure_fresh() - core mtime-based trigger mechanism

    Design philosophy:
    - Fail fast, let Meta-Agent handle recovery
    - No double file reads (validate + load)
    - Minimal overhead on hot path
    """

    # These should be defined in the parent class
    _skills: dict[str, Any]
    _command_cache: dict[str, Any]
    _mtime_cache: dict[str, float]
    skills_dir: Path

    def _ensure_fresh(self, skill_name: str) -> bool:
        """
        Check if a skill needs reloading and reload it if necessary.

        Phase 67: Simplified - only checks mtime, no syntax validation.

        Args:
            skill_name: Name of the skill to check

        Returns:
            True if skill is loaded and fresh, False if not found
        """
        skill = self._skills.get(skill_name)
        if skill is None:
            _get_logger().debug("Skill not in memory", skill=skill_name)
            return False

        # Check if scripts directory exists
        if not skill.path or not skill.path.exists():
            _get_logger().warning("Skill path deleted", skill=skill_name)
            return False

        try:
            # Get max mtime of all .py files in scripts/
            script_files = list(skill.path.glob("*.py"))
            if not script_files:
                return True  # No scripts to track

            current_mtime = max(f.stat().st_mtime for f in script_files)

            # Compare with cached mtime
            cached_mtime = self._mtime_cache.get(skill_name, 0.0)

            if current_mtime > cached_mtime:
                _get_logger().info(
                    "Hot reload triggered",
                    skill=skill_name,
                    cached_mtime=cached_mtime,
                    current_mtime=current_mtime,
                )
                self._reload_skill(skill, current_mtime)

            return True

        except Exception as e:
            _get_logger().warning(
                "Hot reload check failed",
                skill=skill_name,
                error=str(e),
            )
            # Return True to allow execution - if import fails, it will error naturally
            return True

    def _reload_skill(self, skill: Any, new_mtime: float) -> None:
        """
        Reload a skill after detecting file changes.

        Phase 67: Simplified - direct unload + reload, failures propagate.

        Args:
            skill: The skill object to reload
            new_mtime: The new modification time to cache

        Raises:
            RuntimeError: If reload fails
        """
        skill_name = skill.name
        skill_path = skill.path.parent  # scripts/ -> skill root

        _get_logger().info("Reloading skill", skill=skill_name)

        # 1. Force unload (suppress notifications during reload)
        self.unload(skill_name)

        # 2. Load fresh version
        new_skill = self.load_skill(skill_path, reload=True)

        if new_skill:
            # 3. Update mtime cache
            self._mtime_cache[skill_name] = new_mtime
            _get_logger().info(
                "Skill reloaded successfully",
                skill=skill_name,
                commands=len(new_skill.commands),
            )
        else:
            raise RuntimeError(f"Failed to reload skill: {skill_name}")


__all__ = [
    "HotReloadMixin",
]
