"""
decorators.py - Pydantic-Powered Macros

Updated for ODF-EP v6.0 (Pydantic V2 Modernization)
- Uses create_model for automatic OpenAPI schema generation
- Adds inject_resources for dependency injection (Prefect/FastAPI style)
- Adds SkillCommandHandler for unified error handling, logging, and result filtering

Modularized structure:
- di.py: Dependency Injection Container
- schema.py: Schema Generation
- execution.py: Execution Decorators
- handlers.py: Skill Command Handler (v2.2)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

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
from .handlers import (
    ExecutionResult,
    LoggerConfig,
    ResultConfig,
    SkillCommandHandler,
    create_handler,
    ErrorStrategy,
)
from .schema import _generate_tool_schema
from .types import CommandResult

# Re-export for convenience
__all__ = [
    # MCP result contract (for agent/CLI)
    "normalize_mcp_tool_result",
    "is_mcp_canonical_result",
    "MCP_TOOL_RESULT_SCHEMA_V1",
    "MCP_RESULT_CONTENT_KEY",
    "MCP_RESULT_IS_ERROR_KEY",
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
    # Handlers (v2.2)
    "ExecutionResult",
    "LoggerConfig",
    "ResultConfig",
    "SkillCommandHandler",
    "create_handler",
    "ErrorStrategy",
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
# MCP tools/call result – delegate to shared schema API
# =============================================================================

from .mcp_schema import (
    CONTENT_KEY as MCP_RESULT_CONTENT_KEY,
    IS_ERROR_KEY as MCP_RESULT_IS_ERROR_KEY,
    SCHEMA_NAME as MCP_TOOL_RESULT_SCHEMA_V1,
    build_result as _mcp_build_result,
    is_canonical as is_mcp_canonical_result,
)


def _text_from_raw(value: Any) -> str:
    """Serialize a raw return value to display text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def normalize_mcp_tool_result(return_value: Any) -> dict[str, Any]:
    """Normalize any skill return value to MCP tools/call result shape (shared schema API)."""
    if hasattr(return_value, "success") and hasattr(return_value, "data"):
        if return_value.success and return_value.data is not None:
            return normalize_mcp_tool_result(return_value.data)
        return _mcp_build_result(
            getattr(return_value, "error", None) or str(return_value),
            is_error=True,
        )
    if is_mcp_canonical_result(return_value):
        return return_value
    return _mcp_build_result(_text_from_raw(return_value), is_error=False)


def _copy_skill_attrs(
    wrapper: Callable, inner: Callable, original_annotations: dict[str, Any] | None = None
) -> None:
    """Copy skill_command metadata and annotations to wrapper."""
    for attr in ("_is_skill_command", "_skill_config", "_injected_params"):
        if hasattr(inner, attr):
            setattr(wrapper, attr, getattr(inner, attr))
    ann = (
        original_annotations
        if original_annotations is not None
        else getattr(inner, "__annotations__", None)
    )
    if ann:
        wrapper.__annotations__ = dict(ann)
        wrapper.__annotations__["return"] = dict[str, Any]


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
    # Provider Variants Support
    variants: list[str] | None = None,
    default_variant: str | None = None,
    # Dependency Injection Configuration
    inject_root: bool = False,
    inject_settings: list[str] | None = None,
    autowire: bool = True,  # Enable generic auto-wiring via inject_resources
    # Execution Control
    retry_on: tuple[type[Exception], ...] | None = None,
    max_attempts: int = 1,
    cache_ttl: float = 0.0,
    # Execution Handler (v2.2) - Unified error/logging/result handling
    error_strategy: str | None = None,  # "raise", "suppress", "log_only"
    log_level: str | None = None,  # "debug", "info", "warning", "error", "off"
    trace_args: bool = False,
    trace_result: bool = True,
    trace_timing: bool = True,
    filter_empty: bool = True,
    max_result_depth: int = 3,
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
    - Provider Variants: Support multiple implementations (e.g., local, rust, remote).
    - Execution Handler (v2.2): Built-in error handling, logging, and result filtering.

    MCP Annotations Guide:
    - read_only=True: Tool doesn't modify environment (e.g., read_file)
    - destructive=True: Tool performs destructive updates (e.g., delete_file)
    - idempotent=True: Same input produces same output (e.g., get_info)
    - open_world=True: Tool interacts with external systems (e.g., http_request)

    Provider Variants:
    - variants: List of available variant names (e.g., ["local", "rust"])
    - default_variant: Preferred variant when not specified (e.g., "rust")

    Execution Handler (v2.2) - Unified error/logging/result handling:
    - error_strategy: "raise" (default), "suppress", or "log_only"
    - log_level: "debug", "info" (default), "warning", "error", "off"
    - trace_args: Log function arguments (default: False)
    - trace_result: Log successful results (default: True)
    - trace_timing: Log execution timing (default: True)
    - filter_empty: Filter empty dict/list results (default: True)
    - max_result_depth: Max nesting depth for result display (default: 3)

    Usage:
        @skill_command(
            name="my_command",
            error_strategy="suppress",
            log_level="debug",
            trace_args=True,
        )
        def my_command(query: str) -> dict:
            '''Process a query and return result.'''
            ...

    This automatically applies SkillCommandHandler for consistent behavior.
    """
    from ..config.logging import get_logger

    logger = get_logger("omni.api")

    # Build annotations dict per MCP spec - filter out None values
    annotations = {
        "title": title,
        "readOnlyHint": read_only,  # MCP: True = read-only
        "destructiveHint": destructive,  # MCP: True = destructive
        "idempotentHint": idempotent,  # MCP: True = idempotent
        "openWorldHint": open_world,  # MCP: True = external network
    }
    # Filter out None values for cleaner output
    annotations = {k: v for k, v in annotations.items() if v is not None}

    def decorator(func: Callable) -> Callable:
        original_annotations = getattr(func, "__annotations__", None)
        if original_annotations is not None:
            original_annotations = dict(original_annotations)
        # Apply auto-wiring decorator if enabled (inject_resources)
        # This wraps the function to inject Settings/ConfigPaths based on type hints
        if autowire:
            func = inject_resources(func)

        # Apply Execution Handler if any handler params are specified (v2.2)
        # This wraps the function with unified error/logging/result handling
        # Only trigger when at least one handler param is explicitly set to non-default
        handler_config = None
        has_explicit_handler_params = (
            error_strategy is not None  # Non-default: None vs "raise"
            or log_level is not None  # Non-default: None vs "info"
            or trace_args is True  # Non-default: True vs False
            or trace_result is False  # Non-default: False vs True
            or trace_timing is False  # Non-default: False vs True
            or filter_empty is False  # Non-default: False vs True
            or max_result_depth != 3  # Non-default: not 3 vs 3
        )
        if has_explicit_handler_params:
            from .handlers import (
                SkillCommandHandler,
                ErrorStrategy,
                LoggerConfig,
                ResultConfig,
                LogLevel,
            )

            # Determine command name for logging
            cmd_name = name or func.__name__

            # Map log_level string to LogLevel enum
            log_level_enum = LogLevel.INFO
            if log_level:
                log_level_map = {
                    "debug": LogLevel.DEBUG,
                    "info": LogLevel.INFO,
                    "warning": LogLevel.WARNING,
                    "error": LogLevel.ERROR,
                    "off": LogLevel.OFF,
                }
                log_level_enum = log_level_map.get(log_level, LogLevel.INFO)

            # Build handler config
            handler = SkillCommandHandler(
                name=cmd_name,
                error_strategy=ErrorStrategy(error_strategy)
                if error_strategy
                else ErrorStrategy.RAISE,
                log_config=LoggerConfig(
                    level=log_level_enum,
                    trace_args=trace_args,
                    trace_result=trace_result,
                    trace_timing=trace_timing,
                )
                if log_level is not None or trace_args or trace_result or trace_timing
                else None,
                result_config=ResultConfig(
                    filter_empty=filter_empty,
                    max_result_depth=max_result_depth,
                )
                if not filter_empty or max_result_depth != 3
                else None,
            )
            func = handler(func)

            # Store handler config for introspection
            handler_config = {
                "error_strategy": error_strategy or "raise",
                "log_level": log_level or "info",
                "trace_args": trace_args,
                "trace_result": trace_result,
                "trace_timing": trace_timing,
                "filter_empty": filter_empty,
                "max_result_depth": max_result_depth,
            }

        # Determine params to hide from schema (Dependency Injection)
        exclude_params = set()
        if inject_root:
            exclude_params.add("project_root")

        # Also hide params that are auto-injected by inject_resources
        # This prevents them from appearing in the JSON Schema
        injected_params = getattr(func, "_injected_params", set())
        exclude_params.update(injected_params)

        # Get the full description (includes Args section for param extraction)
        full_description = (
            description or (func.__doc__ or "") if description else (func.__doc__ or "")
        )

        # Immediately generate schema - type errors will surface now
        # Pass full_description for parameter description extraction
        try:
            input_schema = _generate_tool_schema(func, exclude_params, full_description)
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
            "variants": variants or [],
            "default_variant": default_variant,
            "input_schema": input_schema,
            "execution": {
                "retry_on": retry_on,
                "max_attempts": max_attempts,
                "cache_ttl": cache_ttl,
                "inject_root": inject_root,
                "inject_settings": inject_settings or [],
                "autowire": autowire,
                "handler": handler_config,
            },
        }

        # Register in global registry for schema generation
        # Use lazy import to avoid circular dependency
        from omni.core.skills.tools_loader import _skill_command_registry

        full_name = f"{category}.{name or func.__name__}"
        _skill_command_registry[full_name] = func

        # Note: Validation registry registration is handled by ToolsLoader._register_for_validation()
        # when the skill is loaded. This avoids circular dependency issues.

        # One wrapper: run inner then normalize; sync/async chosen once
        import asyncio

        _inner = func
        _is_async = asyncio.iscoroutinefunction(_inner)

        async def _async_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            out = await _inner(*args, **kwargs)
            return normalize_mcp_tool_result(out)

        def _sync_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            out = _inner(*args, **kwargs)
            return normalize_mcp_tool_result(out)

        wrapper = _async_run if _is_async else _sync_run
        wrapper.__name__ = _inner.__name__
        wrapper.__doc__ = _inner.__doc__
        _copy_skill_attrs(wrapper, _inner, original_annotations)
        return wrapper

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


# =============================================================================
# Skill Resource Decorator (MCP Resource Registration)
# =============================================================================


def skill_resource(
    name: str | None = None,
    description: str | None = None,
    resource_uri: str | None = None,
    mime_type: str = "application/json",
):
    """Decorator to mark a function as an MCP Resource provider.

    Unlike ``@skill_command`` (Tool — executes actions), ``@skill_resource``
    declares a **read-only data endpoint** exposed via ``resources/read``.

    The function is called when the MCP client reads the resource URI.

    Example::

        @skill_resource(
            name="status",
            description="Git repository status",
            resource_uri="omni://skill/git/status",
        )
        async def git_status() -> dict:
            return {"branch": "main", "clean": True}

    Args:
        name: Resource name (defaults to function name).
        description: Human-readable description.
        resource_uri: Full MCP resource URI (e.g. ``omni://skill/git/status``).
            If omitted, the server will expose as ``omni://skill/{skill_name}/{name}``.
        mime_type: MIME type for the resource content.
    """

    def decorator(func: Callable) -> Callable:
        resource_name = name or func.__name__
        resource_desc = description or (func.__doc__ or "").strip().split("\n")[0]

        func._is_skill_resource = True  # type: ignore[attr-defined]
        func._resource_config = {  # type: ignore[attr-defined]
            "name": resource_name,
            "description": resource_desc,
            "resource_uri": resource_uri,
            "mime_type": mime_type,
        }
        return func

    # Support bare @skill_resource without parentheses
    if callable(name):
        func = name
        name = None
        return decorator(func)

    return decorator


def is_skill_resource(func: Callable) -> bool:
    """Check if a function is marked with @skill_resource."""
    return getattr(func, "_is_skill_resource", False)


def get_resource_config(func: Callable) -> dict | None:
    """Get the resource config attached to a function (for @skill_resource)."""
    return getattr(func, "_resource_config", None)


# =============================================================================
# Prompt Decorator (MCP Prompt Template Registration)
# =============================================================================


def prompt(
    name: str | None = None,
    description: str | None = None,
):
    """Decorator to mark a function as an MCP Prompt template.

    The function receives prompt arguments (e.g. from MCP get_prompt) and
    returns the prompt content (string or list of messages).

    Example::

        @prompt(
            name="analyze_code",
            description="Code analysis template",
        )
        def analyze_code(file_path: str) -> str:
            return f'''
        请分析 {file_path}:
        1. 代码结构
        2. 潜在问题
        '''

    Args:
        name: Prompt name (defaults to function name).
        description: Human-readable description for list_prompts.
    """

    def decorator(func: Callable) -> Callable:
        prompt_name = name or func.__name__
        prompt_desc = description or (func.__doc__ or "").strip().split("\n")[0]

        func._is_prompt = True  # type: ignore[attr-defined]
        func._prompt_config = {  # type: ignore[attr-defined]
            "name": prompt_name,
            "description": prompt_desc,
        }
        return func

    if callable(name):
        func = name
        name = None
        return decorator(func)

    return decorator


def is_prompt(func: Callable) -> bool:
    """Check if a function is marked with @prompt."""
    return getattr(func, "_is_prompt", False)


def get_prompt_config(func: Callable) -> dict | None:
    """Get the prompt config attached to a function (for @prompt)."""
    return getattr(func, "_prompt_config", None)
