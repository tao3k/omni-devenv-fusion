from __future__ import annotations

import importlib.util
from pathlib import Path

from omni.foundation.runtime.gitops import get_project_root


def _load_module():
    module_path = (
        Path(get_project_root()) / "scripts" / "channel" / "reconstruct_omni_agent_trace.py"
    )
    spec = importlib.util.spec_from_file_location("reconstruct_omni_agent_trace", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_trace_entries_filters_and_extracts_chain(tmp_path: Path) -> None:
    mod = _load_module()
    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "\n".join(
            [
                (
                    "2026-02-20T01:11:00Z INFO omni_agent::agent::mod: "
                    'event="session.route.decision_selected" session_id="telegram:1:2" '
                    "route=graph confidence=0.91"
                ),
                (
                    "2026-02-20T01:11:01Z INFO omni_agent::agent::mod: "
                    'event="session.injection.snapshot_created" session_id="telegram:1:2" '
                    "snapshot_id=snap-1"
                ),
                (
                    "2026-02-20T01:11:02Z INFO omni_agent::agent::reflection: "
                    'event="agent.reflection.policy_hint.stored" session_id="telegram:1:2"'
                ),
                (
                    "2026-02-20T01:11:03Z INFO omni_agent::agent::persistence: "
                    'event="agent.memory.gate.evaluated" session_id="telegram:1:2" verdict=retain'
                ),
                (
                    "2026-02-20T01:11:04Z INFO omni_agent::channels::telegram::runtime::webhook: "
                    'event="session.route.decision_selected" session_id="telegram:9:9" route=react'
                ),
            ]
        ),
        encoding="utf-8",
    )
    entries = mod.load_trace_entries(log_file, session_id="telegram:1:2")
    assert len(entries) == 4
    assert entries[0]["event"] == "session.route.decision_selected"
    assert entries[1]["event"] == "session.injection.snapshot_created"
    assert entries[2]["event"] == "agent.reflection.policy_hint.stored"
    assert entries[3]["event"] == "agent.memory.gate.evaluated"


def test_build_trace_summary_marks_stage_flags(tmp_path: Path) -> None:
    mod = _load_module()
    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "\n".join(
            [
                '2026-02-20T01:11:00Z INFO x: event="telegram.dedup.update_accepted"',
                '2026-02-20T01:11:01Z INFO x: event="session.route.decision_selected"',
                '2026-02-20T01:11:02Z INFO x: event="session.injection.snapshot_created"',
                '2026-02-20T01:11:03Z INFO x: event="agent.reflection.lifecycle.transition"',
                '2026-02-20T01:11:04Z INFO x: event="agent.memory.recall.planned"',
                '2026-02-20T01:11:05Z INFO x: event="agent.memory.recall.injected"',
                '2026-02-20T01:11:06Z INFO x: event="suggested_link" reason="alias bridge"',
            ]
        ),
        encoding="utf-8",
    )
    entries = mod.load_trace_entries(log_file)
    summary = mod.build_trace_summary(entries)
    flags = summary["stage_flags"]
    assert flags["has_dedup"] is True
    assert flags["has_route"] is True
    assert flags["has_injection"] is True
    assert flags["has_reflection"] is True
    assert flags["has_memory"] is True
    assert flags["has_suggested_link"] is True
    assert summary["quality_score"] == 100.0


def test_evaluate_trace_health_reports_missing_suggested_link(tmp_path: Path) -> None:
    mod = _load_module()
    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "\n".join(
            [
                '2026-02-20T01:11:00Z INFO x: event="session.route.decision_selected"',
                '2026-02-20T01:11:01Z INFO x: event="session.injection.snapshot_created"',
                '2026-02-20T01:11:02Z INFO x: event="agent.reflection.lifecycle.transition"',
                '2026-02-20T01:11:03Z INFO x: event="agent.memory.gate.evaluated"',
            ]
        ),
        encoding="utf-8",
    )
    entries = mod.load_trace_entries(log_file)
    summary = mod.build_trace_summary(entries)
    errors = mod.evaluate_trace_health(summary, require_suggested_link=True)
    assert "missing suggested_link evidence" in errors


def test_evaluate_trace_health_respects_required_stage_subset() -> None:
    mod = _load_module()
    summary = {
        "stage_flags": {
            "has_dedup": True,
            "has_route": False,
            "has_injection": False,
            "has_reflection": False,
            "has_memory": True,
            "has_suggested_link": False,
        }
    }
    errors = mod.evaluate_trace_health(summary, required_stages=("memory",))
    assert errors == []
