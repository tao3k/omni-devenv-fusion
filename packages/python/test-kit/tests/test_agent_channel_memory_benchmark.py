"""Tests for scripts/channel/test_omni_agent_memory_benchmark.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _load_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_memory_benchmark.py"
    spec = importlib.util.spec_from_file_location("omni_agent_memory_benchmark", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_scenarios_from_default_fixture() -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "memory_benchmark_scenarios.json"
    )
    scenarios = module.load_scenarios(fixture_path)
    assert len(scenarios) >= 3
    assert scenarios[0].scenario_id == "preference_recall"
    assert len(scenarios[0].queries) == 2


def test_keyword_hit_ratio_is_case_insensitive() -> None:
    module = _load_module()
    ratio = module.keyword_hit_ratio(
        '"Use Bullet style with Valkey and Postgres."',
        ("bullet", "VALKEY", "postgres"),
    )
    assert ratio == 1.0
    assert module.keyword_hit_ratio(None, ("atlas-echo-42",)) == 0.0
    assert module.keyword_hit_ratio("anything", ()) is None


def test_summarize_mode_counts_feedback_and_success() -> None:
    module = _load_module()

    turn_pass = module.TurnResult(
        mode="adaptive",
        iteration=1,
        scenario_id="s1",
        query_index=1,
        prompt="p1",
        expected_keywords=("valkey",),
        required_ratio=1.0,
        keyword_hit_ratio=1.0,
        keyword_success=True,
        decision="injected",
        query_tokens=20,
        recalled_selected=3,
        recalled_injected=2,
        context_chars_injected=320,
        pipeline_duration_ms=15,
        best_score=0.8,
        weakest_score=0.4,
        k1=20,
        k2=5,
        lambda_value=0.3,
        min_score=0.08,
        budget_pressure=0.1,
        window_pressure=0.2,
        recall_feedback_bias=0.0,
        feedback_direction="up",
        feedback_bias_before=0.0,
        feedback_bias_after=0.1,
        mcp_error_detected=False,
        bot_excerpt="Valkey",
    )
    turn_fail = module.TurnResult(
        mode="adaptive",
        iteration=1,
        scenario_id="s1",
        query_index=2,
        prompt="p2",
        expected_keywords=("atlas",),
        required_ratio=1.0,
        keyword_hit_ratio=0.0,
        keyword_success=False,
        decision="skipped",
        query_tokens=18,
        recalled_selected=1,
        recalled_injected=0,
        context_chars_injected=0,
        pipeline_duration_ms=22,
        best_score=0.2,
        weakest_score=0.2,
        k1=16,
        k2=4,
        lambda_value=0.35,
        min_score=0.1,
        budget_pressure=0.2,
        window_pressure=0.25,
        recall_feedback_bias=0.1,
        feedback_direction="down",
        feedback_bias_before=0.1,
        feedback_bias_after=0.0,
        mcp_error_detected=True,
        bot_excerpt="not found",
    )

    summary = module.summarize_mode(
        mode="adaptive",
        iterations=1,
        scenario_count=1,
        turns=[turn_pass, turn_fail],
    )
    assert summary.query_turns == 2
    assert summary.scored_turns == 2
    assert summary.success_count == 1
    assert summary.success_rate == 0.5
    assert summary.injected_count == 1
    assert summary.skipped_count == 1
    assert summary.feedback_updates == 2
    assert summary.feedback_up_count == 1
    assert summary.feedback_down_count == 1
    assert summary.mcp_error_turns == 1


def test_select_feedback_direction_deadband_vs_strict() -> None:
    module = _load_module()

    strict_down = module.select_feedback_direction(
        keyword_hit_ratio=0.66,
        keyword_success=False,
        policy="strict",
        down_threshold=0.34,
    )
    deadband_neutral = module.select_feedback_direction(
        keyword_hit_ratio=0.66,
        keyword_success=False,
        policy="deadband",
        down_threshold=0.34,
    )
    deadband_down = module.select_feedback_direction(
        keyword_hit_ratio=0.0,
        keyword_success=False,
        policy="deadband",
        down_threshold=0.34,
    )
    up = module.select_feedback_direction(
        keyword_hit_ratio=1.0,
        keyword_success=True,
        policy="deadband",
        down_threshold=0.34,
    )

    assert strict_down == "down"
    assert deadband_neutral is None
    assert deadband_down == "down"
    assert up == "up"


def test_has_event_matches_event_token() -> None:
    module = _load_module()
    lines = [
        '2026-01-01T00:00:00Z INFO foo event="telegram.command.session_reset.replied"',
        '2026-01-01T00:00:01Z INFO foo event="agent.memory.recall.planned"',
    ]
    assert module.has_event(lines, "agent.memory.recall.planned")
    assert not module.has_event(lines, "telegram.command.control_admin_required.replied")


def test_resolve_runtime_partition_mode_prefers_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat")
    monkeypatch.setattr(
        module, "session_partition_mode_from_runtime_log", lambda _path: "chat_user"
    )
    monkeypatch.setattr(module, "telegram_session_partition_mode", lambda: "chat_user")
    assert module.resolve_runtime_partition_mode(tmp_path / "runtime.log") == "chat"


def test_run_probe_raises_runtime_error_when_control_command_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    log_file = tmp_path / "runtime.log"
    log_file.write_text("", encoding="utf-8")

    config = module.BenchmarkConfig(
        dataset_path=tmp_path / "dataset.json",
        log_file=log_file,
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        chat_id=1304799691,
        user_id=1304799702,
        thread_id=None,
        runtime_partition_mode="chat",
        username="ci-user",
        max_wait=90,
        max_idle_secs=40,
        modes=("baseline", "adaptive"),
        iterations=1,
        skip_reset=False,
        output_json=tmp_path / "report.json",
        output_markdown=tmp_path / "report.md",
        fail_on_mcp_error=False,
        feedback_policy="deadband",
        feedback_down_threshold=0.34,
    )

    def _fake_count_lines(path: object) -> int:
        return 0

    def _fake_read_new_lines(path: object, cursor: int) -> tuple[int, list[str]]:
        return (
            cursor + 1,
            [
                "2026-01-01T00:00:00Z INFO foo "
                'event="telegram.command.control_admin_required.replied"'
            ],
        )

    def _fake_run(cmd: list[str], check: bool) -> None:
        raise subprocess.CalledProcessError(returncode=7, cmd=cmd)

    monkeypatch.setattr(module, "count_lines", _fake_count_lines)
    monkeypatch.setattr(module, "read_new_lines", _fake_read_new_lines)
    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    with pytest.raises(RuntimeError, match="admin-capable Telegram user"):
        module.run_probe(
            config,
            prompt="/reset",
            expect_event=module.RESET_EVENT,
            allow_no_bot=True,
        )


def test_run_probe_passes_session_partition_hint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    log_file = tmp_path / "runtime.log"
    log_file.write_text("", encoding="utf-8")
    captured_cmd: list[str] = []

    config = module.BenchmarkConfig(
        dataset_path=tmp_path / "dataset.json",
        log_file=log_file,
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        chat_id=1304799691,
        user_id=1304799702,
        thread_id=None,
        runtime_partition_mode="chat",
        username="ci-user",
        max_wait=90,
        max_idle_secs=40,
        modes=("baseline", "adaptive"),
        iterations=1,
        skip_reset=False,
        output_json=tmp_path / "report.json",
        output_markdown=tmp_path / "report.md",
        fail_on_mcp_error=False,
        feedback_policy="deadband",
        feedback_down_threshold=0.34,
    )

    monkeypatch.setattr(module, "count_lines", lambda _path: 0)
    monkeypatch.setattr(module, "read_new_lines", lambda _path, _cursor: (0, []))

    def _fake_run(cmd: list[str], check: bool) -> None:
        captured_cmd[:] = cmd

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    module.run_probe(
        config,
        prompt="/reset",
        expect_event=module.RESET_EVENT,
    )
    assert "--session-partition" in captured_cmd
    partition_index = captured_cmd.index("--session-partition")
    assert captured_cmd[partition_index + 1] == "chat"
