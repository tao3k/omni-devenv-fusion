"""
src/agent/core/skill_manager/hot_reload.py
Phase 36.5: Hot reload with syntax validation.

Contains:
- mtime-based file change detection
- Syntax validation before reload (transactional safety)
- Hot reload execution
"""

from __future__ import annotations

import asyncio
import py_compile
from pathlib import Path
from typing import Any


class HotReloadMixin:
    """
    Mixin providing hot reload functionality with safety checks.

    Used by SkillManager to detect and reload modified skills.
    """

    # These should be defined in the parent class
    _skills: dict[str, Any]
    _command_cache: dict[str, Any]
    _mtime_cache: dict[str, float]
    skills_dir: Path

    def _ensure_fresh(self, skill_name: str) -> bool:
        """
        Check and reload skill if modified (hot-reload).

        Optimizations:
        - Check both tools.py and scripts/* for modifications
        - Clear command cache on reload
        """
        from ..protocols import _get_logger

        skill_path = self._discover_single(skill_name)
        if skill_path is None:
            _get_logger().debug("Skill not found on disk", skill=skill_name)
            return False

        if skill_name not in self._skills:
            return self.load_skill(skill_path) is not None

        skill = self._skills[skill_name]
        tools_path = skill_path / "tools.py"
        scripts_path = skill_path / "scripts"

        try:
            # Check tools.py mtime
            current_mtime = tools_path.stat().st_mtime

            # Also check scripts/* directory for modifications
            scripts_mtime = 0.0
            scripts_files = []
            if scripts_path.exists() and scripts_path.is_dir():
                for script_file in scripts_path.glob("*.py"):
                    if script_file.name.startswith("_"):
                        continue  # Skip __init__.py and private modules
                    try:
                        file_mtime = script_file.stat().st_mtime
                        scripts_mtime = max(scripts_mtime, file_mtime)
                        scripts_files.append(f"{script_file.name}:{file_mtime}")
                    except (FileNotFoundError, OSError):
                        pass

            # DEBUG: Log mtime comparison
            should_reload = current_mtime > skill.mtime or scripts_mtime > skill.mtime
            _get_logger().debug(
                "Hot-reload check",
                skill=skill_name,
                skill_mtime=skill.mtime,
                tools_mtime=current_mtime,
                scripts_mtime=scripts_mtime,
                should_reload=should_reload,
                scripts=scripts_files[:3],  # First 3 for logging
            )

            # Trigger reload if any file was modified
            if should_reload:
                modified = []
                if current_mtime > skill.mtime:
                    modified.append("tools.py")
                if scripts_mtime > skill.mtime:
                    modified.append("scripts/*")
                _get_logger().info("Hot-reloading skill", skill=skill_name, modified=modified)

                # Clear stale cache entries for this skill
                keys_to_remove = [k for k in self._command_cache if k.startswith(f"{skill_name}.")]
                for key in keys_to_remove:
                    del self._command_cache[key]

                return self.load_skill(skill_path, reload=True) is not None
        except FileNotFoundError:
            _get_logger().warning("Skill file deleted", skill=skill_name)

        return True

    def _validate_syntax(self, skill_path: Path) -> bool:
        """
        Phase 36.5: Validate Python syntax before reloading.

        This is a safety check to prevent destroying a working skill
        when the new code has syntax errors.

        Args:
            skill_path: Path to skill directory

        Returns:
            True if all Python files have valid syntax, False otherwise
        """
        from ..protocols import _get_logger

        valid = True

        # Check tools.py
        tools_path = skill_path / "tools.py"
        if tools_path.exists():
            try:
                py_compile.compile(tools_path, doraise=True)
            except py_compile.PyCompileError as e:
                _get_logger().error("Syntax error in tools.py", skill=skill_path.name, error=str(e))
                valid = False

        # Check scripts/*.py (skip __init__.py)
        scripts_path = skill_path / "scripts"
        if scripts_path.exists() and scripts_path.is_dir():
            for py_file in scripts_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue  # Skip __init__.py and private modules
                try:
                    py_compile.compile(py_file, doraise=True)
                except py_compile.PyCompileError as e:
                    _get_logger().error(
                        "Syntax error in script",
                        skill=skill_path.name,
                        file=str(py_file.relative_to(skill_path)),
                        error=str(e),
                    )
                    valid = False

        return valid

    def reload(self, skill_name: str) -> Any | None:
        """
        Force reload a skill.

        Phase 36.5: This performs a transactional hot-reload cycle:
        1. Validate syntax of new code BEFORE unloading old code
        2. Unload the existing skill (with sys.modules cleanup)
        3. Load the fresh version from disk
        4. Notifies observers of the change (single "reload" event)

        If syntax validation fails, the old skill is preserved.
        """
        from ..protocols import _get_logger
        import sys

        skill_path = self._discover_single(skill_name)
        if skill_path is None:
            _get_logger().warning("Cannot reload - skill not found", skill=skill_name)
            return None

        # Phase 36.5: Syntax validation BEFORE destructive operations
        if not self._validate_syntax(skill_path):
            _get_logger().error(
                "⚠️ [Reload] Syntax validation failed - aborting reload", skill=skill_name
            )
            return self._skills.get(skill_name)  # Return existing skill, don't modify

        # Unload first to ensure clean slate (suppress notification)
        skill = self._skills.pop(skill_name, None)
        if skill:
            # Clear command cache entries for this skill
            keys_to_remove = [k for k in self._command_cache if k.startswith(f"{skill_name}.")]
            for key in keys_to_remove:
                del self._command_cache[key]
            self._mtime_cache.pop(skill_name, None)
            # Recursive sys.modules cleanup
            if skill.module_name:
                if skill.module_name in sys.modules:
                    del sys.modules[skill.module_name]
                prefix = f"agent.skills.{skill_name}."
                modules_to_remove = [m for m in sys.modules if m.startswith(prefix)]
                for module in modules_to_remove:
                    del sys.modules[module]
            _get_logger().info("Skill unloaded for reload", skill=skill_name)

        # Load fresh (single notification for reload)
        result = self.load_skill(skill_path, reload=True)
        if result:
            # Send a single "reload" notification to batch unload+load
            self._pending_changes.append((skill_name, "reload"))
            # Trigger the notification
            if self._pending_change_task is not None:
                self._pending_change_task.cancel()
            try:
                loop = asyncio.get_running_loop()
                self._pending_change_task = loop.create_task(self._debounced_notify())
            except RuntimeError:
                pass

        return result


__all__ = [
    "HotReloadMixin",
]
