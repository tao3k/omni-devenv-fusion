"""
executor.py - Skill Command Execution

Handles skill command execution with caching and JIT loading.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from models import Skill, SkillCommand


def _get_logger():
    from ..protocols import _get_logger

    return _get_logger()


class SkillExecutor:
    """
    Executes skill commands with caching and JIT loading support.
    """

    __slots__ = (
        "_command_cache",
        "_try_get_cached",
        "_store_cached",
        "_try_jit_load",
        "_ensure_fresh",
    )

    def __init__(
        self,
        command_cache: dict[str, "SkillCommand"],
        try_get_cached: Callable[..., Optional[str]],
        store_cached: Callable[..., None],
        try_jit_load: Callable[..., Any],
        ensure_fresh: Callable[[str], bool],
    ) -> None:
        self._command_cache = command_cache
        self._try_get_cached = try_get_cached
        self._store_cached = store_cached
        self._try_jit_load = try_jit_load
        self._ensure_fresh = ensure_fresh

    # =========================================================================
    # Command Execution
    # =========================================================================

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None,
        skills: dict[str, "Skill"],
        touch_skill: Callable[[str], None],
    ) -> str:
        """
        Execute a skill command.

        Args:
            skill_name: Name of the skill
            command_name: Name of the command
            args: Arguments for the command
            skills: Skills registry dict
            touch_skill: Function to update LRU

        Returns:
            Command output as string
        """
        # Handle special "help" command
        if command_name == "help":
            return self._get_skill_context(skill_name, skills)

        # JIT Loading Check
        if not self._ensure_fresh(skill_name):
            jit_success = await self._try_jit_load(skill_name)
            if not jit_success:
                return f"Error: Skill '{skill_name}' not found (and JIT load failed)"

        # Update LRU order
        touch_skill(skill_name)

        # HOT RELOAD FIX: Clear command cache for fresh function references
        cache_key = f"{skill_name}.{command_name}"
        if cache_key in self._command_cache:
            del self._command_cache[cache_key]

        # Try cache lookup first
        command = self._command_cache.get(cache_key)
        skill = None

        if command is None:
            skill = skills.get(skill_name)
            if skill is None:
                return f"Error: Skill '{skill_name}' not loaded"

            command = skill.commands.get(command_name)
            if command is None:
                # Try alternate naming
                alt_name = f"{skill_name}_{command_name}"
                command = skill.commands.get(alt_name)

            if command is None:
                available = list(skill.commands.keys())
                return f"Error: Command '{command_name}' not found in '{skill_name}'. Available: {available}"

        if skill is None:
            skill = skills.get(skill_name)

        args = args or {}

        # Check result cache
        if skill is not None:
            cached_output = self._try_get_cached(skill, command, args)
            if cached_output is not None:
                _get_logger().debug("Cache hit", skill=skill_name, command=command_name)
                return cached_output

        # Execute command
        result = await command.execute(args)
        output_str = result.output if result.success else f"Error: {result.error}"

        # Store in cache if successful
        if skill is not None and result.success:
            self._store_cached(skill, command, args, output_str)

        return output_str

    def _get_skill_context(self, skill_name: str, skills: dict[str, "Skill"]) -> str:
        """Get skill context via Repomix."""
        if not self._ensure_fresh(skill_name):
            return f"Skill '{skill_name}' not found"

        skill = skills.get(skill_name)
        if skill is None:
            return f"Skill '{skill_name}' not found"

        if skill.context_cache is None:
            return f"No context available for '{skill_name}'"

        return skill.context_cache.get() or f"# {skill_name}\n\nNo context available."


__all__ = ["SkillExecutor"]
