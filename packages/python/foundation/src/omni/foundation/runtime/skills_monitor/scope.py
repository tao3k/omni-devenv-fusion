"""Context managers for skills monitor scope."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from omni.foundation.config.logging import get_logger

from .context import reset_current_monitor, set_current_monitor
from .monitor import SkillsMonitor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = get_logger(__name__)


@asynccontextmanager
async def skills_monitor_scope(
    skill_command: str,
    *,
    sample_interval_s: float = 1.0,
    verbose: bool = False,
    output_json: bool = False,
    auto_report: bool = True,
) -> AsyncIterator[SkillsMonitor]:
    """Async context manager for monitoring skill execution."""
    token = set_current_monitor(None)
    monitor = SkillsMonitor(
        skill_command,
        sample_interval_s=sample_interval_s,
        verbose=verbose,
    )
    set_current_monitor(monitor)
    monitor.start_sampler()
    try:
        yield monitor
    finally:
        try:
            monitor.stop_sampler()
        except Exception as e:
            logger.debug("skills_monitor_stop_failed", skill_command=skill_command, error=str(e))
        try:
            if auto_report:
                monitor.report(output_json=output_json)
        except Exception as e:
            logger.debug("skills_monitor_report_failed", skill_command=skill_command, error=str(e))
        try:
            reset_current_monitor(token)
        except Exception as e:
            logger.debug("skills_monitor_reset_failed", skill_command=skill_command, error=str(e))


def run_with_monitor[T](
    skill_command: str,
    coro_fn: Callable[[], Awaitable[T]],
    *,
    sample_interval_s: float = 1.0,
    verbose: bool = False,
    output_json: bool = False,
    auto_report: bool = True,
) -> T:
    """
    Run an async coroutine under monitor scope (for sync callers).

    Example:
        result = run_with_monitor(
            "knowledge.recall",
            lambda: run_skill("knowledge", "recall", {"query": "..."}),
            verbose=True,
        )
    """

    async def _wrapped() -> T:
        async with skills_monitor_scope(
            skill_command,
            sample_interval_s=sample_interval_s,
            verbose=verbose,
            output_json=output_json,
            auto_report=auto_report,
        ):
            return await coro_fn()

    return asyncio.run(_wrapped())
