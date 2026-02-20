"""Unit tests for tools/list sweep analysis utilities."""

from __future__ import annotations

import pytest

from omni.agent.mcp_server.tools_list_sweep import (
    SweepPoint,
    detect_knee_concurrency,
    recommend_concurrency_by_slo,
    recommended_http_pool_limits,
)


def test_recommended_http_pool_limits_adds_headroom() -> None:
    max_connections, max_keepalive_connections = recommended_http_pool_limits(120)
    assert max_connections == 136
    assert max_keepalive_connections == 136


def test_recommended_http_pool_limits_respects_minimum() -> None:
    max_connections, max_keepalive_connections = recommended_http_pool_limits(20)
    assert max_connections == 64
    assert max_keepalive_connections == 64


def test_recommended_http_pool_limits_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency must be > 0"):
        recommended_http_pool_limits(0)


def test_detect_knee_concurrency_returns_first_matching_jump() -> None:
    points = [
        SweepPoint(40, 1000, 0, 1.20, 800.0, 30.0, 140.0, 190.0),
        SweepPoint(80, 1000, 0, 1.15, 820.0, 60.0, 260.0, 390.0),
        SweepPoint(120, 1000, 0, 0.95, 1060.0, 80.0, 309.0, 373.0),
        SweepPoint(160, 1000, 0, 1.48, 673.0, 151.0, 664.0, 1042.0),
    ]
    assert detect_knee_concurrency(points) == 160


def test_recommend_concurrency_prefers_highest_rps_within_slo() -> None:
    points = [
        SweepPoint(40, 1000, 0, 1.20, 800.0, 30.0, 140.0, 190.0),
        SweepPoint(80, 1000, 0, 1.15, 820.0, 60.0, 260.0, 390.0),
        SweepPoint(120, 1000, 0, 0.95, 1060.0, 80.0, 309.0, 373.0),
        SweepPoint(160, 1000, 0, 1.48, 673.0, 151.0, 664.0, 1042.0),
    ]
    recommendation = recommend_concurrency_by_slo(points, p95_slo_ms=400.0, p99_slo_ms=500.0)
    assert recommendation.recommended_concurrency == 120
    assert recommendation.feasible_concurrency == (40, 80, 120)
    assert recommendation.knee_concurrency == 160


def test_recommend_concurrency_falls_back_when_slo_not_met() -> None:
    points = [
        SweepPoint(40, 1000, 0, 1.20, 800.0, 30.0, 440.0, 590.0),
        SweepPoint(80, 1000, 0, 1.15, 920.0, 60.0, 560.0, 790.0),
        SweepPoint(120, 1000, 0, 0.95, 1000.0, 80.0, 609.0, 873.0),
    ]
    recommendation = recommend_concurrency_by_slo(points, p95_slo_ms=300.0, p99_slo_ms=450.0)
    assert recommendation.recommended_concurrency == 120
    assert recommendation.feasible_concurrency == ()
    assert recommendation.reason.startswith("no point satisfied SLO")
