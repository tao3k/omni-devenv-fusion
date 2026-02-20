"""
tool_context.py - Unified execution context for long-running tool calls (MCP + CLI).

Single timeout interface: both MCP server and CLI skill runner call
run_with_execution_timeout(coro). Config (mcp.timeout, mcp.idle_timeout) is read
in one place; no per-caller logic.

Usage:
  - Runner (MCP or CLI): call run_with_execution_timeout(coro). Do not read
    timeout config or call run_with_idle_timeout directly.
  - Skill (e.g. researcher): call run_with_heartbeat(coro) or heartbeat() during
    long work. Works identically in MCP and CLI.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")

# Context is set by the MCP server (or other runner) before invoking the tool.
# Tools read it and call heartbeat() during long work.
_tool_context_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "tool_execution_context", default=None
)


def set_tool_context(last_activity: list[float] | None = None) -> dict[str, Any]:
    """Create and set execution context for this async context. Returns the context dict."""
    if last_activity is None:
        last_activity = [time.monotonic()]

    def heartbeat() -> None:
        last_activity[0] = time.monotonic()

    ctx: dict[str, Any] = {
        "last_activity": last_activity,
        "heartbeat": heartbeat,
    }
    _tool_context_var.set(ctx)
    return ctx


def get_tool_context() -> dict[str, Any] | None:
    """Get current tool execution context, if any. Used by skills to call heartbeat()."""
    return _tool_context_var.get()


def clear_tool_context() -> None:
    """Clear the context (e.g. after tool completes)."""
    _tool_context_var.set(None)


def heartbeat() -> None:
    """No-op if no context; otherwise update last_activity. Call this during long work."""
    ctx = _tool_context_var.get()
    if ctx and "heartbeat" in ctx:
        ctx["heartbeat"]()


_HEARTBEAT_INTERVAL_S = 10.0


async def run_with_heartbeat(
    coro: Coroutine[Any, Any, T], interval_s: float = _HEARTBEAT_INTERVAL_S
) -> T:
    """Run a coroutine with periodic heartbeat so MCP idle_timeout does not kill long work.

    Use this inside tools that perform long-running work (LLM calls, parsing, embedding).
    The runner's idle_timeout cancels only when no heartbeat for N seconds; this keeps
    progress visible.

    Args:
        coro: The coroutine to run (e.g. long pipeline steps).
        interval_s: Seconds between heartbeat calls; default 10.

    Returns:
        The result of the coroutine.
    """
    stop = asyncio.Event()
    hb_task: asyncio.Task | None = None

    async def _loop() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_s)
            except asyncio.TimeoutError:
                heartbeat()

    hb_task = asyncio.create_task(_loop())
    try:
        return await coro
    finally:
        stop.set()
        if hb_task:
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass


async def run_with_idle_timeout(
    coro: Coroutine[Any, Any, T],
    total_timeout_s: float,
    idle_timeout_s: float = 0,
) -> T:
    """Run a coroutine under the unified MCP-style timeout and heartbeat framework.

    Sets tool_context so that any code inside the coroutine can call heartbeat()
    to signal progress. Enforces:
    - Hard cap: total_timeout_s (wall-clock).
    - If idle_timeout_s > 0: cancel when no heartbeat for idle_timeout_s (no progress).

    Args:
        coro: The tool coroutine to run (e.g. kernel.execute_tool(...)).
        total_timeout_s: Maximum wall-clock seconds; 0 = no cap.
        idle_timeout_s: If > 0, cancel when last_activity is older than this many
            seconds. 0 = only use total_timeout_s (no heartbeat check).

    Returns:
        The result of the coroutine.

    Raises:
        asyncio.TimeoutError: On total or idle timeout, with message indicating which.
    """
    ctx = set_tool_context()
    try:
        if idle_timeout_s <= 0:
            if total_timeout_s and total_timeout_s > 0:
                return await asyncio.wait_for(coro, timeout=total_timeout_s)
            return await coro
        # Idle + total: run coro and a watcher that checks last_activity and elapsed
        start = time.monotonic()
        task = asyncio.create_task(coro)
        check_interval = max(0.5, min(5.0, idle_timeout_s / 3))
        total_cap = total_timeout_s if total_timeout_s > 0 else float("inf")
        while True:
            done, _pending = await asyncio.wait({task}, timeout=check_interval)
            if task in done:
                break
            now = time.monotonic()
            last = ctx["last_activity"][0]
            if now - last >= idle_timeout_s:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise asyncio.TimeoutError(
                    f"No progress for {idle_timeout_s}s (idle timeout). "
                    "Tool should call heartbeat() during long work."
                )
            if now - start >= total_cap:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise asyncio.TimeoutError(f"Tool exceeded wall-clock limit of {total_timeout_s}s.")
        return task.result()
    finally:
        clear_tool_context()


def get_execution_timeout_config() -> tuple[float, float]:
    """Get (total_timeout_s, idle_timeout_s) from config. Single source for MCP and CLI."""
    try:
        from omni.foundation.config.paths import get_config_paths

        paths = get_config_paths()
        total = paths.get_mcp_timeout(None) or 1800
        idle = paths.get_mcp_idle_timeout(None) or 0
        total_s = float(total)
        idle_s = float(idle)
        if total_s <= 0:
            total_s = 1800.0
        return total_s, idle_s
    except Exception:
        return 1800.0, 0.0


async def run_with_execution_timeout(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine with unified timeout and heartbeat. Use this from MCP and CLI.

    Reads mcp.timeout and mcp.idle_timeout from config. Sets tool_context so
    heartbeat() works. Do not duplicate this logic in callers.
    """
    total_s, idle_s = get_execution_timeout_config()
    return await run_with_idle_timeout(
        coro,
        total_timeout_s=total_s,
        idle_timeout_s=idle_s,
    )
