"""
src/agent/core/skill_manager/models.py
 Skill Manager Models - DTOs for skill commands and skills.

Contains:
- SkillCommand: A single command exposed by a skill
- Skill: A loaded skill with commands and context

 Added script mode support for @skill_command decorated commands.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from common.mcp_core.lazy_cache.repomix_cache import RepomixCache

from ...protocols import ExecutionMode, ExecutionResult, SkillCategory

if TYPE_CHECKING:
    from ...protocols import SkillManifest

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

     Supports script mode for @skill_command decorated functions
    with built-in dependency injection and retry logic.
    """

    name: str
    func: Callable[..., Any]
    description: str = ""
    category: str = "general"
    _skill_name: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    #  Script mode fields
    _script_mode: bool = False
    _inject_root: bool = False
    _inject_settings: list[str] = field(default_factory=list)
    _retry_on: tuple[type[Exception], ...] = (ConnectionError, TimeoutError)
    _max_attempts: int = 3

    #  Caching support
    cache_ttl: float = 0.0  # Time-to-live in seconds. 0 = no caching.
    pure: bool = False  # If True, implies side-effect free and safely cacheable.

    def __post_init__(self) -> None:
        """Normalize category to enum."""
        if isinstance(self.category, str):
            object.__setattr__(self, "category", SkillCategory(self.category))

    def _prepare_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Prepare arguments with dependency injection for script mode."""
        import inspect

        from common.gitops import get_project_root
        from common.config.settings import get_setting

        if not self._script_mode:
            return args

        prepared = dict(args)

        # Get function signature to validate accepted parameters
        sig = inspect.signature(self.func)
        accepted_params = set(sig.parameters.keys())

        # Inject project root if requested AND function accepts it
        if (
            self._inject_root
            and "project_root" not in prepared
            and "project_root" in accepted_params
        ):
            prepared["project_root"] = get_project_root()

        # Inject settings if requested AND function accepts them
        for key in self._inject_settings:
            arg_name = key.replace(".", "_")
            if arg_name not in prepared and arg_name in accepted_params:
                try:
                    prepared[arg_name] = get_setting(key)
                except Exception:
                    pass  # Setting not found, skip

        return prepared

    async def execute(self, args: dict[str, Any]) -> ExecutionResult:
        """
        Execute the command with arguments.

        Handles:
        - Script mode: With dependency injection and retry
        - Legacy: Raw return values (converted to ExecutionResult)
        - Enhanced: CommandResult from @skill_command decorator
        """
        import asyncio
        import time

        t0 = time.perf_counter()

        # Prepare args with DI for script mode
        prepared_args = self._prepare_args(args)

        try:
            # Execute with retry for script mode
            if self._script_mode:
                result = await self._execute_with_retry(prepared_args)
            elif asyncio.iscoroutinefunction(self.func):
                result = await self.func(**prepared_args)
            else:
                result = self.func(**prepared_args)

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

    async def _execute_with_retry(self, args: dict[str, Any]) -> Any:
        """Execute with retry logic for script mode."""
        import asyncio

        last_error = None
        for attempt in range(self._max_attempts):
            try:
                if asyncio.iscoroutinefunction(self.func):
                    return await self.func(**args)
                else:
                    return self.func(**args)
            except Exception as e:
                last_error = e
                # Check if retryable
                if not isinstance(e, self._retry_on):
                    raise
                # Wait before retry (exponential backoff)
                if attempt < self._max_attempts - 1:
                    await asyncio.sleep(0.1 * (2**attempt))
        raise last_error


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
