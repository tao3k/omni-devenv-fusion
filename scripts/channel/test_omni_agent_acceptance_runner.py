#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_acceptance_module():
    module_path = Path(__file__).resolve().with_name("test_omni_agent_acceptance.py")
    spec = importlib.util.spec_from_file_location("test_omni_agent_acceptance", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_run_step_success(tmp_path: Path) -> None:
    module = _load_acceptance_module()
    output_file = tmp_path / "ok.txt"
    cmd = ["python3", "-c", f"open(r'{output_file}', 'w', encoding='utf-8').write('ok')"]
    result = module.run_step(
        step="success",
        title="ok",
        cmd=cmd,
        expected_outputs=[output_file],
        attempts=1,
    )
    assert result.passed
    assert result.returncode == 0
    assert result.missing_outputs == ()


def test_run_step_missing_output_marks_failure(tmp_path: Path) -> None:
    module = _load_acceptance_module()
    missing_file = tmp_path / "missing.json"
    result = module.run_step(
        step="missing-output",
        title="missing",
        cmd=["python3", "-c", "print('ok')"],
        expected_outputs=[missing_file],
        attempts=1,
    )
    assert not result.passed
    assert result.returncode == 0
    assert str(missing_file) in result.missing_outputs


def test_to_markdown_contains_failure_tail() -> None:
    module = _load_acceptance_module()
    report = {
        "started_at": "2026-02-20T00:00:00+00:00",
        "finished_at": "2026-02-20T00:00:01+00:00",
        "duration_ms": 1000,
        "overall_passed": False,
        "summary": {"total": 1, "passed": 0, "failed": 1},
        "artifacts": {
            "group_profile_json": ".run/config/agent-channel-groups.json",
            "group_profile_env": ".run/config/agent-channel-groups.env",
            "matrix_json": ".run/reports/agent-channel-session-matrix.json",
            "complex_json": ".run/reports/agent-channel-complex-scenarios.json",
            "memory_evolution_json": ".run/reports/agent-channel-memory-evolution.json",
        },
        "steps": [
            {
                "step": "command_events",
                "passed": False,
                "returncode": 1,
                "attempts": 2,
                "duration_ms": 123,
                "missing_outputs": [".run/reports/x.json"],
                "stderr_tail": "boom",
                "stdout_tail": "",
            }
        ],
    }
    markdown = module.to_markdown(report)
    assert "Agent Channel Acceptance Report" in markdown
    assert "missing_outputs" in markdown
    assert "boom" in markdown

    # Ensure report is JSON-serializable in expected shape.
    json.dumps(report)


def test_build_config_resolves_group_thread_from_env(monkeypatch) -> None:
    module = _load_acceptance_module()
    monkeypatch.setenv("OMNI_TEST_GROUP_THREAD_ID", "42")
    monkeypatch.delenv("OMNI_TEST_GROUP_THREAD_B", raising=False)
    args = argparse.Namespace(
        titles="Test1,Test2,Test3",
        log_file=".run/logs/omni-agent-webhook.log",
        output_json=".run/reports/agent-channel-acceptance.json",
        output_markdown=".run/reports/agent-channel-acceptance.md",
        group_profile_json=".run/config/agent-channel-groups.json",
        group_profile_env=".run/config/agent-channel-groups.env",
        max_wait=40,
        max_idle_secs=25,
        group_thread_id=None,
        group_thread_id_b=None,
        evolution_max_wait=90,
        evolution_max_idle_secs=60,
        evolution_max_parallel=4,
        retries=2,
    )
    cfg = module.build_config(args)
    assert cfg.group_thread_id == 42
    assert cfg.group_thread_id_b == 43


def test_run_pipeline_includes_topic_isolation_step_when_thread_is_configured(
    tmp_path: Path,
) -> None:
    module = _load_acceptance_module()
    observed: list[tuple[str, tuple[str, ...]]] = []

    def _fake_run_step(*, step, title, cmd, expected_outputs, attempts):
        observed.append((step, tuple(cmd)))
        return module.StepResult(
            step=step,
            title=title,
            command=tuple(cmd),
            returncode=0,
            duration_ms=1,
            attempts=attempts,
            passed=True,
            expected_outputs=tuple(str(path) for path in expected_outputs),
            missing_outputs=(),
            stdout_tail="",
            stderr_tail="",
        )

    module.run_step = _fake_run_step
    cfg = module.AcceptanceConfig(
        titles="Test1,Test2,Test3",
        log_file=tmp_path / "runtime.log",
        output_json=tmp_path / "acceptance.json",
        output_markdown=tmp_path / "acceptance.md",
        group_profile_json=tmp_path / "groups.json",
        group_profile_env=tmp_path / "groups.env",
        max_wait=40,
        max_idle_secs=25,
        group_thread_id=42,
        group_thread_id_b=43,
        evolution_max_wait=90,
        evolution_max_idle_secs=60,
        evolution_max_parallel=4,
        retries=1,
    )
    report = module.run_pipeline(cfg)
    assert report["overall_passed"] is True

    by_step = {step: cmd for step, cmd in observed}
    assert "command_events_topic_isolation" in by_step
    assert "--assert-admin-topic-isolation" in by_step["command_events_topic_isolation"]
    assert "--group-thread-id" in by_step["command_events_topic_isolation"]
    assert "--group-thread-id-b" in by_step["command_events_topic_isolation"]
    assert "--thread-a" in by_step["session_matrix"]
    assert "--thread-b" in by_step["session_matrix"]


def test_run_pipeline_skips_topic_isolation_step_when_thread_is_not_configured(
    tmp_path: Path,
) -> None:
    module = _load_acceptance_module()
    observed: list[tuple[str, tuple[str, ...]]] = []

    def _fake_run_step(*, step, title, cmd, expected_outputs, attempts):
        observed.append((step, tuple(cmd)))
        return module.StepResult(
            step=step,
            title=title,
            command=tuple(cmd),
            returncode=0,
            duration_ms=1,
            attempts=attempts,
            passed=True,
            expected_outputs=tuple(str(path) for path in expected_outputs),
            missing_outputs=(),
            stdout_tail="",
            stderr_tail="",
        )

    module.run_step = _fake_run_step
    cfg = module.AcceptanceConfig(
        titles="Test1,Test2,Test3",
        log_file=tmp_path / "runtime.log",
        output_json=tmp_path / "acceptance.json",
        output_markdown=tmp_path / "acceptance.md",
        group_profile_json=tmp_path / "groups.json",
        group_profile_env=tmp_path / "groups.env",
        max_wait=40,
        max_idle_secs=25,
        group_thread_id=None,
        group_thread_id_b=None,
        evolution_max_wait=90,
        evolution_max_idle_secs=60,
        evolution_max_parallel=4,
        retries=1,
    )
    report = module.run_pipeline(cfg)
    assert report["overall_passed"] is True

    by_step = {step: cmd for step, cmd in observed}
    assert "command_events_topic_isolation" not in by_step
    assert "--thread-a" not in by_step["session_matrix"]
    assert "--thread-b" not in by_step["session_matrix"]
