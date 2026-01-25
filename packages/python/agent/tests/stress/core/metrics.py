"""
core/metrics.py - Metrics Collection Module

Independent metrics collection for stress testing.
Can be used without the full agent stack.
"""

from __future__ import annotations

import gc
import os
import time
from contextlib import contextmanager
from typing import Any

import psutil
from pydantic import BaseModel


class MemorySnapshot(BaseModel):
    """Memory state at a point in time."""

    rss_mb: float
    vms_mb: float
    timestamp: float
    turn: int


class TestMetrics(BaseModel):
    """Metrics collected during a stress test."""

    test_name: str = "unknown"
    start_time: float = 0.0
    end_time: float | None = None
    memory_snapshots: list[MemorySnapshot] = []
    custom_metrics: dict[str, Any] = {}

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    @property
    def peak_memory_mb(self) -> float:
        if not self.memory_snapshots:
            return 0.0
        return max(s.rss_mb for s in self.memory_snapshots)

    @property
    def avg_memory_mb(self) -> float:
        if not self.memory_snapshots:
            return 0.0
        return sum(s.rss_mb for s in self.memory_snapshots) / len(self.memory_snapshots)

    def memory_growth_mb(self) -> float:
        if len(self.memory_snapshots) < 2:
            return 0.0
        return self.memory_snapshots[-1].rss_mb - self.memory_snapshots[0].rss_mb


class MetricsCollector:
    """
    Independent metrics collector for stress tests.

    Usage:
        collector = MetricsCollector()
        collector.start()
        # ... run test ...
        collector.snapshot(turn=1)
        # ... more test ...
        metrics = collector.stop()
        print(f"Memory growth: {metrics.memory_growth_mb:.2f} MB")
    """

    def __init__(self, process: psutil.Process | None = None):
        self._process = process or psutil.Process(os.getpid())
        self._snapshots: list[MemorySnapshot] = []
        self._start_time: float | None = None
        self._running = False

    def start(self) -> None:
        """Start metrics collection."""
        gc.collect()  # Clean slate
        self._start_time = time.time()
        self._running = True
        self._snapshots = []

    def snapshot(self, turn: int = 0) -> MemorySnapshot:
        """Capture current memory state."""
        if not self._running:
            raise RuntimeError("MetricsCollector not started")

        gc.collect()  # Force cleanup before measuring
        mem_info = self._process.memory_info()
        snapshot = MemorySnapshot(
            rss_mb=mem_info.rss / 1024 / 1024,
            vms_mb=mem_info.vms / 1024 / 1024,
            timestamp=time.time(),
            turn=turn,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def stop(self, test_name: str = "stress_test") -> TestMetrics:
        """Stop collection and return final metrics."""
        if not self._running:
            raise RuntimeError("MetricsCollector not started")

        self._running = False
        end_time = time.time()

        return TestMetrics(
            test_name=test_name,
            start_time=self._start_time or time.time(),
            end_time=end_time,
            memory_snapshots=self._snapshots,
        )

    def reset(self) -> None:
        """Reset collector state."""
        self._snapshots = []
        self._start_time = None
        self._running = False


@contextmanager
def measure_memory(test_name: str = "test"):
    """
    Context manager for quick memory measurement.

    Usage:
        with measure_memory("my_test") as metrics:
            # run code
            pass
        print(f"Growth: {metrics.memory_growth_mb:.2f} MB")
    """
    collector = MetricsCollector()
    collector.start()
    try:
        yield collector
    finally:
        collector.stop()


class MemoryThresholdChecker:
    """Check if memory growth exceeds thresholds."""

    def __init__(
        self,
        warning_threshold_mb: float = 50.0,
        error_threshold_mb: float = 100.0,
    ):
        self.warning_threshold = warning_threshold_mb
        self.error_threshold = error_threshold_mb
        self.last_check_result: tuple[bool, str] = (True, "")

    def check(self, growth_mb: float) -> tuple[bool, str]:
        """
        Check if memory growth is within thresholds.

        Returns:
            (passed: bool, message: str)
        """
        if growth_mb > self.error_threshold:
            result = (
                False,
                f"CRITICAL: Memory growth {growth_mb:.1f}MB exceeds error threshold {self.error_threshold}MB",
            )
        elif growth_mb > self.warning_threshold:
            result = (
                False,
                f"WARNING: Memory growth {growth_mb:.1f}MB exceeds warning threshold {self.warning_threshold}MB",
            )
        else:
            result = (True, f"OK: Memory growth {growth_mb:.1f}MB within limits")

        self.last_check_result = result
        return result


__all__ = [
    "MemorySnapshot",
    "MemoryThresholdChecker",
    "MetricsCollector",
    "TestMetrics",
    "measure_memory",
]
