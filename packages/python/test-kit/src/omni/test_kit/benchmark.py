"""Scale benchmark helpers: latency thresholds and assertions.

Used by benchmark tests in test-kit to avoid regression on skills/core paths.
Run benchmark tests with: just test-benchmarks (from repo root).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


def assert_sync_latency_under_ms(
    fn: Callable[[], T],
    threshold_ms: float,
    iterations: int = 5,
) -> T:
    """Run sync fn N times; assert average latency < threshold_ms. Returns last result."""
    latencies: list[float] = []
    last: Any = None
    for _ in range(iterations):
        start = time.perf_counter()
        last = fn()
        latencies.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < threshold_ms, (
        f"Average latency {avg_ms:.1f}ms exceeds threshold {threshold_ms}ms (n={iterations})"
    )
    return last  # type: ignore[return-value]


async def assert_async_latency_under_ms(
    coro_fn: Callable[[], Awaitable[T]],
    threshold_ms: float,
    iterations: int = 5,
) -> T:
    """Run async coro_fn N times; assert average latency < threshold_ms. Returns last result."""
    latencies: list[float] = []
    last: Any = None
    for _ in range(iterations):
        start = time.perf_counter()
        last = await coro_fn()
        latencies.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < threshold_ms, (
        f"Average latency {avg_ms:.1f}ms exceeds threshold {threshold_ms}ms (n={iterations})"
    )
    return last  # type: ignore[return-value]
