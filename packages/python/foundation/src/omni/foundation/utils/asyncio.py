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

    If already inside an event loop, execute the coroutine in an isolated
    worker thread to avoid nested-loop hacks.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


__all__ = [
    "run_async_blocking",
]
