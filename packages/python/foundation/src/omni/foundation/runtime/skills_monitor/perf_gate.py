"""Shared helpers for knowledge.recall performance gate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class RecallPerfRun:
    """Single measured run for knowledge.recall gate."""

    elapsed_ms: float
    rss_peak_delta_mb: float
    ok: bool
    row_budget_rss_peak_delta_max_mb: float | None = None
    row_budget_memory_observed: bool = False
    error: str = ""


@dataclass(frozen=True)
class RecallPerfSummary:
    """Aggregated metrics and gate verdict inputs."""

    total_runs: int
    ok_runs: int
    failed_runs: int
    p95_ms: float
    rss_peak_delta_max_mb: float
    elapsed_avg_ms: float
    row_budget_memory_observed_runs: int
    row_budget_rss_peak_delta_max_mb: float


def extract_status_and_error(result: Any) -> tuple[str, str]:
    """Extract normalized (status, error) from raw/canonical skill results."""
    from omni.foundation.api.mcp_schema import parse_result_payload

    candidate: Any = result
    if not isinstance(candidate, dict | str):
        if hasattr(candidate, "to_dict") and callable(candidate.to_dict):
            candidate = candidate.to_dict()
        elif hasattr(candidate, "model_dump") and callable(candidate.model_dump):
            candidate = candidate.model_dump()
        elif hasattr(candidate, "dict") and callable(candidate.dict):
            candidate = candidate.dict()

    canonical_is_error: bool | None = None
    if isinstance(candidate, dict):
        raw_flag = candidate.get("isError")
        if isinstance(raw_flag, bool):
            canonical_is_error = raw_flag

    payload: dict[str, Any] | None = None
    try:
        parsed = parse_result_payload(candidate)
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = None

    if payload is None and isinstance(candidate, dict):
        payload = candidate
    if payload is None:
        return "unknown", ""

    status = str(payload.get("status", "")).strip().lower()
    error_value = payload.get("error")
    error = str(error_value) if isinstance(error_value, str) else ""

    if not status:
        if canonical_is_error is True or error:
            status = "error"
        elif canonical_is_error is False:
            status = "success"
        else:
            status = "unknown"

    if canonical_is_error is True and status == "success":
        status = "error"

    return status, error


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    """Return nearest-rank percentile value (P95 -> ceil(0.95*N)-1)."""
    if not values:
        return 0.0
    if percentile <= 0:
        return min(values)
    if percentile >= 100:
        return max(values)
    ordered = sorted(values)
    rank = max(1, ceil((percentile / 100.0) * len(ordered)))
    return float(ordered[rank - 1])


def summarize_runs(runs: list[RecallPerfRun]) -> RecallPerfSummary:
    """Aggregate recall performance runs into a summary."""
    total = len(runs)
    ok_runs = [r for r in runs if r.ok]
    failed_runs = total - len(ok_runs)
    elapsed_values = [float(r.elapsed_ms) for r in ok_runs]
    peak_values = [float(r.rss_peak_delta_mb) for r in ok_runs]
    row_budget_peak_values = [
        float(r.row_budget_rss_peak_delta_max_mb)
        for r in ok_runs
        if isinstance(r.row_budget_rss_peak_delta_max_mb, int | float)
    ]
    row_budget_observed_runs = sum(1 for r in ok_runs if bool(r.row_budget_memory_observed))
    p95_ms = percentile_nearest_rank(elapsed_values, 95.0) if elapsed_values else 0.0
    avg_ms = (sum(elapsed_values) / len(elapsed_values)) if elapsed_values else 0.0
    max_peak = max(peak_values) if peak_values else 0.0
    return RecallPerfSummary(
        total_runs=total,
        ok_runs=len(ok_runs),
        failed_runs=failed_runs,
        p95_ms=float(p95_ms),
        rss_peak_delta_max_mb=float(max_peak),
        elapsed_avg_ms=float(avg_ms),
        row_budget_memory_observed_runs=int(row_budget_observed_runs),
        row_budget_rss_peak_delta_max_mb=float(
            max(row_budget_peak_values) if row_budget_peak_values else 0.0
        ),
    )


def evaluate_gate(
    summary: RecallPerfSummary,
    *,
    max_p95_ms: float,
    max_rss_peak_delta_mb: float,
    max_failures: int,
    max_row_budget_rss_peak_delta_mb: float,
    min_row_budget_memory_observed_runs: int = 1,
) -> tuple[bool, list[str]]:
    """Evaluate gate verdict and return (passed, failure_reasons)."""
    failures: list[str] = []
    if summary.failed_runs > max_failures:
        failures.append(f"failed_runs={summary.failed_runs} exceeds max_failures={max_failures}")
    if summary.ok_runs == 0:
        failures.append("no successful recall runs")
    if summary.p95_ms > max_p95_ms:
        failures.append(f"p95_ms={summary.p95_ms:.1f} exceeds max_p95_ms={max_p95_ms:.1f}")
    if summary.rss_peak_delta_max_mb > max_rss_peak_delta_mb:
        failures.append(
            "rss_peak_delta_max_mb="
            f"{summary.rss_peak_delta_max_mb:.1f} exceeds max_rss_peak_delta_mb="
            f"{max_rss_peak_delta_mb:.1f}"
        )
    required_observed_runs = max(0, int(min_row_budget_memory_observed_runs))
    if summary.row_budget_memory_observed_runs < required_observed_runs:
        failures.append(
            "row_budget_memory_observed_runs="
            f"{summary.row_budget_memory_observed_runs} below "
            f"min_row_budget_memory_observed_runs={required_observed_runs}"
        )
    if summary.row_budget_rss_peak_delta_max_mb > max_row_budget_rss_peak_delta_mb:
        failures.append(
            "row_budget_rss_peak_delta_max_mb="
            f"{summary.row_budget_rss_peak_delta_max_mb:.1f} exceeds "
            "max_row_budget_rss_peak_delta_mb="
            f"{max_row_budget_rss_peak_delta_mb:.1f}"
        )
    return (len(failures) == 0, failures)


__all__ = [
    "RecallPerfRun",
    "RecallPerfSummary",
    "evaluate_gate",
    "extract_status_and_error",
    "percentile_nearest_rank",
    "summarize_runs",
]
