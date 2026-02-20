"""Utilities for MCP tools/list concurrency sweep analysis."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """One concurrency point in a tools/list benchmark sweep."""

    concurrency: int
    total: int
    errors: int
    elapsed_s: float
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


@dataclass(frozen=True, slots=True)
class SweepRecommendation:
    """Recommended concurrency with SLO and throughput context."""

    recommended_concurrency: int | None
    reason: str
    feasible_concurrency: tuple[int, ...]
    knee_concurrency: int | None


def recommended_http_pool_limits(
    max_concurrency: int,
    *,
    min_connections: int = 64,
    headroom: int = 16,
) -> tuple[int, int]:
    """Return `(max_connections, max_keepalive_connections)` for stable sweep load."""
    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be > 0")
    if min_connections <= 0:
        raise ValueError("min_connections must be > 0")
    if headroom < 0:
        raise ValueError("headroom must be >= 0")
    target = max(min_connections, max_concurrency + headroom)
    return (target, target)


def detect_knee_concurrency(
    points: Iterable[SweepPoint],
    *,
    min_p95_jump_ratio: float = 1.8,
    max_rps_ratio: float = 0.8,
) -> int | None:
    """
    Detect first knee point where tail latency sharply increases and throughput drops.

    Heuristic:
    - current p95 / previous p95 >= min_p95_jump_ratio
    - current rps / previous rps <= max_rps_ratio
    """
    ordered = sorted(points, key=lambda point: point.concurrency)
    if len(ordered) < 2:
        return None
    for previous, current in pairwise(ordered):
        if previous.p95_ms <= 0 or previous.rps <= 0:
            continue
        p95_ratio = current.p95_ms / previous.p95_ms
        rps_ratio = current.rps / previous.rps
        if p95_ratio >= min_p95_jump_ratio and rps_ratio <= max_rps_ratio:
            return current.concurrency
    return None


def recommend_concurrency_by_slo(
    points: Iterable[SweepPoint],
    *,
    p95_slo_ms: float,
    p99_slo_ms: float,
) -> SweepRecommendation:
    """
    Recommend a concurrency using SLO gating first, then max throughput.

    Rules:
    - Keep only points with `errors == 0`, `p95 <= p95_slo`, `p99 <= p99_slo`.
    - Pick the feasible point with highest RPS.
    - If none is feasible, return highest-RPS point overall as fallback.
    """
    ordered = sorted(points, key=lambda point: point.concurrency)
    if not ordered:
        return SweepRecommendation(
            recommended_concurrency=None,
            reason="no data points",
            feasible_concurrency=(),
            knee_concurrency=None,
        )

    feasible = [
        point
        for point in ordered
        if point.errors == 0 and point.p95_ms <= p95_slo_ms and point.p99_ms <= p99_slo_ms
    ]
    knee = detect_knee_concurrency(ordered)
    if feasible:
        winner = max(feasible, key=lambda point: (point.rps, -point.p95_ms, -point.p99_ms))
        return SweepRecommendation(
            recommended_concurrency=winner.concurrency,
            reason="selected highest-RPS point within SLO bounds",
            feasible_concurrency=tuple(point.concurrency for point in feasible),
            knee_concurrency=knee,
        )

    fallback = max(ordered, key=lambda point: (point.rps, -point.p95_ms, -point.p99_ms))
    return SweepRecommendation(
        recommended_concurrency=fallback.concurrency,
        reason="no point satisfied SLO; selected highest-RPS fallback",
        feasible_concurrency=(),
        knee_concurrency=knee,
    )
