"""
MCP Memory Monitor - Diagnose memory leaks during tools/call.

Uses tracemalloc (stdlib) and resource.getrusage to observe RSS before/after
each tool invocation. When growth exceeds threshold, logs top allocations
to help locate leaks (e.g. embedding service, vector cache).

Enable via settings:
  mcp.memory_monitor_enabled: true
  mcp.memory_monitor_threshold_mb: 100  # Log tracemalloc when single call grows by this much

Usage:
  with memory_monitor_scope("knowledge.recall"):
      result = await kernel.execute_tool(...)
"""

from __future__ import annotations

import tracemalloc
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Generator

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting

from .resources import get_process_memory_mb

logger = get_logger("omni.agent.mcp_server.memory_monitor")

_TRACEMALLOC_STARTED = False


def _is_enabled() -> bool:
    """Check if memory monitoring is enabled via settings."""
    try:
        return bool(get_setting("mcp.memory_monitor_enabled"))
    except Exception:
        return False


def _get_threshold_mb() -> float:
    """Get growth threshold in MiB for logging tracemalloc stats."""
    try:
        return float(get_setting("mcp.memory_monitor_threshold_mb") or 100)
    except Exception:
        return 100.0


def _ensure_tracemalloc_started() -> None:
    """Start tracemalloc if not already running (required for get_traced_memory)."""
    global _TRACEMALLOC_STARTED
    if not _TRACEMALLOC_STARTED and tracemalloc.is_tracing() is False:
        tracemalloc.start(10)  # Keep 10 frames
        _TRACEMALLOC_STARTED = True


def _log_tracemalloc_top(count: int = 15) -> None:
    """Log top memory allocations from tracemalloc."""
    if not tracemalloc.is_tracing():
        return
    try:
        snapshot = tracemalloc.take_snapshot()
        top = snapshot.statistics("lineno")[:count]
        logger.warning("[MEMORY] tracemalloc top allocations (possible leak sources):")
        for i, stat in enumerate(top[:5], 1):
            tb_str = "".join(stat.traceback.format())
            logger.warning("  #%d %.2f MiB\n%s", i, stat.size / 1024 / 1024, tb_str)
    except Exception as e:
        logger.debug("tracemalloc snapshot failed: %s", e)


@contextmanager
def memory_monitor_scope(tool_name: str) -> Generator[None, None, None]:
    """Context manager for sync code: log RSS before/after, tracemalloc on large growth."""
    if not _is_enabled():
        yield
        return

    before_mb = get_process_memory_mb()
    if before_mb is None:
        before_mb = 0.0

    _ensure_tracemalloc_started()
    logger.debug("[MEMORY] before %s: RSS=%.1f MiB", tool_name, before_mb)

    try:
        yield
    finally:
        after_mb = get_process_memory_mb()
        if after_mb is not None:
            delta = after_mb - before_mb
            logger.debug(
                "[MEMORY] after %s: RSS=%.1f MiB (delta=%.1f MiB)",
                tool_name,
                after_mb,
                delta,
            )
            threshold = _get_threshold_mb()
            if delta > threshold:
                logger.warning(
                    "[MEMORY] %s grew RSS by %.1f MiB (threshold=%.1f); dumping allocations",
                    tool_name,
                    delta,
                    threshold,
                )
                _log_tracemalloc_top()


@asynccontextmanager
async def amemory_monitor_scope(tool_name: str) -> AsyncIterator[None]:
    """Async context manager: same as memory_monitor_scope for use with async with."""
    if not _is_enabled():
        yield
        return

    before_mb = get_process_memory_mb()
    if before_mb is None:
        before_mb = 0.0

    _ensure_tracemalloc_started()
    logger.debug("[MEMORY] before %s: RSS=%.1f MiB", tool_name, before_mb)

    try:
        yield
    finally:
        after_mb = get_process_memory_mb()
        if after_mb is not None:
            delta = after_mb - before_mb
            logger.debug(
                "[MEMORY] after %s: RSS=%.1f MiB (delta=%.1f MiB)",
                tool_name,
                after_mb,
                delta,
            )
            threshold = _get_threshold_mb()
            if delta > threshold:
                logger.warning(
                    "[MEMORY] %s grew RSS by %.1f MiB (threshold=%.1f); dumping allocations",
                    tool_name,
                    delta,
                    threshold,
                )
                _log_tracemalloc_top()
