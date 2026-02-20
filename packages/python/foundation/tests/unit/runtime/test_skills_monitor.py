"""Unit tests for skills monitor internals."""

from __future__ import annotations

import asyncio
import io

import pytest

from omni.foundation.runtime.skills_monitor.context import (
    record_phase,
    reset_current_monitor,
    set_current_monitor,
    suppress_skill_command_phase_events,
)
from omni.foundation.runtime.skills_monitor.monitor import SkillsMonitor
from omni.foundation.runtime.skills_monitor.reporters.summary_reporter import SummaryReporter
from omni.foundation.runtime.skills_monitor.scope import skills_monitor_scope
from omni.foundation.runtime.skills_monitor.types import MonitorReport, Sample


class _StopSignal:
    def __init__(self) -> None:
        self.called = False

    def set(self) -> None:
        self.called = True


class _PendingTask:
    def __init__(self) -> None:
        self.cancel_called = False
        self.result_called = False

    def cancel(self) -> None:
        self.cancel_called = True

    def done(self) -> bool:
        return False

    def result(self) -> None:
        self.result_called = True
        raise AssertionError("result() must not be called for pending task")


class _DoneCancelledTask:
    def __init__(self) -> None:
        self.cancel_called = False
        self.result_called = False

    def cancel(self) -> None:
        self.cancel_called = True

    def done(self) -> bool:
        return True

    def result(self) -> None:
        self.result_called = True
        raise asyncio.CancelledError()


def test_stop_sampler_does_not_call_result_for_pending_task() -> None:
    """Pending sampler task should be cancelled without touching task.result()."""
    monitor = SkillsMonitor("knowledge.recall")
    pending = _PendingTask()

    stop = _StopSignal()
    monitor._sampler_stop = stop  # type: ignore[assignment]
    monitor._sampler_task = pending  # type: ignore[assignment]
    monitor._take_sample = lambda: None  # type: ignore[method-assign]

    monitor.stop_sampler()

    assert pending.cancel_called is True
    assert pending.result_called is False
    assert stop.called is True
    assert monitor._sampler_task is None


def test_stop_sampler_allows_done_cancelled_task() -> None:
    """Done+cancelled sampler task should not leak CancelledError."""
    monitor = SkillsMonitor("knowledge.recall")
    task = _DoneCancelledTask()

    stop = _StopSignal()
    monitor._sampler_stop = stop  # type: ignore[assignment]
    monitor._sampler_task = task  # type: ignore[assignment]
    monitor._take_sample = lambda: None  # type: ignore[method-assign]

    monitor.stop_sampler()

    assert task.cancel_called is True
    assert task.result_called is True
    assert stop.called is True
    assert monitor._sampler_task is None


def test_build_report_includes_current_and_peak_rss(monkeypatch) -> None:
    """Report should include both current RSS and peak RSS deltas."""
    monitor = SkillsMonitor("knowledge.recall")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.monitor.get_rss_mb",
        lambda: 108.5,
    )
    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.monitor.get_rss_peak_mb",
        lambda: 150.0,
    )

    report = monitor.build_report()
    assert report.rss_start_mb == 100.0
    assert report.rss_end_mb == 108.5
    assert round(report.rss_delta_mb, 1) == 8.5
    assert report.rss_peak_start_mb == 120.0
    assert report.rss_peak_end_mb == 150.0
    assert round(report.rss_peak_delta_mb, 1) == 30.0

    payload = report.to_dict()
    assert payload["rss_mb"]["delta"] == 8.5
    assert payload["rss_peak_mb"]["delta"] == 30.0
    assert payload["link_graph_signals"] is None
    assert payload["retrieval_signals"] is None


def test_monitor_report_to_dict_validates_signal_schema() -> None:
    """MonitorReport.to_dict should enforce shared signal schema validation."""
    report = MonitorReport(
        skill_command="knowledge.recall",
        elapsed_sec=0.1,
        rss_start_mb=100.0,
        rss_end_mb=101.0,
        rss_delta_mb=1.0,
        rss_peak_start_mb=100.0,
        rss_peak_end_mb=101.0,
        rss_peak_delta_mb=1.0,
        cpu_avg_percent=0.0,
        phases=[],
        rust_db_events=[],
        samples_count=1,
        link_graph_signals=None,
        retrieval_signals={"bad": True},
    )

    with pytest.raises(ValueError, match="skills monitor signals schema violation"):
        report.to_dict()


def test_build_report_includes_machine_readable_retrieval_signals() -> None:
    """Report JSON should include aggregated retrieval row-budget signals."""
    monitor = SkillsMonitor("knowledge.recall")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monitor.record_phase(
        "retrieval.rows.semantic",
        18.0,
        mode="semantic",
        collection="knowledge_chunks",
        fetch_limit=5,
        rows_fetched=7,
        rows_parsed=7,
        rows_returned=5,
        rows_capped=2,
        rss_delta_mb=8.5,
        rss_peak_delta_mb=9.0,
    )
    monitor.record_phase(
        "retrieval.rows.hybrid",
        21.0,
        mode="hybrid",
        collection="knowledge_chunks",
        fetch_limit=3,
        rows_fetched=6,
        rows_parsed=4,
        rows_returned=3,
        rows_capped=1,
        rows_parse_dropped=2,
        rss_delta_mb=2.0,
        rss_peak_delta_mb=2.5,
    )

    report = monitor.build_report()
    payload = report.to_dict()
    signals = payload["retrieval_signals"]
    assert isinstance(signals, dict)
    row_budget = signals["row_budget"]
    assert row_budget["count"] == 2
    assert row_budget["query_count"] == 0
    assert row_budget["backend_count"] == 2
    assert row_budget["rows_fetched_sum"] == 13
    assert row_budget["rows_parsed_sum"] == 11
    assert row_budget["rows_returned_sum"] == 8
    assert row_budget["rows_capped_sum"] == 3
    assert row_budget["rows_parse_dropped_sum"] == 2
    assert row_budget["memory"]["observed_count"] == 2
    assert row_budget["memory"]["rss_delta_sum"] == 10.5
    assert row_budget["memory"]["rss_peak_delta_sum"] == 11.5
    assert row_budget["memory"]["rss_delta_max"] == 8.5
    assert row_budget["memory"]["rss_peak_delta_max"] == 9.0
    assert row_budget["modes"]["semantic"]["count"] == 1
    assert row_budget["modes"]["hybrid"]["count"] == 1


def test_build_report_retrieval_signals_prefers_query_event_for_return_budget() -> None:
    """When query event exists, returned/capped sums should come from query-level output."""
    monitor = SkillsMonitor("knowledge.recall")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monitor.record_phase(
        "retrieval.rows.semantic",
        10.0,
        mode="semantic",
        collection="knowledge_chunks",
        fetch_limit=4,
        rows_fetched=6,
        rows_parsed=6,
        rows_returned=4,
        rows_capped=2,
    )
    monitor.record_phase(
        "retrieval.rows.query",
        1.0,
        mode="semantic",
        collection="knowledge_chunks",
        fetch_limit=4,
        rows_input=4,
        rows_returned=4,
        rows_capped=0,
    )

    report = monitor.build_report()
    payload = report.to_dict()
    row_budget = payload["retrieval_signals"]["row_budget"]
    assert row_budget["count"] == 2
    assert row_budget["query_count"] == 1
    assert row_budget["backend_count"] == 1
    assert row_budget["rows_fetched_sum"] == 6
    assert row_budget["rows_parsed_sum"] == 6
    assert row_budget["rows_input_sum"] == 4
    assert row_budget["rows_returned_sum"] == 4
    assert row_budget["rows_capped_sum"] == 0
    assert row_budget["rows_parse_dropped_sum"] == 0
    assert row_budget["memory"]["observed_count"] == 0
    assert row_budget["memory"]["rss_delta_sum"] is None
    assert row_budget["memory"]["rss_peak_delta_sum"] is None
    assert row_budget["memory"]["rss_delta_max"] is None
    assert row_budget["memory"]["rss_peak_delta_max"] is None
    assert row_budget["latest"]["phase"] == "retrieval.rows.query"


def test_build_report_includes_machine_readable_link_graph_signals() -> None:
    """Report JSON should include aggregated link_graph_signals payload."""
    monitor = SkillsMonitor("knowledge.recall")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monitor.record_phase(
        "link_graph.policy.search",
        353.0,
        backend="wendao",
        timed_out=True,
        timeout_s=0.35,
        timeout_bucket="machine_like",
    )
    monitor.record_phase(
        "link_graph.proximity.fetch",
        0.0,
        skipped=True,
        reason="recent_graph_search_timeout",
    )

    report = monitor.build_report()
    payload = report.to_dict()
    signals = payload["link_graph_signals"]
    assert isinstance(signals, dict)
    assert signals["policy_search"]["count"] == 1
    assert signals["policy_search"]["timeouts"] == 1
    assert signals["policy_search"]["buckets"]["machine_like"] == 1
    assert signals["policy_search"]["latest"]["timeout_bucket"] == "machine_like"
    assert signals["proximity_fetch"]["count"] == 1
    assert signals["proximity_fetch"]["skipped"] == 1
    assert signals["proximity_fetch"]["reasons"]["recent_graph_search_timeout"] == 1


def test_build_report_includes_machine_readable_graph_stats_signals() -> None:
    """Report JSON should include aggregated graph-stats signal payload."""
    monitor = SkillsMonitor("knowledge.search")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monitor.record_phase(
        "skill_command.execute",
        38.0,
        tool="search.search",
        graph_stats_source="cache",
        graph_stats_cache_hit=True,
        graph_stats_fresh=True,
        graph_stats_age_ms=12,
        graph_stats_refresh_scheduled=False,
        graph_stats_total_notes=337,
    )

    report = monitor.build_report()
    payload = report.to_dict()
    signals = payload["link_graph_signals"]
    assert isinstance(signals, dict)
    assert signals["graph_stats"]["count"] == 1
    assert signals["graph_stats"]["sources"]["cache"] == 1
    assert signals["graph_stats"]["cache_hit_true"] == 1
    assert signals["graph_stats"]["fresh_true"] == 1
    assert signals["graph_stats"]["latest"]["total_notes"] == 337


def test_build_report_includes_machine_readable_link_graph_index_refresh_signals() -> None:
    """Report JSON should include aggregated LinkGraph index refresh signals."""
    monitor = SkillsMonitor("knowledge.recall")
    monitor.samples = [Sample(elapsed_s=0.0, rss_mb=100.0, rss_peak_mb=120.0, cpu_percent=None)]

    monitor.record_phase(
        "link_graph.index.delta.plan",
        2.0,
        strategy="delta",
        reason="delta_requested",
        changed_count=1,
        force_full=False,
        threshold=256,
    )
    monitor.record_phase(
        "link_graph.index.delta.apply",
        8.0,
        success=True,
        changed_count=1,
    )
    monitor.record_phase(
        "link_graph.index.delta.plan",
        1.0,
        strategy="full",
        reason="threshold_exceeded",
        changed_count=300,
        force_full=False,
        threshold=256,
    )
    monitor.record_phase(
        "link_graph.index.rebuild.full",
        55.0,
        success=True,
        reason="threshold_exceeded",
        changed_count=300,
    )

    report = monitor.build_report()
    payload = report.to_dict()
    signals = payload["link_graph_signals"]
    assert isinstance(signals, dict)
    index = signals["index_refresh"]
    assert index["observed"]["total"] == 4
    assert index["plan"]["count"] == 2
    assert index["plan"]["strategies"]["delta"] == 1
    assert index["plan"]["strategies"]["full"] == 1
    assert index["delta_apply"]["success"] == 1
    assert index["delta_apply"]["failed"] == 0
    assert index["full_rebuild"]["count"] == 1
    assert index["full_rebuild"]["success"] == 1
    assert index["full_rebuild"]["reasons"]["threshold_exceeded"] == 1


def test_summary_reporter_emits_dashboard_sections() -> None:
    """Summary reporter should emit dashboard sections with peak RSS details."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.recall",
            "elapsed_sec": 1.23,
            "rss_mb": {"start": 100.0, "end": 120.0, "delta": 20.0},
            "rss_peak_mb": {"start": 110.0, "end": 150.0, "delta": 40.0},
            "cpu_avg_percent": 0.2,
            "phases": [
                {
                    "phase": "runner.fast.load",
                    "duration_ms": 500.0,
                    "timestamp_s": 0.5,
                    "rss_delta_mb": 15.0,
                    "rss_peak_delta_mb": 20.0,
                    "tool": "knowledge.recall",
                },
                {
                    "phase": "vector.embed.mcp",
                    "duration_ms": 220.0,
                    "timestamp_s": 0.8,
                    "success": True,
                    "port": 3002,
                    "path": "/messages/",
                    "attempts": 1,
                    "cached_target_hit": True,
                },
            ],
            "rust_db_events": [
                {"op": "search_optimized", "duration_ms": 120.0, "collection": "knowledge_chunks"}
            ],
            "samples_count": 3,
        }
    )

    output = stream.getvalue()
    assert "skills-monitor dashboard" in output
    assert "RSS(peak):" in output
    assert "Bottlenecks:" in output
    assert "Phases (grouped):" in output
    assert "Top Events:" in output
    assert "Rust/DB events:" in output
    assert "port=3002" in output
    assert "cached_target_hit=True" in output


def test_summary_reporter_emits_retrieval_signals() -> None:
    """Summary reporter should print dedicated retrieval row-budget block."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.recall",
            "elapsed_sec": 0.33,
            "rss_mb": {"start": 100.0, "end": 112.0, "delta": 12.0},
            "rss_peak_mb": {"start": 100.0, "end": 113.0, "delta": 13.0},
            "cpu_avg_percent": 0.1,
            "phases": [
                {
                    "phase": "retrieval.rows.semantic",
                    "duration_ms": 19.0,
                    "timestamp_s": 0.1,
                    "mode": "semantic",
                    "fetch_limit": 4,
                    "rows_fetched": 6,
                    "rows_parsed": 6,
                    "rows_returned": 4,
                    "rows_capped": 2,
                    "rss_delta_mb": 3.0,
                    "rss_peak_delta_mb": 4.0,
                },
                {
                    "phase": "retrieval.rows.query",
                    "duration_ms": 20.0,
                    "timestamp_s": 0.2,
                    "mode": "semantic",
                    "fetch_limit": 4,
                    "rows_input": 4,
                    "rows_returned": 4,
                    "rows_capped": 0,
                    "rss_delta_mb": 0.1,
                    "rss_peak_delta_mb": 0.2,
                },
            ],
            "retrieval_signals": {
                "row_budget": {
                    "count": 2,
                    "query_count": 1,
                    "backend_count": 1,
                    "rows_fetched_sum": 6,
                    "rows_parsed_sum": 6,
                    "rows_input_sum": 4,
                    "rows_returned_sum": 4,
                    "rows_capped_sum": 2,
                    "rows_parse_dropped_sum": 0,
                    "memory": {
                        "observed_count": 2,
                        "rss_delta_sum": 3.1,
                        "rss_peak_delta_sum": 4.2,
                        "rss_delta_max": 3.0,
                        "rss_peak_delta_max": 4.0,
                    },
                    "modes": {"semantic": {"count": 1, "rows_returned": 4, "rows_capped": 0}},
                    "latest": {
                        "phase": "retrieval.rows.query",
                        "mode": "semantic",
                        "fetch_limit": 4,
                        "rows_fetched": None,
                        "rows_parsed": None,
                        "rows_input": 4,
                        "rows_returned": 4,
                        "rows_capped": 0,
                        "rows_parse_dropped": None,
                    },
                }
            },
            "link_graph_signals": None,
            "rust_db_events": [],
            "samples_count": 1,
        }
    )

    output = stream.getvalue()
    assert "Retrieval Signals:" in output
    assert (
        "row_budget: count=2 query=1 backend=1 fetched=6 parsed=6 input=4 "
        "returned=4 capped=2 parse_dropped=0"
    ) in output
    assert "row_budget.modes: semantic=1" in output
    assert "row_budget.latest: phase=retrieval.rows.query mode=semantic limit=4" in output
    assert "row_budget.memory: observed=2" in output


def test_summary_reporter_skips_retrieval_signals_without_payload() -> None:
    """Summary reporter should not derive retrieval block from phases when payload is missing."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.recall",
            "elapsed_sec": 0.21,
            "rss_mb": {"start": 100.0, "end": 109.0, "delta": 9.0},
            "rss_peak_mb": {"start": 100.0, "end": 110.0, "delta": 10.0},
            "cpu_avg_percent": 0.0,
            "phases": [
                {
                    "phase": "retrieval.rows.graph",
                    "duration_ms": 12.0,
                    "timestamp_s": 0.1,
                    "mode": "graph",
                    "fetch_limit": 2,
                    "rows_fetched": 3,
                    "rows_parsed": 3,
                    "rows_returned": 2,
                    "rows_capped": 1,
                }
            ],
            "rust_db_events": [],
            "samples_count": 1,
        }
    )

    output = stream.getvalue()
    assert "Retrieval Signals:" not in output


def test_summary_reporter_emits_link_graph_index_signals() -> None:
    """Summary reporter should print dedicated LinkGraph index signal block."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.recall",
            "elapsed_sec": 0.44,
            "rss_mb": {"start": 100.0, "end": 108.0, "delta": 8.0},
            "rss_peak_mb": {"start": 100.0, "end": 109.0, "delta": 9.0},
            "cpu_avg_percent": 0.1,
            "phases": [
                {
                    "phase": "link_graph.index.delta.plan",
                    "duration_ms": 2.0,
                    "timestamp_s": 0.1,
                    "strategy": "delta",
                    "reason": "delta_requested",
                    "changed_count": 2,
                    "threshold": 256,
                    "force_full": False,
                },
                {
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": 9.0,
                    "timestamp_s": 0.2,
                    "success": True,
                    "changed_count": 2,
                },
                {
                    "phase": "link_graph.index.rebuild.full",
                    "duration_ms": 64.0,
                    "timestamp_s": 0.3,
                    "success": True,
                    "reason": "delta_failed_fallback",
                    "changed_count": 2,
                },
            ],
            "link_graph_signals": {
                "index_refresh": {
                    "observed": {
                        "total": 3,
                        "plan": 1,
                        "delta_apply": 1,
                        "full_rebuild": 1,
                    },
                    "plan": {
                        "count": 1,
                        "strategies": {"delta": 1},
                        "reasons": {"delta_requested": 1},
                        "force_full_true": 0,
                        "latest": {
                            "strategy": "delta",
                            "reason": "delta_requested",
                            "changed_count": 2,
                            "threshold": 256,
                            "force_full": False,
                        },
                    },
                    "delta_apply": {
                        "count": 1,
                        "success": 1,
                        "failed": 0,
                        "latest": {"success": True, "changed_count": 2},
                    },
                    "full_rebuild": {
                        "count": 1,
                        "success": 1,
                        "failed": 0,
                        "reasons": {"delta_failed_fallback": 1},
                        "latest": {
                            "success": True,
                            "reason": "delta_failed_fallback",
                            "changed_count": 2,
                        },
                    },
                }
            },
            "rust_db_events": [],
            "samples_count": 1,
        }
    )

    output = stream.getvalue()
    assert "LinkGraph Index Signals:" in output
    assert "observed: total=3 plan=1 delta_apply=1 full_rebuild=1" in output
    assert "plan.strategies: delta=1" in output
    assert "delta.apply: count=1 success=1 failed=0" in output
    assert "full.reasons: delta_failed_fallback=1" in output


def test_summary_reporter_emits_link_graph_timeout_signals() -> None:
    """Summary reporter should show LinkGraph timeout bucket and proximity skip signals."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.recall",
            "elapsed_sec": 0.62,
            "rss_mb": {"start": 100.0, "end": 120.0, "delta": 20.0},
            "rss_peak_mb": {"start": 100.0, "end": 122.0, "delta": 22.0},
            "cpu_avg_percent": 0.1,
            "phases": [
                {
                    "phase": "link_graph.policy.search",
                    "duration_ms": 353.0,
                    "timestamp_s": 0.35,
                    "backend": "wendao",
                    "timed_out": True,
                    "timeout_s": 0.35,
                    "timeout_bucket": "machine_like",
                },
                {
                    "phase": "link_graph.proximity.fetch",
                    "duration_ms": 0.0,
                    "timestamp_s": 0.36,
                    "skipped": True,
                    "reason": "recent_graph_search_timeout",
                },
            ],
            "link_graph_signals": {
                "policy_search": {
                    "count": 1,
                    "timeouts": 1,
                    "buckets": {"machine_like": 1},
                    "latest": {
                        "timeout_s": 0.35,
                        "timeout_bucket": "machine_like",
                        "backend": "wendao",
                        "timed_out": True,
                    },
                },
                "proximity_fetch": {
                    "count": 1,
                    "skipped": 1,
                    "timed_out": 0,
                    "reasons": {"recent_graph_search_timeout": 1},
                },
            },
            "rust_db_events": [],
            "samples_count": 2,
        }
    )

    output = stream.getvalue()
    assert "LinkGraph Signals:" in output
    assert "policy.buckets: machine_like=1" in output
    assert "policy.latest: timeout=0.350s bucket=machine_like" in output
    assert "proximity.reasons: recent_graph_search_timeout=1" in output
    assert "timeout_bucket=machine_like" in output


def test_summary_reporter_emits_graph_stats_signals() -> None:
    """Summary reporter should include graph_stats meta observability block."""
    stream = io.StringIO()
    reporter = SummaryReporter(stream=stream)

    reporter.emit(
        {
            "skill_command": "knowledge.search",
            "elapsed_sec": 0.31,
            "rss_mb": {"start": 100.0, "end": 108.0, "delta": 8.0},
            "rss_peak_mb": {"start": 100.0, "end": 110.0, "delta": 10.0},
            "cpu_avg_percent": 0.1,
            "phases": [
                {
                    "phase": "skill_command.execute",
                    "duration_ms": 34.0,
                    "timestamp_s": 0.2,
                    "tool": "search.search",
                    "graph_stats_source": "probe",
                    "graph_stats_cache_hit": False,
                    "graph_stats_fresh": True,
                    "graph_stats_age_ms": 0,
                    "graph_stats_refresh_scheduled": False,
                    "graph_stats_total_notes": 337,
                }
            ],
            "link_graph_signals": {
                "graph_stats": {
                    "count": 1,
                    "sources": {"probe": 1},
                    "cache_hit_true": 0,
                    "fresh_true": 1,
                    "refresh_scheduled": 0,
                    "age_ms": {"avg": 0.0, "max": 0},
                    "latest": {
                        "source": "probe",
                        "cache_hit": False,
                        "fresh": True,
                        "age_ms": 0,
                        "refresh_scheduled": False,
                        "total_notes": 337,
                    },
                }
            },
            "rust_db_events": [],
            "samples_count": 1,
        }
    )

    output = stream.getvalue()
    assert "Graph Stats Signals:" in output
    assert "sources: probe=1" in output
    assert "cache_hit: true=0 false=1" in output
    assert "latest: source=probe cache_hit=False fresh=True age_ms=0" in output


def test_record_phase_suppresses_nested_skill_command_events() -> None:
    """Suppression context should drop only skill_command.execute, not other phases."""
    monitor = SkillsMonitor("knowledge.recall")
    token = set_current_monitor(monitor)
    try:
        with suppress_skill_command_phase_events():
            record_phase("skill_command.execute", 10.0, tool="search.recall")
            record_phase("vector.search", 5.0, collection="knowledge_chunks")
    finally:
        reset_current_monitor(token)

    phase_names = [p.phase for p in monitor.phases]
    assert "skill_command.execute" not in phase_names
    assert "vector.search" in phase_names


def test_record_phase_verbose_emits_key_details(capsys) -> None:
    """Verbose phase line should include important extra fields for quick diagnosis."""
    monitor = SkillsMonitor("knowledge.recall", verbose=True)

    monitor.record_phase(
        "vector.embed.mcp",
        18.0,
        success=True,
        port=3002,
        path="/messages/",
        attempts=1,
        cached_target_hit=True,
    )

    captured = capsys.readouterr()
    assert "[monitor] phase=vector.embed.mcp duration_ms=18" in captured.err
    assert "port=3002" in captured.err
    assert "path=/messages/" in captured.err
    assert "attempts=1" in captured.err
    assert "cached_target_hit=True" in captured.err


@pytest.mark.asyncio
async def test_skills_monitor_scope_supports_deferred_report(monkeypatch) -> None:
    """auto_report=False should skip report emission at scope exit."""
    emitted: list[bool] = []

    monkeypatch.setattr(SkillsMonitor, "start_sampler", lambda self: None)
    monkeypatch.setattr(SkillsMonitor, "stop_sampler", lambda self: None)

    def _fake_report(self, output_json: bool = False) -> None:
        emitted.append(output_json)

    monkeypatch.setattr(SkillsMonitor, "report", _fake_report)

    async with skills_monitor_scope("knowledge.recall", auto_report=False):
        pass

    assert emitted == []
