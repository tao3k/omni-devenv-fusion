"""Tests for shared async dispatch helpers."""

from __future__ import annotations

import asyncio

import pytest

from omni.tracer.async_utils import DispatchMode, dispatch_coroutine


def test_dispatch_coroutine_runs_without_running_loop() -> None:
    state = {"called": False}

    async def _work() -> None:
        state["called"] = True

    dispatch_coroutine(_work())
    assert state["called"] is True


def test_dispatch_coroutine_background_mode_uses_thread(monkeypatch) -> None:
    called = {"thread_started": False}

    class _FakeThread:
        def __init__(self, *, target, args, daemon):
            del daemon
            self._target = target
            self._args = args

        def start(self):
            called["thread_started"] = True
            self._target(*self._args)

    import omni.tracer.async_utils as module

    monkeypatch.setattr(module.threading, "Thread", _FakeThread)

    state = {"called": False}

    async def _work() -> None:
        state["called"] = True

    dispatch_coroutine(_work(), mode=DispatchMode.BACKGROUND)

    assert called["thread_started"] is True
    assert state["called"] is True


@pytest.mark.asyncio
async def test_dispatch_coroutine_schedules_with_running_loop() -> None:
    state = {"called": False}

    async def _work() -> None:
        await asyncio.sleep(0)
        state["called"] = True

    dispatch_coroutine(_work())
    await asyncio.sleep(0.01)
    assert state["called"] is True


@pytest.mark.asyncio
async def test_dispatch_coroutine_tracks_pending_tasks() -> None:
    pending: set[asyncio.Task[None]] = set()

    async def _work() -> None:
        await asyncio.sleep(0)

    dispatch_coroutine(_work(), pending_tasks=pending)
    assert pending
    await asyncio.sleep(0.01)
    assert not pending
