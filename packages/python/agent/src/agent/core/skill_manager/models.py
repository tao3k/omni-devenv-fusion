"""
src/agent/core/skill_manager/models.py
Phase 29: Skill Manager Models - DTOs for skill commands and skills.

Contains:
- SkillCommand: A single command exposed by a skill
- Skill: A loaded skill with commands and context
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from common.mcp_core.lazy_cache.repomix_cache import RepomixCache

from ..protocols import ExecutionMode, ExecutionResult, SkillCategory

if TYPE_CHECKING:
    from ..protocols import SkillManifest

# Lazy logger
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Command Implementation
# =============================================================================


@dataclass(slots=True)
class SkillCommand:
    """
    A single command exposed by a skill.

    Note: We don't inherit from ISkillCommand protocol here to avoid
    dataclass field ordering issues with Protocol base classes.
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
        """
        Execute the command with arguments.

        Handles both:
        - Legacy: Raw return values (converted to ExecutionResult)
        - Enhanced: CommandResult from @skill_command decorator
        """
        import asyncio
        import time

        t0 = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(**args)
            else:
                result = self.func(**args)

            # Check if result is already a CommandResult (enhanced decorator)
            if hasattr(result, "success") and hasattr(result, "data"):
                # Enhanced: Use CommandResult fields
                return ExecutionResult(
                    success=result.success,
                    output=str(result.data),
                    error=result.error,
                    duration_ms=result.metadata.get("duration_ms", 0.0),
                )

            # Legacy: Raw return value
            return ExecutionResult(
                success=True,
                output=str(result),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                duration_ms=duration_ms,
            )


# =============================================================================
# Skill Implementation
# =============================================================================


@dataclass(slots=True)
class Skill:
    """
    A loaded skill with commands and context.

    Note: We don't inherit from ISkill protocol here to avoid
    dataclass field ordering issues with Protocol base classes.
    """

    name: str
    manifest: "SkillManifest"
    commands: dict[str, SkillCommand] = field(default_factory=dict)
    module_name: str = ""
    path: Path | None = None
    mtime: float = 0.0
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY
    _context_cache: RepomixCache | None = None  # Lazy loaded
    _context_path: Path | None = None  # Store path for lazy creation
    _module: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.execution_mode, str):
            self.execution_mode = ExecutionMode(self.execution_mode)

    @property
    def context_cache(self) -> RepomixCache | None:
        """Lazily create RepomixCache only when needed."""
        if self._context_cache is None and self._context_path is not None:
            self._context_cache = RepomixCache(target_path=self._context_path)
        return self._context_cache

    def get_command(self, name: str) -> SkillCommand | None:
        """Get a specific command by name."""
        return self.commands.get(name)

    async def load(self) -> None:
        """Load is handled by SkillManager during registration."""
        pass

    async def unload(self) -> None:
        """Cleanup resources."""
        self.commands.clear()
        self._module = None


__all__ = [
    "SkillCommand",
    "Skill",
]
