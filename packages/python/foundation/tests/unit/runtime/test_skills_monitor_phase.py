"""Unit tests for skills monitor phase instrumentation helpers."""

from __future__ import annotations

from omni.foundation.runtime.skills_monitor import phase as phase_runtime


def test_build_memory_delta_fields_returns_expected_values() -> None:
    payload = phase_runtime.build_memory_delta_fields(
        rss_before=100.0,
        rss_peak_before=120.0,
        rss_after=108.75,
        rss_peak_after=128.25,
    )

    assert payload == {
        "rss_before_mb": 100.0,
        "rss_after_mb": 108.75,
        "rss_delta_mb": 8.75,
        "rss_peak_before_mb": 120.0,
        "rss_peak_after_mb": 128.25,
        "rss_peak_delta_mb": 8.25,
    }


def test_record_phase_with_memory_emits_duration_and_memory(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    monkeypatch.setattr(phase_runtime, "sample_memory", lambda: (113.0, 135.0))
    monkeypatch.setattr(phase_runtime.time, "perf_counter", lambda: 12.5)

    def _capture(phase: str, duration_ms: float, **extra: object) -> None:
        recorded["phase"] = phase
        recorded["duration_ms"] = duration_ms
        recorded["extra"] = dict(extra)

    monkeypatch.setattr(phase_runtime, "_record_phase", _capture)

    phase_runtime.record_phase_with_memory(
        "retrieval.rows.semantic",
        started_at=10.0,
        rss_before=100.0,
        rss_peak_before=130.0,
        mode="semantic",
        collection="knowledge_chunks",
    )

    assert recorded["phase"] == "retrieval.rows.semantic"
    assert recorded["duration_ms"] == 2500.0
    extra = recorded["extra"]
    assert isinstance(extra, dict)
    assert extra["mode"] == "semantic"
    assert extra["collection"] == "knowledge_chunks"
    assert extra["rss_before_mb"] == 100.0
    assert extra["rss_after_mb"] == 113.0
    assert extra["rss_delta_mb"] == 13.0
    assert extra["rss_peak_before_mb"] == 130.0
    assert extra["rss_peak_after_mb"] == 135.0
    assert extra["rss_peak_delta_mb"] == 5.0


def test_phase_scope_emits_payload_with_memory(monkeypatch) -> None:
    recorded: dict[str, object] = {}
    times = iter([1.0, 1.25])
    memories = iter([(100.0, 120.0), (104.0, 126.0)])

    monkeypatch.setattr(phase_runtime.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(phase_runtime, "sample_memory", lambda: next(memories))

    def _capture(phase: str, duration_ms: float, **extra: object) -> None:
        recorded["phase"] = phase
        recorded["duration_ms"] = duration_ms
        recorded["extra"] = dict(extra)

    monkeypatch.setattr(phase_runtime, "_record_phase", _capture)

    with phase_runtime.phase_scope("retrieval.rows.query", {"mode": "semantic"}) as payload:
        payload["rows_input"] = 4
        payload["rows_returned"] = 4

    assert recorded["phase"] == "retrieval.rows.query"
    assert recorded["duration_ms"] == 250.0
    extra = recorded["extra"]
    assert isinstance(extra, dict)
    assert extra["mode"] == "semantic"
    assert extra["rows_input"] == 4
    assert extra["rows_returned"] == 4
    assert extra["rss_delta_mb"] == 4.0
    assert extra["rss_peak_delta_mb"] == 6.0
