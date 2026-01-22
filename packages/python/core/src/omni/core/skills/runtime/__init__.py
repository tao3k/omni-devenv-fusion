"""
omni.core.skills.runtime - Skill Runtime Environment

Standalone runtime implementation for Zero-Code Skill Architecture.
Manages SkillContext and skill lifecycle.

Usage:
    from omni.core.skills.runtime import get_skill_context, SkillContext
    ctx = get_skill_context(skills_dir)
    ctx.register_skill(universal_skill)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.runtime")


class SkillContext:
    """Runtime context for managing skills.

    Provides:
    - Skill registration and retrieval
    - Skill lifecycle management
    - Command dispatch (both decorated and native functions)
    """

    def __init__(self, skills_dir: Path):
        """Initialize skill context.

        Args:
            skills_dir: Path to assets/skills directory
        """
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Any] = {}
        self._commands: dict[str, Any] = {}  # Decorated commands: "skill.command"
        self._native: dict[str, Any] = {}  # Native functions: "skill.function"

    def register_skill(self, skill: Any) -> None:
        """Register a loaded skill (UniversalScriptSkill).

        Args:
            skill: A UniversalScriptSkill instance
        """
        if hasattr(skill, "name"):
            self._skills[skill.name] = skill

            # Register decorated commands from the skill
            if hasattr(skill, "_script_loader") and skill._script_loader is not None:
                loader = skill._script_loader

                # Register decorated commands
                for cmd_name, handler in loader.commands.items():
                    self._commands[cmd_name] = handler

                # Register native functions (without decorator)
                for func_name, func in loader.native_functions.items():
                    # Store as "skill.function" for direct lookup
                    full_name = f"{skill.name}.{func_name}"
                    self._native[full_name] = func
                    # Also store just the function name for skill-level lookup
                    self._native[func_name] = func

            logger.debug(
                f"Registered skill: {skill.name} ({len(self._commands)} commands, {len(self._native)} native)"
            )
        else:
            logger.warning(f"Attempted to register nameless skill: {skill}")

    def get_skill(self, name: str) -> Any | None:
        """Get a registered skill by name.

        Args:
            name: Skill name (e.g., "git", "filesystem")

        Returns:
            Skill instance or None
        """
        return self._skills.get(name)

    def get_command(self, full_name: str) -> Any | None:
        """Get a command handler (decorated commands).

        Args:
            full_name: Command name (e.g., "git.git_commit")

        Returns:
            Command function or None
        """
        return self._commands.get(full_name)

    def get_native(self, skill_name: str, func_name: str) -> Any | None:
        """Get a native function from a skill.

        Args:
            skill_name: Skill name (e.g., "git")
            func_name: Function name (e.g., "status")

        Returns:
            Native function or None
        """
        # Try "skill.function" format first
        key = f"{skill_name}.{func_name}"
        if key in self._native:
            return self._native[key]
        # Fall back to just function name
        return self._native.get(func_name)

    def list_native_functions(self, skill_name: str | None = None) -> list[str]:
        """List native function names.

        Args:
            skill_name: Optional skill name to filter by

        Returns:
            List of native function names
        """
        if skill_name:
            return [
                k
                for k in self._native.keys()
                if isinstance(k, str) and k.startswith(f"{skill_name}.")
            ]
        return list(set(self._native.keys()))

    def list_skills(self) -> list[str]:
        """List registered skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def list_commands(self) -> list[str]:
        """List all registered commands.

        Returns:
            List of command names
        """
        return list(self._commands.keys())

    def clear(self) -> None:
        """Clear all registered skills and commands."""
        self._skills.clear()
        self._commands.clear()

    @property
    def skills_count(self) -> int:
        """Get number of registered skills."""
        return len(self._skills)


class SkillRegistry:
    """Legacy skill registry (for compatibility)."""

    def __init__(self):
        self._skills: dict[str, Any] = {}

    def register(self, name: str, skill: Any) -> None:
        self._skills[name] = skill

    def get(self, name: str) -> Any | None:
        return self._skills.get(name)


class SkillDiscovery:
    """Skill discovery service."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)

    def discover(self) -> list[str]:
        """Discover available skills.

        Returns:
            List of skill names
        """
        if not self.skills_dir.exists():
            return []

        return [
            d.name for d in self.skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")
        ]


# Global context singleton
_context: SkillContext | None = None


def get_skill_context(skills_dir: Path) -> SkillContext:
    """Get or create the global skill context.

    Args:
        skills_dir: Path to assets/skills directory

    Returns:
        SkillContext instance
    """
    global _context
    if _context is None:
        _context = SkillContext(skills_dir)
    return _context


def get_skill_manager(skills_dir: Path) -> SkillContext:
    """Backward compatibility alias for get_skill_context."""
    return get_skill_context(skills_dir)


def reset_context() -> None:
    """Reset the global skill context (for testing)."""
    global _context
    if _context is not None:
        _context.clear()
    _context = None


def get_registry() -> SkillRegistry:
    """Get the skill registry (for compatibility)."""
    return SkillRegistry()


async def run_command(command: str, **kwargs) -> Any:
    """Run a skill command (decorated or native).

    Args:
        command: Full command name (e.g., "git.git_commit" or "git.status")
        **kwargs: Command arguments

    Returns:
        Command result
    """
    global _context
    if _context is None:
        raise RuntimeError("SkillContext not initialized. Call get_skill_context() first.")

    # First try decorated command
    handler = _context.get_command(command)
    if handler is None:
        # Try native function: parse "skill.func" -> skill="git", func="status"
        if "." in command:
            skill_name, func_name = command.split(".", 1)
            handler = _context.get_native(skill_name, func_name)

    if handler is None:
        available = _context.list_commands()
        raise ValueError(f"Command '{command}' not found. Available: {available}")

    if hasattr(handler, "__call__"):
        import inspect

        if inspect.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return handler(**kwargs)

    raise TypeError(f"Command handler is not callable: {handler}")


# Convenience type aliases
SkillManager = SkillContext

# Deprecated type stubs - removed (agent.core.skill_runtime no longer exists)


__all__ = [
    # Context
    "SkillContext",
    "SkillManager",  # Alias
    "get_skill_context",
    "get_skill_manager",
    "reset_context",
    # Registry
    "SkillRegistry",
    "get_registry",
    # Execution
    "run_command",
]
