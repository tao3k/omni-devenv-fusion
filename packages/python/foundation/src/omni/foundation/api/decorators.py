"""
decorators.py - Pydantic-Powered Macros

Updated for ODF-EP v6.0 (Pydantic V2 Modernization)
- Uses create_model for automatic OpenAPI schema generation
- Replaces legacy manual introspection in utils/introspection.py
- Adds inject_resources for dependency injection (Prefect/FastAPI style)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Type, TypeVar, get_type_hints

from pydantic import create_model, Field

from ..config.logging import get_logger
from .types import CommandResult

if TYPE_CHECKING:
    from ..config.paths import ConfigPaths
    from ..config.settings import Settings

logger = get_logger("omni.api")

# Type variable for generic callable
F = TypeVar("F", bound=Callable[..., Any])

# Default parameters to exclude from public schema (Dependency Injection)
_INJECTED_PARAMS = frozenset({"project_root", "root_path", "settings"})

# Type references that should be excluded from schema (non-Pydantic types)
_INJECTED_TYPES = frozenset()


# =============================================================================
# Dependency Injection Container (Inspired by Prefect/FastAPI)
# =============================================================================


class _DIContainer:
    """
    Simple Dependency Injection Container.

    Maps type hints to factory functions for auto-wiring.
    """

    _bindings: dict[str, Callable] = {}

    @classmethod
    def bind(cls, key: str, factory: Callable) -> None:
        """Bind a key to a factory function."""
        cls._bindings[key] = factory

    @classmethod
    def resolve(cls, key: str) -> Any:
        """Resolve a key to its instance."""
        factory = cls._bindings.get(key)
        if factory:
            return factory()
        return None

    @classmethod
    def clear(cls) -> None:
        """Clear all bindings (useful for testing)."""
        cls._bindings.clear()


# Keys for dependency injection
_DI_SETTINGS = "settings"
_DI_CONFIG_PATHS = "config_paths"


def _get_settings() -> "Settings":
    """Factory for Settings injection."""
    from ..config.settings import Settings

    return Settings()


def _get_config_paths() -> "ConfigPaths":
    """Factory for ConfigPaths injection."""
    from ..config.paths import get_config_paths

    return get_config_paths()


# Register factories
_DIContainer.bind(_DI_SETTINGS, _get_settings)
_DIContainer.bind(_DI_CONFIG_PATHS, _get_config_paths)


# =============================================================================
# Dependency Injection Decorator (Zero-Cost Abstraction)
# =============================================================================


def inject_resources(func: F) -> F:
    """
    [Macro] Automatic Dependency Injection.

    Detects function parameter type hints and injects infrastructure objects:
    - settings: Settings
    - paths: ConfigPaths
    - logger: BoundLogger (coming soon)

    Injected parameters are automatically excluded from JSON Schema generation.

    Usage:
        @inject_resources
        def my_command(
            param1: str,
            settings: Settings,  # Auto-injected
            paths: ConfigPaths   # Auto-injected
        ):
            api_key = settings.get("api.key")
            log_dir = paths.get_log_dir()
            ...

    This is equivalent to Prefect's dependency injection pattern.
    """
    # Import here for lazy evaluation (avoid circular imports)
    from ..config.settings import Settings
    from ..config.paths import ConfigPaths

    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    # Detect which parameters can be injected
    injectables: dict[str, str] = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        hint = type_hints.get(name)
        if hint is Settings:
            injectables[name] = _DI_SETTINGS
        elif hint is ConfigPaths:
            injectables[name] = _DI_CONFIG_PATHS

    if not injectables:
        return func

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        # Inject dependencies at runtime
        for name, key in injectables.items():
            if name not in kwargs:
                kwargs[name] = _DIContainer.resolve(key)
        return await func(*args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        for name, key in injectables.items():
            if name not in kwargs:
                kwargs[name] = _DIContainer.resolve(key)
        return func(*args, **kwargs)

    # Attach metadata for schema generation
    wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    wrapper._injected_params = set(injectables.keys())  # type: ignore[attr-defined]

    return wrapper  # type: ignore[return-value]


# =============================================================================
# Pydantic V2 Schema Generation (Replaces legacy introspection.py)
# =============================================================================


def _generate_tool_schema(func: Callable, exclude_params: set[str] | None = None) -> dict[str, Any]:
    """
    [Core Algorithm] Auto-generate OpenAPI Schema using Pydantic V2 reflection.

    Principle:
    1. Analyze function signature and type annotations.
    2. Dynamically build a Pydantic Model (create_model) to represent parameter structure.
    3. Export standard Schema via .model_json_schema().
    """
    if exclude_params is None:
        exclude_params = set()

    sig = inspect.signature(func)

    # Get resolved type hints (handles ForwardRef, etc.)
    try:
        type_hints = get_type_hints(func, include_extras=True)
    except Exception:
        # Fallback to raw annotations if type resolution fails
        type_hints = {n: p.annotation for n, p in sig.parameters.items()}

    # Lazy import Settings to avoid circular dependency
    from ..config.settings import Settings
    from ..config.paths import ConfigPaths

    # Build a set of types to exclude from schema generation
    _INJECTED_TYPES_SET = {Settings, ConfigPaths}

    fields = {}

    for param_name, param in sig.parameters.items():
        # 1. Filter out dependency injection params (e.g., project_root) and *args/**kwargs
        if param_name in exclude_params or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = type_hints.get(param_name, Any)

        # 2. Filter out infrastructure types that can't be serialized by Pydantic
        # Settings, ConfigPaths, etc. are injected at runtime and shouldn't appear in schema
        # Handle both direct type and Union types (e.g., Optional[Settings])

        # Check if annotation is an injected type or contains one (e.g., Union[Settings, None])
        is_injected = False
        if annotation in _INJECTED_TYPES_SET:
            is_injected = True
        else:
            # Handle both typing.Union (Optional[X]) and types.UnionType (X | None)
            from typing import get_origin, get_args, Union as TypingUnion
            import types

            origin = get_origin(annotation)
            # Check for typing.Union (Optional[X]) or Python 3.10+ types.UnionType (X | None)
            if origin is TypingUnion or origin is types.UnionType:
                args = get_args(annotation)
                if any(arg in _INJECTED_TYPES_SET for arg in args):
                    is_injected = True

        if is_injected:
            continue

        default = param.default

        # 3. Build field definition: (Type, DefaultValue)
        # If no default, Pydantic uses ... (Ellipsis) to indicate required
        if default == inspect.Parameter.empty:
            fields[param_name] = (annotation, ...)
        else:
            fields[param_name] = (annotation, default)

    # 3. Dynamically create model
    # model_name doesn't matter much, just for schema generation
    DynamicModel = create_model(f"{func.__name__}Args", **fields)
    full_schema = DynamicModel.model_json_schema()

    return {
        "type": "object",
        "properties": full_schema.get("properties", {}),
        "required": full_schema.get("required", []),
    }


def _extract_description(func: Callable) -> str:
    """Extract first line of docstring as description."""
    if func.__doc__:
        lines = [line.strip() for line in func.__doc__.split("\n") if line.strip()]
        return lines[0] if lines else ""
    return ""


# =============================================================================
# Execution Decorators
# =============================================================================


def trace_execution(
    op_name: str | None = None,
    log_args: bool = False,
    log_result: bool = False,
) -> Callable[[F], F]:
    """Trace function execution with timing and logging."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = op_name or func.__name__
            start = time.perf_counter()
            try:
                logger.debug(f"Starting: {name}")
                if log_args:
                    logger.debug(f"  Args: {args}, kwargs: {kwargs}")
                result = await func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"Finished: {name} in {duration:.2f}ms")
                if log_result:
                    logger.debug(f"  Result: {result}")
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.error(f"Failed: {name} after {duration:.2f}ms - {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = op_name or func.__name__
            start = time.perf_counter()
            try:
                logger.debug(f"Starting: {name}")
                if log_args:
                    logger.debug(f"  Args: {args}, kwargs: {kwargs}")
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"Finished: {name} in {duration:.2f}ms")
                if log_result:
                    logger.debug(f"  Result: {result}")
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.error(f"Failed: {name} after {duration:.2f}ms - {e}")
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore

    return decorator


def measure_time(unit: str = "ms") -> Callable[[F], F]:
    """Measure and log function execution time."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            logger.debug(f"{func.__name__}: {duration * _TIME_MULTIPLIERS[unit]:.2f}{unit}")
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            logger.debug(f"{func.__name__}: {duration * _TIME_MULTIPLIERS[unit]:.2f}{unit}")
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore

    return decorator


_TIME_MULTIPLIERS = {
    "s": 1.0,
    "ms": 1000.0,
    "us": 1_000_000.0,
    "ns": 1_000_000_000.0,
}


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry a function with exponential backoff."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {current_delay:.2f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {e}")
                        raise

            raise last_exception  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {current_delay:.2f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {e}")
                        raise

            raise last_exception  # type: ignore

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore

    return decorator


class TimingContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str, logger_obj: Any | None = None):
        self.name = name
        self.logger = logger_obj or logger
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> TimingContext:
        self.start_time = time.perf_counter()
        self.logger.debug(f"Starting: {self.name}")
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000
        self.logger.debug(f"Finished: {self.name} in {duration_ms:.2f}ms")

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time


def cached(maxsize: int = 128, ttl: float | None = None) -> Callable[[F], F]:
    """Simple cache decorator with optional TTL."""

    def decorator(func: F) -> F:
        cache: dict[str, tuple[float, Any]] = {}

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time as time_module

            key = f"{args}:{kwargs}"
            now = time_module.time()

            if key in cache:
                expires_at, result = cache[key]
                if ttl is None or now < expires_at:
                    return result
                del cache[key]

            result = await func(*args, **kwargs)
            cache[key] = (now + (ttl or float("inf")), result)

            if len(cache) > maxsize:
                cache.pop(next(iter(cache)))

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time as time_module

            key = f"{args}:{kwargs}"
            now = time_module.time()

            if key in cache:
                expires_at, result = cache[key]
                if ttl is None or now < expires_at:
                    return result
                del cache[key]

            result = func(*args, **kwargs)
            cache[key] = (now + (ttl or float("inf")), result)

            if len(cache) > maxsize:
                cache.pop(next(iter(cache)))

            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# Skill Command Decorator (Metadata-Driven Architecture)
# =============================================================================


def skill_command(
    name: str | None = None,
    description: str | None = None,
    category: str = "general",
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
    """

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


__all__ = [
    "trace_execution",
    "measure_time",
    "retry",
    "TimingContext",
    "cached",
    "inject_resources",
    "skill_command",
    "is_skill_command",
    "get_script_config",
    "CommandResult",
]
