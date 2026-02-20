"""Context and instrumentation for skills monitor."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .monitor import SkillsMonitor

_current_monitor: contextvars.ContextVar[SkillsMonitor | None] = contextvars.ContextVar(
    "skills_monitor", default=None
)
_suppress_skill_command_phase: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "skills_monitor_suppress_skill_command_phase", default=False
)


def get_current_monitor() -> SkillsMonitor | None:
    """Return the active SkillsMonitor for the current context, if any."""
    return _current_monitor.get(None)


def set_current_monitor(monitor: SkillsMonitor | None) -> contextvars.Token:
    """Set the current monitor and return token for reset."""
    return _current_monitor.set(monitor)


def reset_current_monitor(token: contextvars.Token) -> None:
    """Restore previous monitor state."""
    _current_monitor.reset(token)


def is_skill_command_phase_suppressed() -> bool:
    """Return True when skill_command.execute monitor events should be suppressed."""
    return bool(_suppress_skill_command_phase.get(False))


def set_skill_command_phase_suppressed(suppressed: bool) -> contextvars.Token:
    """Set suppression flag for skill_command.execute events and return token."""
    return _suppress_skill_command_phase.set(bool(suppressed))


def reset_skill_command_phase_suppressed(token: contextvars.Token) -> None:
    """Restore previous suppression flag state."""
    _suppress_skill_command_phase.reset(token)


@contextmanager
def suppress_skill_command_phase_events():
    """Suppress nested skill_command.execute phase events within current context."""
    token = set_skill_command_phase_suppressed(True)
    try:
        yield
    finally:
        reset_skill_command_phase_suppressed(token)


def record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record a phase event to the current monitor (if active)."""
    if phase == "skill_command.execute" and is_skill_command_phase_suppressed():
        return
    mon = get_current_monitor()
    if mon is not None:
        mon.record_phase(phase, duration_ms, **extra)


def record_rust_db(op: str, duration_ms: float, **extra: Any) -> None:
    """Record a Rust/DB event to the current monitor (if active)."""
    mon = get_current_monitor()
    if mon is not None:
        mon.record_rust_db(op, duration_ms, **extra)
