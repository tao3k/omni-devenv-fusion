"""
api.py - Foundation API Decorators and Utilities

Provides standardized decorators for:
- Execution tracing, timing, retry, caching
- Dependency injection
- Schema generation
- Skill command decorator with MCP annotations

Usage:
    from omni.foundation.api import trace_execution, measure_time, retry
    from omni.foundation.api.decorators import skill_command
"""

# Lazy exports - avoid importing at module level
_lazy_exports = None


def __getattr__(name: str):
    """Lazy load api submodules."""
    global _lazy_exports

    if _lazy_exports is None:
        from . import decorators

        _lazy_exports = decorators

    return getattr(_lazy_exports, name)


def __dir__():
    """List available attributes for autocomplete."""
    from . import decorators

    return [
        # Execution decorators
        "trace_execution",
        "measure_time",
        "retry",
        "TimingContext",
        "cached",
        # DI
        "inject_resources",
        "_DIContainer",
        "_DI_SETTINGS",
        "_DI_CONFIG_PATHS",
        "_get_settings",
        "_get_config_paths",
        # Schema
        "_generate_tool_schema",
        # Skill command
        "skill_command",
        "is_skill_command",
        "get_script_config",
        "get_tool_annotations",
        "CommandResult",
    ]
