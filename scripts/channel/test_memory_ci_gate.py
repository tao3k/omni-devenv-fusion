#!/usr/bin/env python3

from __future__ import annotations

import json
import socket
import sys
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from test_omni_agent_memory_ci_gate import (
    GateConfig,
    assert_cross_group_complex_quality,
    assert_evolution_slow_response_quality,
    assert_mcp_waiting_warning_budget,
    assert_session_matrix_quality,
    assert_trace_reconstruction_quality,
    can_bind_tcp,
    parse_args,
    resolve_runtime_ports,
)

if TYPE_CHECKING:
    from pathlib import Path


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_cfg(tmp_path: Path) -> GateConfig:
    return GateConfig(
        profile="nightly",
        project_root=tmp_path,
        script_dir=tmp_path,
        agent_bin=None,
        webhook_port=18081,
        telegram_api_port=18080,
        valkey_port=6379,
        valkey_url="redis://127.0.0.1:6379/0",
        valkey_prefix="omni-agent:session:ci:test",
        username="ci-user",
        webhook_secret="test-webhook-secret",
        chat_id=1001,
        chat_b=1002,
        chat_c=1003,
        user_id=2001,
        user_b=2002,
        user_c=2003,
        runtime_log_file=tmp_path / "runtime.log",
        mock_log_file=tmp_path / "mock.log",
        runtime_startup_timeout_secs=90,
        quick_max_wait=45,
        quick_max_idle=25,
        full_max_wait=90,
        full_max_idle=40,
        matrix_max_wait=45,
        matrix_max_idle=30,
        benchmark_iterations=3,
        skip_matrix=False,
        skip_benchmark=False,
        skip_evolution=False,
        skip_rust_regressions=False,
        skip_discover_cache_gate=False,
        skip_reflection_quality_gate=False,
        skip_trace_reconstruction_gate=False,
        skip_cross_group_complex_gate=False,
        evolution_report_json=tmp_path / "evolution.json",
        benchmark_report_json=tmp_path / "benchmark.json",
        session_matrix_report_json=tmp_path / "session-matrix.json",
        session_matrix_report_markdown=tmp_path / "session-matrix.md",
        trace_report_json=tmp_path / "trace-reconstruction.json",
        trace_report_markdown=tmp_path / "trace-reconstruction.md",
        cross_group_report_json=tmp_path / "cross-group-complex.json",
        cross_group_report_markdown=tmp_path / "cross-group-complex.md",
        cross_group_dataset=tmp_path / "complex-dataset.json",
        cross_group_scenario_id="cross_group_control_plane_stress",
        min_planned_hits=10,
        min_successful_corrections=3,
        min_recall_credit_events=1,
        min_quality_score=90.0,
        slow_response_min_duration_ms=20000,
        slow_response_long_step_ms=1200,
        slow_response_min_long_steps=1,
        trace_min_quality_score=90.0,
        trace_max_events=2000,
        min_session_steps=20,
        require_cross_group_step=True,
        require_mixed_batch_steps=True,
        cross_group_max_wait=90,
        cross_group_max_idle=80,
        cross_group_max_parallel=3,
        discover_cache_hit_p95_ms=15.0,
        discover_cache_miss_p95_ms=80.0,
        discover_cache_bench_iterations=12,
        max_mcp_call_waiting_events=0,
        max_mcp_connect_waiting_events=0,
        max_mcp_waiting_events_total=0,
    )


def write_report(cfg: GateConfig, payload: dict[str, object]) -> None:
    cfg.session_matrix_report_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.session_matrix_report_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def passing_report(cfg: GateConfig) -> dict[str, object]:
    steps = [{"name": f"step-{index}", "passed": True} for index in range(1, 18)]
    steps.extend(
        [
            {"name": "concurrent_cross_group", "passed": True},
            {"name": "mixed_reset_session_a", "passed": True},
            {"name": "mixed_resume_status_session_b", "passed": True},
            {"name": "mixed_plain_session_c", "passed": True},
        ]
    )
    return {
        "overall_passed": True,
        "summary": {"total": len(steps), "failed": 0},
        "config": {
            "chat_id": cfg.chat_id,
            "chat_b": cfg.chat_b,
            "chat_c": cfg.chat_c,
        },
        "steps": steps,
    }


def test_assert_session_matrix_quality_accepts_full_matrix(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    write_report(cfg, passing_report(cfg))
    assert_session_matrix_quality(cfg)


def test_assert_session_matrix_quality_rejects_missing_cross_group(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    report = passing_report(cfg)
    report["steps"] = [step for step in report["steps"] if step["name"] != "concurrent_cross_group"]
    report["summary"] = {"total": len(report["steps"]), "failed": 0}
    write_report(cfg, report)
    with pytest.raises(RuntimeError, match="concurrent_cross_group"):
        assert_session_matrix_quality(cfg)


def test_assert_session_matrix_quality_accepts_chat_partition_baseline_cross_chat(
    tmp_path: Path,
) -> None:
    cfg = build_cfg(tmp_path)
    steps = [{"name": f"step-{index}", "passed": True} for index in range(1, 16)]
    steps.extend(
        [
            {"name": "concurrent_baseline_cross_chat", "passed": True},
            {"name": "mixed_reset_session_a", "passed": True},
            {"name": "mixed_resume_status_session_b", "passed": True},
            {"name": "mixed_plain_session_c", "passed": True},
        ]
    )
    write_report(
        cfg,
        {
            "overall_passed": True,
            "summary": {"total": len(steps), "failed": 0},
            "config": {
                "chat_id": cfg.chat_id,
                "chat_b": cfg.chat_b,
                "chat_c": cfg.chat_c,
            },
            "steps": steps,
        },
    )
    assert len(steps) == 19
    assert_session_matrix_quality(cfg)


def test_assert_trace_reconstruction_quality_accepts_valid_report(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.trace_report_json.write_text(
        json.dumps(
            {
                "summary": {
                    "events_total": 8,
                    "quality_score": 100.0,
                    "stage_flags": {
                        "has_route": True,
                        "has_injection": True,
                        "has_reflection": True,
                        "has_memory": True,
                    },
                },
                "errors": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert_trace_reconstruction_quality(cfg)


def test_assert_trace_reconstruction_quality_rejects_low_quality(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.trace_report_json.write_text(
        json.dumps(
            {
                "summary": {
                    "events_total": 4,
                    "quality_score": 75.0,
                    "stage_flags": {
                        "has_route": True,
                        "has_injection": True,
                        "has_reflection": True,
                        "has_memory": False,
                    },
                },
                "errors": ["missing memory lifecycle events"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="trace reconstruction quality gates failed"):
        assert_trace_reconstruction_quality(cfg)


def test_assert_evolution_slow_response_quality_accepts_long_horizon_report(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.evolution_report_json.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "scenarios": [
                    {
                        "scenario_id": "memory_self_correction_high_complexity_dag",
                        "duration_ms": 32000,
                        "steps": [
                            {"step_id": "a", "duration_ms": 1600},
                            {"step_id": "b", "duration_ms": 900},
                            {"step_id": "c", "duration_ms": 1700},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert_evolution_slow_response_quality(cfg)


def test_assert_evolution_slow_response_quality_rejects_short_report(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.evolution_report_json.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "scenarios": [
                    {
                        "scenario_id": "memory_self_correction_high_complexity_dag",
                        "duration_ms": 8000,
                        "steps": [{"step_id": "a", "duration_ms": 500}],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="slow-response resilience gate failed"):
        assert_evolution_slow_response_quality(cfg)


def test_assert_cross_group_complex_quality_accepts_parallel_isolation_report(
    tmp_path: Path,
) -> None:
    cfg = build_cfg(tmp_path)
    cfg.cross_group_report_json.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "scenarios": [
                    {
                        "scenario_id": "cross_group_control_plane_stress",
                        "passed": True,
                        "steps": [
                            {
                                "step_id": "a0",
                                "session_alias": "a",
                                "session_key": "telegram:1001:2001",
                                "wave_index": 0,
                                "mcp_waiting_seen": False,
                            },
                            {
                                "step_id": "b0",
                                "session_alias": "b",
                                "session_key": "telegram:1002:2002",
                                "wave_index": 0,
                                "mcp_waiting_seen": False,
                            },
                            {
                                "step_id": "c0",
                                "session_alias": "c",
                                "session_key": "telegram:1003:2003",
                                "wave_index": 1,
                                "mcp_waiting_seen": False,
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert_cross_group_complex_quality(cfg)


def test_assert_cross_group_complex_quality_rejects_missing_third_group(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.cross_group_report_json.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "scenarios": [
                    {
                        "scenario_id": "cross_group_control_plane_stress",
                        "passed": True,
                        "steps": [
                            {
                                "step_id": "a0",
                                "session_alias": "a",
                                "session_key": "telegram:1001:2001",
                                "wave_index": 0,
                                "mcp_waiting_seen": False,
                            },
                            {
                                "step_id": "b0",
                                "session_alias": "b",
                                "session_key": "telegram:1002:2002",
                                "wave_index": 0,
                                "mcp_waiting_seen": False,
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="missing session aliases"):
        assert_cross_group_complex_quality(cfg)


def test_assert_mcp_waiting_warning_budget_accepts_clean_runtime_log(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.runtime_log_file.write_text(
        "\n".join(
            [
                '2026-02-20T00:00:00Z INFO event="session.route.decision_selected"',
                '2026-02-20T00:00:01Z INFO event="agent.memory.recall.planned"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert_mcp_waiting_warning_budget(cfg)


def test_assert_mcp_waiting_warning_budget_rejects_over_budget(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg.runtime_log_file.write_text(
        "\n".join(
            [
                '2026-02-20T00:00:00Z WARN event="mcp.pool.call.waiting"',
                '2026-02-20T00:00:01Z WARN event="mcp.pool.connect.waiting"',
                '2026-02-20T00:00:02Z WARN event="mcp.pool.connect.waiting"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="mcp waiting warning budget exceeded"):
        assert_mcp_waiting_warning_budget(cfg)


def test_assert_mcp_waiting_warning_budget_allows_configured_budget(tmp_path: Path) -> None:
    cfg = build_cfg(tmp_path)
    cfg = replace(
        cfg,
        max_mcp_call_waiting_events=2,
        max_mcp_connect_waiting_events=3,
        max_mcp_waiting_events_total=5,
    )
    cfg.runtime_log_file.write_text(
        "\n".join(
            [
                '2026-02-20T00:00:00Z WARN event="mcp.pool.call.waiting"',
                '2026-02-20T00:00:01Z WARN event="mcp.pool.connect.waiting"',
                '2026-02-20T00:00:02Z WARN event="mcp.pool.connect.waiting"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert_mcp_waiting_warning_budget(cfg)


def test_resolve_runtime_ports_reassigns_when_requested_ports_are_occupied() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as first:
        first.bind(("127.0.0.1", 0))
        first.listen(1)
        first_port = int(first.getsockname()[1])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as second:
            second.bind(("127.0.0.1", 0))
            second.listen(1)
            second_port = int(second.getsockname()[1])

            webhook_port, telegram_api_port = resolve_runtime_ports(
                webhook_port=first_port,
                telegram_api_port=second_port,
            )

    assert webhook_port != first_port
    assert telegram_api_port != second_port
    assert webhook_port != telegram_api_port
    assert can_bind_tcp("127.0.0.1", webhook_port)
    assert can_bind_tcp("127.0.0.1", telegram_api_port)


def test_resolve_runtime_ports_reassigns_when_ports_conflict() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_holder:
        socket_holder.bind(("127.0.0.1", 0))
        socket_holder.listen(1)
        requested = int(socket_holder.getsockname()[1])

    # The requested port is now free, but using the same value for both inputs must still
    # produce two distinct bindable ports.
    webhook_port, telegram_api_port = resolve_runtime_ports(
        webhook_port=requested,
        telegram_api_port=requested,
    )

    assert webhook_port != telegram_api_port
    assert can_bind_tcp("127.0.0.1", webhook_port)
    assert can_bind_tcp("127.0.0.1", telegram_api_port)


def test_parse_args_uses_run_scoped_default_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    webhook_port = pick_free_port()
    telegram_port = pick_free_port()
    valkey_port = pick_free_port()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_memory_ci_gate.py",
            "--profile",
            "quick",
            "--webhook-port",
            str(webhook_port),
            "--telegram-api-port",
            str(telegram_port),
            "--valkey-port",
            str(valkey_port),
        ],
    )

    cfg = parse_args(tmp_path)

    assert cfg.runtime_log_file.parent == (tmp_path / ".run" / "logs")
    assert cfg.runtime_log_file.name.startswith("omni-agent-webhook-ci-quick-")
    assert cfg.runtime_log_file.suffix == ".log"
    assert cfg.mock_log_file.parent == (tmp_path / ".run" / "logs")
    assert cfg.mock_log_file.name.startswith("omni-agent-mock-telegram-quick-")
    assert cfg.mock_log_file.suffix == ".log"
    assert cfg.evolution_report_json.parent == (tmp_path / ".run" / "reports")
    assert cfg.evolution_report_json.name.startswith("omni-agent-memory-evolution-quick-")
    assert cfg.evolution_report_json.suffix == ".json"
    assert cfg.trace_report_markdown.parent == (tmp_path / ".run" / "reports")
    assert cfg.trace_report_markdown.name.startswith("omni-agent-trace-reconstruction-quick-")
    assert cfg.trace_report_markdown.suffix == ".md"
    assert cfg.cross_group_report_json.parent == (tmp_path / ".run" / "reports")
    assert cfg.cross_group_report_json.name.startswith("agent-channel-cross-group-complex-quick-")
    assert cfg.cross_group_report_json.suffix == ".json"
    assert cfg.cross_group_report_markdown.parent == (tmp_path / ".run" / "reports")
    assert cfg.cross_group_report_markdown.name.startswith(
        "agent-channel-cross-group-complex-quick-"
    )
    assert cfg.cross_group_report_markdown.suffix == ".md"
    assert cfg.benchmark_iterations == 3
    assert cfg.max_mcp_call_waiting_events == 0
    assert cfg.max_mcp_connect_waiting_events == 0
    assert cfg.max_mcp_waiting_events_total == 0


def test_parse_args_honors_explicit_artifact_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    webhook_port = pick_free_port()
    telegram_port = pick_free_port()
    valkey_port = pick_free_port()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_memory_ci_gate.py",
            "--profile",
            "nightly",
            "--webhook-port",
            str(webhook_port),
            "--telegram-api-port",
            str(telegram_port),
            "--valkey-port",
            str(valkey_port),
            "--runtime-log-file",
            "custom/runtime.log",
            "--mock-log-file",
            "custom/mock.log",
            "--evolution-report-json",
            "custom/evolution.json",
            "--benchmark-report-json",
            "custom/benchmark.json",
            "--session-matrix-report-json",
            "custom/matrix.json",
            "--session-matrix-report-markdown",
            "custom/matrix.md",
            "--trace-report-json",
            "custom/trace.json",
            "--trace-report-markdown",
            "custom/trace.md",
            "--cross-group-report-json",
            "custom/cross-group.json",
            "--cross-group-report-markdown",
            "custom/cross-group.md",
        ],
    )

    cfg = parse_args(tmp_path)

    assert cfg.runtime_log_file == (tmp_path / "custom/runtime.log").resolve()
    assert cfg.mock_log_file == (tmp_path / "custom/mock.log").resolve()
    assert cfg.evolution_report_json == (tmp_path / "custom/evolution.json").resolve()
    assert cfg.benchmark_report_json == (tmp_path / "custom/benchmark.json").resolve()
    assert cfg.session_matrix_report_json == (tmp_path / "custom/matrix.json").resolve()
    assert cfg.session_matrix_report_markdown == (tmp_path / "custom/matrix.md").resolve()
    assert cfg.trace_report_json == (tmp_path / "custom/trace.json").resolve()
    assert cfg.trace_report_markdown == (tmp_path / "custom/trace.md").resolve()
    assert cfg.cross_group_report_json == (tmp_path / "custom/cross-group.json").resolve()
    assert cfg.cross_group_report_markdown == (tmp_path / "custom/cross-group.md").resolve()


def test_parse_args_sets_skip_rust_regressions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    webhook_port = pick_free_port()
    telegram_port = pick_free_port()
    valkey_port = pick_free_port()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_memory_ci_gate.py",
            "--profile",
            "nightly",
            "--webhook-port",
            str(webhook_port),
            "--telegram-api-port",
            str(telegram_port),
            "--valkey-port",
            str(valkey_port),
            "--skip-rust-regressions",
        ],
    )
    cfg = parse_args(tmp_path)
    assert cfg.skip_rust_regressions is True


def test_parse_args_accepts_agent_bin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    webhook_port = pick_free_port()
    telegram_port = pick_free_port()
    valkey_port = pick_free_port()
    agent_bin = tmp_path / "omni-agent"
    agent_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_memory_ci_gate.py",
            "--profile",
            "quick",
            "--webhook-port",
            str(webhook_port),
            "--telegram-api-port",
            str(telegram_port),
            "--valkey-port",
            str(valkey_port),
            "--agent-bin",
            str(agent_bin),
        ],
    )
    cfg = parse_args(tmp_path)
    assert cfg.agent_bin == agent_bin.resolve()
