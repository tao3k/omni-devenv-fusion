"""
Async execution helpers for sync call sites.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async_blocking(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine from sync code and return its result.

    Always runs the coroutine in a dedicated worker thread with its own event loop.
    This avoids "event loop is already running" and nested-loop issues when callers
    (e.g. route test) or libraries have already set up a loop.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_coro_in_thread, coro)
        return future.result()


def _run_coro_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in this thread with a new event loop. Used by run_async_blocking."""
    return asyncio.run(coro)


__all__ = [
    "run_async_blocking",
]
