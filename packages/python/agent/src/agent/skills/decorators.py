"""
agent/skills/decorators.py
 Reflexion Loop - Enhanced Skill Command Decorator

Extends Phase 25.1 Omni Skill Macros with:
- CommandResult: Structured output with retry metadata
- Error Interception: Captures structured errors for Agent reflection
- Tenacity Pattern: Automatic retry for transient failures
- Context-Aware Observability: Structured logging with structlog

ODF-EP v6.0 Compliance:
- Pillar A: Pydantic Shield (CommandResult frozen=True)
- Pillar C: Tenacity Pattern (@retry for resilience)
- Pillar D: Context-Aware Observability
"""

from __future__ import annotations

import functools
import inspect
import time
from typing import Any, Callable, get_type_hints, Optional, Union

from pydantic import BaseModel, ConfigDict

# Import from common (not mcp_core - these are general utilities)
from common.config_paths import get_project_root
from common.config.settings import get_setting

# Lazy logger - defer structlog.get_logger() to avoid import overhead
_cached_logger: Any | None = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Command Result (Pillar A: Pydantic Shield)
# =============================================================================


class CommandResult(BaseModel):
    """
    Structured output for all skill commands.

    Provides consistent interface for the ReAct planner to observe
    and make decisions based on command execution results.

    ODF-EP v6.0: frozen=True for immutability
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    data: Any  # Raw result data (can be any type)
    error: str | None = None
    metadata: dict[str, Any] = {}

    @property
    def is_retryable(self) -> bool:
        """Check if the error is retryable (transient failure)."""
        if self.error is None:
            return False
        transient_errors = (
            "connection",
            "timeout",
            "network",
            "temporary",
            "rate limit",
            "503",
            "502",
            "504",
        )
        return any(e.lower() in self.error.lower() for e in transient_errors)

    @property
    def retry_count(self) -> int:
        """Get retry count from metadata."""
        return self.metadata.get("retry_count", 0)

    @property
    def duration_ms(self) -> float:
        """Get execution duration from metadata."""
        return self.metadata.get("duration_ms", 0.0)


# =============================================================================
# Skill Command Decorator (Enhanced)
# =============================================================================


def skill_command(
    name: str | None = None,
    category: str = "general",
    description: str | None = None,
    # Dependency Injection Flags
    inject_root: bool = False,
    inject_settings: list[str] | None = None,
    # Retry Configuration
    retry_on: tuple[type[Exception], ...] = (ConnectionError, TimeoutError),
    max_attempts: int = 3,
    #  Caching support
    cache_ttl: float = 0.0,
    pure: bool = False,
):
    """
    [Macro] Mark a function as an exposed skill command with optional DI.

    Enhanced with:
    - Structured CommandResult output
    - Automatic retry for transient failures
    - Context-aware logging
    -  Result caching with TTL

    Args:
        name: Override command name (default: function name)
        category: Grouping for help display (e.g. "git", "file")
        description: Override docstring description
        inject_root: If True, passes 'project_root' (Path) to the function
        inject_settings: List of setting keys to inject (e.g. ["git.path"])
                         Keys are converted to snake_case kwargs (e.g. git_path)
        retry_on: Tuple of exception types to retry on
        max_attempts: Maximum retry attempts (default: 3)
        cache_ttl: Cache time-to-live in seconds (0 = disabled)
        pure: Whether the function is side-effect free (improves caching safety)

    Usage:
        @skill_command(category="git", description="Check git status")
        def git_status(): ...

        @skill_command(category="git", inject_root=True)
        def status(project_root: Path): ...

        @skill_command(category="git", inject_settings=["git.user", "git.email"])
        def setup_config(git_user: str = None, git_email: str = None): ...

        @skill_command(cache_ttl=60.0, pure=True)
        def read_config(): ...  # Read-only operation, cached for 60s
    """

    def decorator(func: Callable) -> Callable:
        # 1. Attach Metadata (used by SkillManager)
        func._is_skill_command = True
        func._skill_config = {
            "name": name or func.__name__,
            "category": category,
            "description": description or _extract_description(func),
            "retry_on": retry_on,
            "max_attempts": max_attempts,
            "input_schema": _get_param_schema(func),
            #  Caching metadata
            "cache_ttl": cache_ttl,
            "pure": pure,
        }

        # 2. Sync Wrapper with Structured Logging
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            log = _get_logger().bind(
                command=name or func.__name__,
                category=category,
            )

            try:
                # Inject Project Root
                if inject_root and "project_root" not in kwargs:
                    kwargs["project_root"] = get_project_root()

                # Inject Settings
                if inject_settings:
                    for key in inject_settings:
                        arg_name = key.replace(".", "_")
                        if arg_name not in kwargs:
                            val = get_setting(key)
                            kwargs[arg_name] = val

                # Execute
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - t0) * 1000

                log.info("command_execution_success", duration_ms=duration_ms)

                return CommandResult(
                    success=True,
                    data=result,
                    metadata={"duration_ms": duration_ms},
                )

            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000
                error_msg = f"{type(e).__name__}: {str(e)}"

                log.error(
                    "command_execution_failed",
                    error=error_msg,
                    duration_ms=duration_ms,
                )

                return CommandResult(
                    success=False,
                    data=None,
                    error=error_msg,
                    metadata={
                        "duration_ms": duration_ms,
                        "exception_type": type(e).__name__,
                        "retryable": isinstance(e, retry_on),
                    },
                )

        # 3. Async Wrapper with Structured Logging
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            log = _get_logger().bind(
                command=name or func.__name__,
                category=category,
            )

            try:
                # Inject Project Root
                if inject_root and "project_root" not in kwargs:
                    kwargs["project_root"] = get_project_root()

                # Inject Settings
                if inject_settings:
                    for key in inject_settings:
                        arg_name = key.replace(".", "_")
                        if arg_name not in kwargs:
                            val = get_setting(key)
                            kwargs[arg_name] = val

                # Execute async function
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - t0) * 1000

                log.info("command_execution_success", duration_ms=duration_ms)

                return CommandResult(
                    success=True,
                    data=result,
                    metadata={"duration_ms": duration_ms},
                )

            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000
                error_msg = f"{type(e).__name__}: {str(e)}"

                log.error(
                    "command_execution_failed",
                    error=error_msg,
                    duration_ms=duration_ms,
                )

                return CommandResult(
                    success=False,
                    data=None,
                    error=error_msg,
                    metadata={
                        "duration_ms": duration_ms,
                        "exception_type": type(e).__name__,
                        "retryable": isinstance(e, retry_on),
                    },
                )

        # Choose wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    # Handle @skill_command without parentheses
    # When used as @skill_command, name receives the decorated function
    if callable(name):
        func = name
        name = None
        return decorator(func)

    return decorator


# =============================================================================
# Structure Validation
# =============================================================================


def get_skill_structure():
    """
    Load ODF-EP v7.0 skill structure from settings.yaml.

    Returns:
        dict with 'required', 'default', 'disallowed' keys
    """
    from common.config.settings import get_setting

    structure = get_setting("skills.architecture.structure", {})
    return {
        "required": [item.get("path", "") for item in structure.get("required", [])],
        "default": [item.get("path", "") for item in structure.get("default", [])],
        "disallowed": structure.get("disallowed_files", []),
    }


def validate_structure(skill_name: str | None = None):
    """
    [Macro] Auto-generate structure validation tests for a skill.

    Reads from assets/settings.yaml (skills.architecture.structure) and
    generates pytest tests that verify:
    - All required files/dirs exist
    - No disallowed files exist
    - Default structure is correct

    Usage in conftest.py or test file:
        from agent.skills.decorators import validate_structure

        # Auto-generate tests for git skill
        validate_structure("git")

    This creates tests:
        test_skill_has_required_files
        test_skill_has_tests_directory
        test_skill_has_no_disallowed_files

    Args:
        skill_name: Skill name (auto-detected from module if not provided)
    """

    def decorator(func: Callable) -> Callable:
        # Get skill name from module
        import sys

        module = sys.modules.get(func.__module__)
        target_skill = skill_name
        if target_skill is None and module:
            parts = module.__name__.split(".")
            if len(parts) >= 2:
                target_skill = parts[-2] if parts[-1] == "tools" else parts[-1]

        # Attach metadata for test generation
        func._validate_skill = target_skill
        return func

    return decorator


def generate_structure_tests(skill_name: str):
    """
    Generate structure validation test functions for a skill.

    This is called by conftest.py to register tests dynamically.

    Args:
        skill_name: Name of the skill to validate

    Returns:
        dict of test_name -> test_function
    """
    from pathlib import Path
    from common.skills_path import SKILLS_DIR

    structure = get_skill_structure()
    skill_path = SKILLS_DIR(skill=skill_name)

    tests = {}

    # Test: Required files exist
    def make_test_required():
        def test():
            for item in structure.get("required", []):
                path = skill_path / item
                assert path.exists(), f"Required {item} must exist"

        return test

    tests["test_skill_has_required_files"] = make_test_required()

    # Test: Disallowed files don't exist
    def make_test_disallowed():
        def test():
            for item in structure.get("disallowed", []):
                path = skill_path / item
                assert not path.exists(), f"Disallowed {item} must NOT exist"

        return test

    tests["test_skill_has_no_disallowed_files"] = make_test_disallowed()

    # Test: Default directories optional (just check they exist if present)
    def make_test_defaults():
        def test():
            for item in structure.get("default", []):
                path = skill_path / item
                if path.exists():
                    assert path.is_dir(), f"{item} should be a directory"

        return test

    tests["test_skill_default_structure"] = make_test_defaults()

    return tests


# =============================================================================
# Utility Functions
# =============================================================================


def _extract_description(func: Callable) -> str:
    """Extract first line of docstring as description."""
    if func.__doc__:
        lines = [line.strip() for line in func.__doc__.split("\n") if line.strip()]
        return lines[0] if lines else ""
    return ""


def _get_param_schema(func: Callable) -> dict:
    """Extract parameter schema from function signature for MCP inputSchema."""
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        # Skip *args and **kwargs
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        # Skip injected parameters
        if param_name in ("project_root",):
            continue

        # Determine type
        param_type = hints.get(param_name, param.annotation)
        if param_type is inspect.Parameter.empty:
            param_type = str

        # Handle Optional types (Union[..., None])
        origin = getattr(param_type, "__origin__", None)
        type_args = getattr(param_type, "__args__", ())

        # Convert to JSON schema type
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        # Check for list in Union args (e.g., Optional[list[str]])
        is_list_type = False
        for arg in type_args:
            arg_origin = getattr(arg, "__origin__", None)
            if arg_origin is list:
                is_list_type = True
                break

        if is_list_type:
            json_type = "array"
        elif origin is list:
            json_type = "array"
        elif origin is Union:
            # Handle Optional[str], Optional[int], etc.
            for arg in type_args:
                if arg not in (type(None), None):
                    json_type = type_map.get(arg, "string")
                    break
            else:
                json_type = "string"
        else:
            json_type = type_map.get(param_type, "string")

        properties[param_name] = {"type": json_type}

        # Check if parameter is required (has no default)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


# =============================================================================
# Skill Script Decorator ( Metadata-Driven Architecture)
# =============================================================================
# Direct decorator for scripts/*.py files - no tools.py router layer needed.
# Auto-detects skill name from file path and registers directly with SkillManager.


_SCRIPT_SKILL_MARKER = "_is_skill_script"


def skill_script(
    name: str | None = None,
    description: str | None = None,
    category: str = "general",
    # Dependency Injection (same as skill_command)
    inject_root: bool = False,
    inject_settings: list[str] | None = None,
    # Retry Configuration
    retry_on: tuple[type[Exception], ...] = (ConnectionError, TimeoutError),
    max_attempts: int = 3,
    #  Caching support
    cache_ttl: float = 0.0,
    pure: bool = False,
):
    """
    [Macro] Mark a function in scripts/*.py as an exposed skill command.

    This decorator is used directly in script files - no tools.py router needed.

    Features:
    - Auto-detects skill name from file path (e.g., git/scripts/commit.py -> skill="git")
    - Auto-generates tool name from function name (e.g., commit -> "git.commit")
    - Stores full metadata for MCP tool registration
    - Supports dependency injection and retry logic
    -  Supports result caching with TTL

    Args:
        name: Override command name (default: function name)
        description: Override docstring description
        category: Grouping for help display (e.g., "write", "read")
        inject_root: If True, passes 'project_root' (Path) to the function
        inject_settings: List of setting keys to inject
        retry_on: Tuple of exception types to retry on
        max_attempts: Maximum retry attempts
        cache_ttl: Cache time-to-live in seconds (0 = disabled)
        pure: Whether the function is side-effect free (improves caching safety)

    Usage (in assets/skills/git/scripts/commit.py):

        from agent.skills.decorators import skill_script

        @skill_script(
            description="Commit staged changes",
            category="write",
            cache_ttl=60.0,  # Cache result for 60 seconds
        )
        def commit(message: str) -> str:
            '''Commit changes to git repository.'''
            # ... implementation ...

    This will be registered as "git.commit" automatically.
    """

    def decorator(func: Callable) -> Callable:
        # Attach script-specific metadata
        func._is_skill_script = True
        func._script_config = {
            "name": name or func.__name__,
            "description": description or _extract_description(func),
            "category": category,
            "retry_on": retry_on,
            "max_attempts": max_attempts,
            "input_schema": _get_param_schema(func),
            "inject_root": inject_root,
            "inject_settings": inject_settings or [],
            #  Caching metadata
            "cache_ttl": cache_ttl,
            "pure": pure,
        }

        # Return the original function (no wrapper for script commands)
        # The SkillLoaderMixin will handle execution with proper context
        return func

    return decorator


def is_skill_script(func: Callable) -> bool:
    """Check if a function is marked with @skill_script."""
    return getattr(func, _SCRIPT_SKILL_MARKER, False)


def get_script_config(func: Callable) -> dict | None:
    """Get the script config attached to a function."""
    return getattr(func, "_script_config", None)


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "skill_command",
    "skill_script",
    "is_skill_script",
    "get_script_config",
    "CommandResult",
    "validate_structure",
    "generate_structure_tests",
    "get_skill_structure",
]
