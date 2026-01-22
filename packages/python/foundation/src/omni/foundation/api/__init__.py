"""
api.py - Foundation API Decorators and Utilities

Provides standardized decorators for:
- Execution tracing
- Error handling
- Retry logic
- Performance measurement

Usage:
    from omni.foundation.api import trace_execution, measure_time, retry
"""

# Lazy exports - avoid importing at module level
_lazy_decorators = None


def __getattr__(name: str):
    """Lazy load api submodules."""
    global _lazy_decorators

    if name in (
        "trace_execution",
        "measure_time",
        "retry",
        "TimingContext",
        "cached",
    ):
        if _lazy_decorators is None:
            from . import decorators

            _lazy_decorators = decorators
        return getattr(_lazy_decorators, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """List available attributes for autocomplete."""
    return [
        "trace_execution",
        "measure_time",
        "retry",
        "TimingContext",
        "cached",
    ]
