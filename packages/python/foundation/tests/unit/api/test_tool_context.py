"""Tests for unified MCP-style tool execution context and idle/total timeout."""

from __future__ import annotations

import asyncio
import time

import pytest

from omni.foundation.api.tool_context import (
    clear_tool_context,
    get_tool_context,
    heartbeat,
    run_with_heartbeat,
    run_with_idle_timeout,
    set_tool_context,
)


@pytest.fixture(autouse=True)
def _clear_context():
    yield
    clear_tool_context()


async def test_run_with_idle_timeout_total_only_completes():
    """With idle_timeout_s=0, only total cap applies; coro completes within cap."""

    async def work():
        await asyncio.sleep(0.05)
        return 42

    result = await run_with_idle_timeout(work(), total_timeout_s=1.0, idle_timeout_s=0)
    assert result == 42


async def test_run_with_idle_timeout_total_only_times_out():
    """With idle_timeout_s=0, total timeout raises TimeoutError."""

    async def work():
        await asyncio.sleep(2.0)
        return 1

    with pytest.raises(asyncio.TimeoutError):
        await run_with_idle_timeout(work(), total_timeout_s=0.1, idle_timeout_s=0)


async def test_run_with_idle_timeout_heartbeat_keeps_alive():
    """With idle_timeout_s set, repeated heartbeat() prevents idle cancel; total cap still applies."""

    async def work():
        for _ in range(8):
            await asyncio.sleep(0.2)
            heartbeat()
        return "done"

    # Idle 0.5s would kill if no heartbeat; we heartbeat every 0.2s. Total 2s cap.
    result = await run_with_idle_timeout(work(), total_timeout_s=3.0, idle_timeout_s=0.5)
    assert result == "done"


async def test_run_with_idle_timeout_returns_promptly_after_task_completion():
    """Completed task should return immediately (no extra wait for check interval)."""

    async def work():
        await asyncio.sleep(0.05)
        heartbeat()
        return "ok"

    started = time.monotonic()
    result = await run_with_idle_timeout(work(), total_timeout_s=5.0, idle_timeout_s=3.0)
    elapsed = time.monotonic() - started

    assert result == "ok"
    assert elapsed < 0.8


async def test_run_with_idle_timeout_idle_cancel():
    """When no heartbeat for idle_timeout_s, TimeoutError with 'idle' message."""

    async def work():
        await asyncio.sleep(0.1)
        heartbeat()
        await asyncio.sleep(2.0)  # no heartbeat -> idle timeout
        return "never"

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        await run_with_idle_timeout(work(), total_timeout_s=10.0, idle_timeout_s=0.4)
    assert "idle" in str(exc_info.value).lower() or "No progress" in str(exc_info.value)


async def test_run_with_heartbeat_keeps_idle_alive():
    """run_with_heartbeat sends periodic heartbeat so idle_timeout does not fire."""

    async def long_work():
        await asyncio.sleep(0.8)
        return "ok"

    # Run inside idle timeout: idle 0.4s would kill; run_with_heartbeat keeps alive
    result = await run_with_idle_timeout(
        run_with_heartbeat(long_work(), interval_s=0.2),
        total_timeout_s=2.0,
        idle_timeout_s=0.4,
    )
    assert result == "ok"


async def test_set_tool_context_allows_heartbeat():
    """heartbeat() updates last_activity when context is set."""
    ctx = set_tool_context()
    t0 = ctx["last_activity"][0]
    time.sleep(0.02)
    heartbeat()
    t1 = ctx["last_activity"][0]
    assert t1 >= t0
    clear_tool_context()
    heartbeat()  # no-op when no context
    assert get_tool_context() is None
