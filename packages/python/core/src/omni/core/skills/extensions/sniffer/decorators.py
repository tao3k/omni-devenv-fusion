"""
decorators.py - Sniffer Decorators for Asset-Driven Detection

Define @sniffer decorator for registering custom detection logic.

Usage:
    from omni.core.skills.extensions.sniffer import sniffer

    @sniffer(name="detect_venv", priority=200)
    def detect_virtualenv(cwd: str) -> float:
        '''Return score 0.0-1.0 indicating skill relevance.'''
        return 1.0 if os.path.exists(os.path.join(cwd, "venv")) else 0.0
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class SnifferFunc(Protocol):
    """Protocol for sniffer functions.

    Sniffer functions detect whether a skill is relevant for a given directory.
    They receive a directory path and return a score between 0.0 (no match)
    and 1.0 (strong match).

    Example:
        @sniffer(name="detect_venv")
        def detect(cwd: str) -> float:
            return 1.0 if os.path.exists(os.path.join(cwd, "venv")) else 0.0

    Can be used for runtime type checking:
        >>> if isinstance(func, SnifferFunc):
        ...     score = func("/some/path")
    """

    def __call__(self, cwd: str) -> float: ...


def sniffer(name: str | None = None, priority: int = 100):
    """
    Decorator: Mark a function as a sniffer.

    The sniffer function receives a directory path and returns a score
    between 0.0 (no match) and 1.0 (strong match). Scores above 0.5
    typically indicate the skill should be activated.

    Args:
        name: Sniffer name (defaults to function name)
        priority: Execution priority (higher = runs first, default 100)

    Example:
        @sniffer(name="check_venv")
        def detect(cwd: str) -> float:
            return 1.0 if os.path.exists(os.path.join(cwd, "venv")) else 0.0
    """

    def decorator(func: SnifferFunc) -> SnifferFunc:
        # Mark function with sniffer metadata
        func._is_sniffer = True  # type: ignore[attr-defined]
        func._sniffer_name = name or func.__name__  # type: ignore[attr-defined]
        func._sniffer_priority = priority  # type: ignore[attr-defined]
        return func

    return decorator


class SnifferResult:
    """Result of a sniffer check."""

    def __init__(
        self,
        skill_name: str,
        score: float,
        reason: str = "",
    ):
        self.skill_name = skill_name
        self.score = score
        self.reason = reason

    def __repr__(self) -> str:
        return f"SnifferResult({self.skill_name}, score={self.score:.2f})"

    def __lt__(self, other: SnifferResult) -> bool:
        return self.score < other.score

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SnifferResult):
            return False
        return self.skill_name == other.skill_name and self.score == other.score


__all__ = ["SnifferFunc", "SnifferResult", "sniffer"]
