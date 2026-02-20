"""
Skill execution lifecycle hooks.

Invoked by the skill runner (core) before and after each skill command execution.
Used by the agent to set the embedding override so that skills use MCP-first
embedding when running from CLI (outside the MCP server process).
"""

from __future__ import annotations

from collections.abc import Callable

_before_skill_execute: list[Callable[[], None]] = []
_after_skill_execute: list[Callable[[], None]] = []


def register_before_skill_execute(cb: Callable[[], None]) -> None:
    """Register a callback to run before each skill command execution."""
    _before_skill_execute.append(cb)


def register_after_skill_execute(cb: Callable[[], None]) -> None:
    """Register a callback to run after each skill command execution."""
    _after_skill_execute.append(cb)


def run_before_skill_execute() -> None:
    """Run all registered before-execute callbacks (e.g. set embedding override)."""
    for cb in _before_skill_execute:
        try:
            cb()
        except Exception:
            pass


def run_after_skill_execute() -> None:
    """Run all registered after-execute callbacks (e.g. clear embedding override)."""
    for cb in _after_skill_execute:
        try:
            cb()
        except Exception:
            pass


__all__ = [
    "register_before_skill_execute",
    "register_after_skill_execute",
    "run_before_skill_execute",
    "run_after_skill_execute",
]
