from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from omni.foundation.runtime.gitops import get_project_root


def _load_module():
    module_path = (
        Path(get_project_root()) / "scripts" / "channel" / "test_omni_agent_memory_slo_report.py"
    )
    spec = importlib.util.spec_from_file_location("channel_memory_slo_report", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "project_root": str(tmp_path),
        "evolution_report_json": ".run/reports/omni-agent-memory-evolution.json",
        "benchmark_report_json": ".run/reports/omni-agent-memory-benchmark.json",
        "session_matrix_report_json": ".run/reports/agent-channel-session-matrix.json",
        "runtime_log_file": ".run/logs/omni-agent-webhook.log",
        "output_json": ".run/reports/omni-agent-memory-slo-report.json",
        "output_markdown": ".run/reports/omni-agent-memory-slo-report.md",
        "min_planned_hits": 10,
        "min_successful_corrections": 3,
        "min_recall_credit_events": 1,
        "min_quality_score": 90.0,
        "required_benchmark_modes": "baseline,adaptive",
        "min_query_turns": 1,
        "max_mode_mcp_error_turns": 0,
        "max_total_mcp_error_turns": 0,
        "min_session_steps": 1,
        "max_session_failed_steps": 0,
        "enable_stream_gate": True,
        "min_stream_ack_ratio": 0.95,
        "min_stream_published_events": 1,
        "max_stream_read_failed": 0,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _seed_reports(tmp_path: Path, *, benchmark_mcp_errors: int = 0) -> None:
    evolution_report = {
        "overall_passed": True,
        "scenarios": [
            {
                "scenario_id": "memory_self_correction_high_complexity_dag",
                "quality_passed": True,
                "quality": {
                    "planned_hits": 12,
                    "successful_corrections": 4,
                    "recall_credit_events": 2,
                    "quality_score": 94.2,
                },
            }
        ],
    }
    benchmark_report = {
        "mode_summaries": {
            "baseline": {"query_turns": 8, "mcp_error_turns": benchmark_mcp_errors},
            "adaptive": {"query_turns": 8, "mcp_error_turns": benchmark_mcp_errors},
        }
    }
    session_matrix_report = {
        "overall_passed": True,
        "summary": {"total": 9, "failed": 0},
    }
    _write_json(tmp_path / ".run/reports/omni-agent-memory-evolution.json", evolution_report)
    _write_json(tmp_path / ".run/reports/omni-agent-memory-benchmark.json", benchmark_report)
    _write_json(tmp_path / ".run/reports/agent-channel-session-matrix.json", session_matrix_report)


def test_memory_slo_report_passes_when_all_gates_pass(tmp_path: Path) -> None:
    module = _load_module()
    _seed_reports(tmp_path)
    runtime_log = tmp_path / ".run/logs/omni-agent-webhook.log"
    runtime_log.parent.mkdir(parents=True, exist_ok=True)
    runtime_log.write_text(
        "\n".join(
            [
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="agent.memory.stream_consumer.event_processed"',
                'DEBUG event="agent.memory.stream_consumer.event_processed"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cfg = module.build_config(_build_args(tmp_path))
    report = module.run_slo_report(cfg)

    assert report["overall_passed"] is True
    assert report["failure_count"] == 0
    assert report["checks"]["stream"]["summary"]["ack_ratio"] == 1.0


def test_memory_slo_report_fails_when_benchmark_mcp_errors_present(tmp_path: Path) -> None:
    module = _load_module()
    _seed_reports(tmp_path, benchmark_mcp_errors=1)
    runtime_log = tmp_path / ".run/logs/omni-agent-webhook.log"
    runtime_log.parent.mkdir(parents=True, exist_ok=True)
    runtime_log.write_text(
        "\n".join(
            [
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="agent.memory.stream_consumer.event_processed"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cfg = module.build_config(_build_args(tmp_path))
    report = module.run_slo_report(cfg)

    assert report["overall_passed"] is False
    failures = report["failures"]
    assert any("benchmark.baseline.mcp_error_turns=1 > 0" in item for item in failures)


def test_memory_slo_report_fails_on_low_stream_ack_ratio(tmp_path: Path) -> None:
    module = _load_module()
    _seed_reports(tmp_path)
    runtime_log = tmp_path / ".run/logs/omni-agent-webhook.log"
    runtime_log.parent.mkdir(parents=True, exist_ok=True)
    runtime_log.write_text(
        "\n".join(
            [
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="session.stream_event.published"',
                'DEBUG event="agent.memory.stream_consumer.event_processed"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cfg = module.build_config(_build_args(tmp_path, min_stream_ack_ratio=0.8))
    report = module.run_slo_report(cfg)

    assert report["overall_passed"] is False
    failures = report["failures"]
    assert any("stream.ack_ratio=0.3333 < 0.8000" in item for item in failures)
