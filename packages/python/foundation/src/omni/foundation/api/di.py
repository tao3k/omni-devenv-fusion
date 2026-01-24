"""
di.py - Dependency Injection Container

Provides dependency injection inspired by Prefect/FastAPI patterns.
- _DIContainer: Simple DI container
- inject_resources: Decorator for auto-wiring dependencies
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, get_type_hints

if TYPE_CHECKING:
    from ..config.paths import ConfigPaths
    from ..config.settings import Settings

# Type variable for generic callable
F = TypeVar("F", bound=Callable[..., Any])


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


def _get_settings() -> Settings:
    """Factory for Settings injection."""
    from ..config.settings import Settings

    return Settings()


def _get_config_paths() -> ConfigPaths:
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
    from ..config.paths import ConfigPaths
    from ..config.settings import Settings

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


__all__ = [
    "_DI_CONFIG_PATHS",
    "_DI_SETTINGS",
    "_DIContainer",
    "_get_config_paths",
    "_get_settings",
    "inject_resources",
]
