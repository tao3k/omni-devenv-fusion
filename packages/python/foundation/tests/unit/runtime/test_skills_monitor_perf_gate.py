"""Unit tests for skills_monitor perf gate helpers."""

from __future__ import annotations

from omni.foundation.runtime.skills_monitor.perf_gate import (
    RecallPerfRun,
    evaluate_gate,
    extract_status_and_error,
    percentile_nearest_rank,
    summarize_runs,
)


def test_percentile_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile_nearest_rank(values, 0.0) == 10.0
    assert percentile_nearest_rank(values, 50.0) == 30.0
    assert percentile_nearest_rank(values, 95.0) == 50.0
    assert percentile_nearest_rank(values, 100.0) == 50.0


def test_summarize_runs_uses_only_success_runs_for_metrics() -> None:
    runs = [
        RecallPerfRun(
            elapsed_ms=100.0,
            rss_peak_delta_mb=20.0,
            ok=True,
            row_budget_rss_peak_delta_max_mb=11.0,
            row_budget_memory_observed=True,
        ),
        RecallPerfRun(
            elapsed_ms=200.0,
            rss_peak_delta_mb=25.0,
            ok=True,
            row_budget_rss_peak_delta_max_mb=13.0,
            row_budget_memory_observed=True,
        ),
        RecallPerfRun(elapsed_ms=999.0, rss_peak_delta_mb=999.0, ok=False, error="boom"),
    ]
    summary = summarize_runs(runs)
    assert summary.total_runs == 3
    assert summary.ok_runs == 2
    assert summary.failed_runs == 1
    assert summary.elapsed_avg_ms == 150.0
    assert summary.p95_ms == 200.0
    assert summary.rss_peak_delta_max_mb == 25.0
    assert summary.row_budget_memory_observed_runs == 2
    assert summary.row_budget_rss_peak_delta_max_mb == 13.0


def test_evaluate_gate_passes_within_thresholds() -> None:
    summary = summarize_runs(
        [
            RecallPerfRun(
                elapsed_ms=100.0,
                rss_peak_delta_mb=20.0,
                ok=True,
                row_budget_rss_peak_delta_max_mb=10.0,
                row_budget_memory_observed=True,
            ),
            RecallPerfRun(
                elapsed_ms=120.0,
                rss_peak_delta_mb=22.0,
                ok=True,
                row_budget_rss_peak_delta_max_mb=12.0,
                row_budget_memory_observed=True,
            ),
        ]
    )
    passed, failures = evaluate_gate(
        summary,
        max_p95_ms=150.0,
        max_rss_peak_delta_mb=40.0,
        max_failures=0,
        max_row_budget_rss_peak_delta_mb=20.0,
        min_row_budget_memory_observed_runs=1,
    )
    assert passed is True
    assert failures == []


def test_evaluate_gate_reports_failure_reasons() -> None:
    summary = summarize_runs(
        [
            RecallPerfRun(
                elapsed_ms=200.0,
                rss_peak_delta_mb=50.0,
                ok=True,
                row_budget_rss_peak_delta_max_mb=45.0,
                row_budget_memory_observed=True,
            ),
            RecallPerfRun(
                elapsed_ms=210.0,
                rss_peak_delta_mb=55.0,
                ok=True,
                row_budget_rss_peak_delta_max_mb=50.0,
                row_budget_memory_observed=True,
            ),
            RecallPerfRun(elapsed_ms=0.0, rss_peak_delta_mb=0.0, ok=False, error="timeout"),
        ]
    )
    passed, failures = evaluate_gate(
        summary,
        max_p95_ms=150.0,
        max_rss_peak_delta_mb=40.0,
        max_failures=0,
        max_row_budget_rss_peak_delta_mb=30.0,
        min_row_budget_memory_observed_runs=1,
    )
    assert passed is False
    assert any("failed_runs" in item for item in failures)
    assert any("p95_ms" in item for item in failures)
    assert any("rss_peak_delta_max_mb" in item for item in failures)
    assert any("row_budget_rss_peak_delta_max_mb" in item for item in failures)


def test_evaluate_gate_fails_when_row_budget_memory_not_observed() -> None:
    summary = summarize_runs(
        [
            RecallPerfRun(elapsed_ms=110.0, rss_peak_delta_mb=20.0, ok=True),
            RecallPerfRun(elapsed_ms=120.0, rss_peak_delta_mb=22.0, ok=True),
        ]
    )
    passed, failures = evaluate_gate(
        summary,
        max_p95_ms=150.0,
        max_rss_peak_delta_mb=40.0,
        max_failures=0,
        max_row_budget_rss_peak_delta_mb=30.0,
        min_row_budget_memory_observed_runs=1,
    )
    assert passed is False
    assert any("row_budget_memory_observed_runs" in item for item in failures)


def test_extract_status_and_error_parses_canonical_success_payload() -> None:
    status, error = extract_status_and_error(
        {
            "content": [{"type": "text", "text": '{"status":"success","results":[]}'}],
            "isError": False,
        }
    )
    assert status == "success"
    assert error == ""


def test_extract_status_and_error_uses_iserror_for_non_json_payload() -> None:
    status, error = extract_status_and_error(
        {
            "content": [{"type": "text", "text": "non-json text"}],
            "isError": False,
        }
    )
    assert status == "success"
    assert error == ""


def test_extract_status_and_error_parses_error_payload() -> None:
    status, error = extract_status_and_error(
        {
            "content": [{"type": "text", "text": '{"status":"error","error":"boom"}'}],
            "isError": True,
        }
    )
    assert status == "error"
    assert error == "boom"
