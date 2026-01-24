"""
decorators.py - Pydantic-Powered Macros

Updated for ODF-EP v6.0 (Pydantic V2 Modernization)
- Uses create_model for automatic OpenAPI schema generation
- Adds inject_resources for dependency injection (Prefect/FastAPI style)

Modularized structure:
- di.py: Dependency Injection Container
- schema.py: Schema Generation
- execution.py: Execution Decorators
"""

from __future__ import annotations

from collections.abc import Callable

# Import from modularized modules for backward compatibility
from .di import (
    _DI_CONFIG_PATHS,
    _DI_SETTINGS,
    _DIContainer,
    _get_config_paths,
    _get_settings,
    inject_resources,
)
from .execution import (
    TimingContext,
    cached,
    measure_time,
    retry,
    trace_execution,
)
from .schema import _generate_tool_schema
from .types import CommandResult

# Re-export for convenience
__all__ = [
    # DI
    "_DIContainer",
    "_DI_SETTINGS",
    "_DI_CONFIG_PATHS",
    "inject_resources",
    "_get_settings",
    "_get_config_paths",
    # Execution
    "trace_execution",
    "measure_time",
    "retry",
    "cached",
    "TimingContext",
    # Schema
    "_generate_tool_schema",
    # Decorators
    "skill_command",
    "is_skill_command",
    "get_script_config",
    "get_tool_annotations",
    "CommandResult",
]


# =============================================================================
# Skill Command Decorator (Metadata-Driven Architecture)
# =============================================================================


def skill_command(
    name: str | None = None,
    description: str | None = None,
    category: str = "general",
    # MCP Tool Annotations (MCP v1.0+ spec)
    title: str | None = None,
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = False,
    # Dependency Injection Configuration
    inject_root: bool = False,
    inject_settings: list[str] | None = None,
    autowire: bool = True,  # Enable generic auto-wiring via inject_resources
    # Execution Control
    retry_on: tuple[type[Exception], ...] | None = None,
    max_attempts: int = 1,
    cache_ttl: float = 0.0,
):
    """
    [Macro] Mark and configure a Skill Command.

    Features:
    - Pre-compute JSON Schema (Fail-fast).
    - Handle DI param schema hiding.
    - Attach metadata for Registry scanning.
    - Auto-wiring: When autowire=True, @inject_resources is applied automatically
      to detect Settings/ConfigPaths type hints and inject them at runtime.
    - MCP Annotations: read_only, destructive, idempotent, open_world for LLM hints.

    MCP Annotations Guide:
    - read_only=True: Tool doesn't modify environment (e.g., read_file)
    - destructive=True: Tool performs destructive updates (e.g., delete_file)
    - idempotent=True: Same input produces same output (e.g., get_info)
    - open_world=True: Tool interacts with external systems (e.g., http_request)
    """
    from ..config.logging import get_logger

    logger = get_logger("omni.api")

    # Build annotations dict per MCP spec
    annotations = {
        "title": title,
        "readOnlyHint": read_only,  # MCP: True = read-only
        "destructiveHint": destructive,  # MCP: True = destructive
        "idempotentHint": idempotent,    # MCP: True = idempotent
        "openWorldHint": open_world,     # MCP: True = external network
    }

    def decorator(func: Callable) -> Callable:
        # Apply auto-wiring decorator if enabled (inject_resources)
        # This wraps the function to inject Settings/ConfigPaths based on type hints
        if autowire:
            func = inject_resources(func)

        # Determine params to hide from schema (Dependency Injection)
        exclude_params = set()
        if inject_root:
            exclude_params.add("project_root")

        # Also hide params that are auto-injected by inject_resources
        # This prevents them from appearing in the JSON Schema
        injected_params = getattr(func, "_injected_params", set())
        exclude_params.update(injected_params)

        # Immediately generate schema - type errors will surface now
        try:
            input_schema = _generate_tool_schema(func, exclude_params)
        except Exception as e:
            logger.warning(f"Failed to generate schema for skill '{func.__name__}': {e}")
            input_schema = {"type": "object", "properties": {}, "required": []}

        # Attach metadata (Protocol)
        func._is_skill_command = True  # type: ignore[attr-defined]
        func._skill_config = {  # type: ignore[attr-defined]
            "name": name or func.__name__,
            "description": description or (func.__doc__ or "").strip().split("\n")[0],
            "category": category,
            "annotations": annotations,
            "input_schema": input_schema,
            "execution": {
                "retry_on": retry_on,
                "max_attempts": max_attempts,
                "cache_ttl": cache_ttl,
                "inject_root": inject_root,
                "inject_settings": inject_settings or [],
                "autowire": autowire,
            },
        }

        return func

    # Support @skill_command without parentheses
    if callable(name):
        func = name
        name = None
        return decorator(func)

    return decorator


def is_skill_command(func: Callable) -> bool:
    """Check if a function is marked with @skill_command."""
    return getattr(func, "_is_skill_command", False)


def get_script_config(func: Callable) -> dict | None:
    """Get the script config attached to a function (for @skill_command)."""
    return getattr(func, "_skill_config", None)


def get_tool_annotations(func: Callable) -> dict | None:
    """Get MCP tool annotations from a skill command function.

    Returns dict with MCP ToolAnnotations fields:
    - title: str | None
    - readOnlyHint: bool | None
    - destructiveHint: bool | None
    - idempotentHint: bool | None
    - openWorldHint: bool | None

    Returns None if function is not a skill command.
    """
    config = get_script_config(func)
    if config:
        return config.get("annotations")
    return None
