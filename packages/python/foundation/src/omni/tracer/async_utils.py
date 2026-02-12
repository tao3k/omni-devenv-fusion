"""
async_utils.py - Shared async dispatch helpers for tracer modules.
"""

from __future__ import annotations

import asyncio
import threading
from enum import Enum
from collections.abc import Coroutine
from typing import Any

from omni.foundation.utils import run_async_blocking


class DispatchMode(str, Enum):
    """Dispatch strategy for coroutine execution from sync code."""

    INLINE = "inline"
    BACKGROUND = "background"


def dispatch_coroutine(
    coro: Coroutine[Any, Any, Any],
    *,
    mode: DispatchMode = DispatchMode.INLINE,
    pending_tasks: set[asyncio.Task[Any]] | None = None,
) -> None:
    """Run or schedule a coroutine safely from sync contexts.

    Behavior:
    - If an event loop is running: schedule with `loop.create_task`.
    - Otherwise:
      - INLINE: run to completion with shared async runner.
      - BACKGROUND: run in a daemon thread with an isolated event loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if mode == DispatchMode.BACKGROUND:
            thread = threading.Thread(target=run_async_blocking, args=(coro,), daemon=True)
            thread.start()
            return
        run_async_blocking(coro)
        return

    task = loop.create_task(coro)
    if pending_tasks is not None:
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)


__all__ = [
    "DispatchMode",
    "dispatch_coroutine",
]
