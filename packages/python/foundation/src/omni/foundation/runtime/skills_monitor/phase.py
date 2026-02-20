"""Common phase instrumentation helpers for skills monitor."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any


def sample_memory() -> tuple[float | None, float | None]:
    """Return current RSS and RSS peak in MiB for phase attribution."""
    try:
        from . import metrics

        return float(metrics.get_rss_mb()), float(metrics.get_rss_peak_mb())
    except Exception:
        return None, None


def build_memory_delta_fields(
    rss_before: float | None,
    rss_peak_before: float | None,
    rss_after: float | None,
    rss_peak_after: float | None,
) -> dict[str, float]:
    """Build optional memory fields for monitor phase payloads."""
    fields: dict[str, float] = {}
    if rss_before is not None and rss_after is not None:
        fields["rss_before_mb"] = round(rss_before, 2)
        fields["rss_after_mb"] = round(rss_after, 2)
        fields["rss_delta_mb"] = round(rss_after - rss_before, 2)
    if rss_peak_before is not None and rss_peak_after is not None:
        fields["rss_peak_before_mb"] = round(rss_peak_before, 2)
        fields["rss_peak_after_mb"] = round(rss_peak_after, 2)
        fields["rss_peak_delta_mb"] = round(rss_peak_after - rss_peak_before, 2)
    return fields


def start_phase_sample() -> tuple[float, float | None, float | None]:
    """Capture phase start timestamp and memory baseline."""
    rss_before, rss_peak_before = sample_memory()
    return time.perf_counter(), rss_before, rss_peak_before


def record_phase_with_memory(
    phase: str,
    started_at: float,
    rss_before: float | None,
    rss_peak_before: float | None,
    **extra: Any,
) -> None:
    """Record phase duration plus memory delta to active skills monitor."""
    rss_after, rss_peak_after = sample_memory()
    _record_phase(
        phase,
        (time.perf_counter() - started_at) * 1000,
        **extra,
        **build_memory_delta_fields(rss_before, rss_peak_before, rss_after, rss_peak_after),
    )


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Route phase event through public skills_monitor API when available."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase as record_phase_api

        record_phase_api(phase, duration_ms, **extra)
        return
    except Exception:
        pass

    try:
        from .context import record_phase as record_phase_ctx

        record_phase_ctx(phase, duration_ms, **extra)
    except Exception:
        return


@contextmanager
def phase_scope(phase: str, extra: dict[str, Any] | None = None):
    """Context manager to measure phase duration + memory delta."""
    started_at, rss_before, rss_peak_before = start_phase_sample()
    payload = extra if extra is not None else {}
    try:
        yield payload
    finally:
        record_phase_with_memory(
            phase,
            started_at,
            rss_before,
            rss_peak_before,
            **payload,
        )


__all__ = [
    "build_memory_delta_fields",
    "phase_scope",
    "record_phase_with_memory",
    "sample_memory",
    "start_phase_sample",
]
