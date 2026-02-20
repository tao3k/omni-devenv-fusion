"""Tests for scripts/channel/test_omni_agent_session_matrix.py."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_matrix_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_session_matrix.py"
    spec = importlib.util.spec_from_file_location("omni_agent_session_matrix_probe", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "max_wait": 35,
        "max_idle_secs": 25,
        "webhook_url": "http://127.0.0.1:8081/telegram/webhook",
        "log_file": ".run/logs/omni-agent-webhook.log",
        "chat_id": None,
        "chat_b": None,
        "chat_c": None,
        "user_a": None,
        "user_b": None,
        "user_c": None,
        "username": None,
        "thread_a": None,
        "thread_b": None,
        "thread_c": None,
        "mixed_plain_prompt": "Please reply with one short sentence for mixed concurrency probe.",
        "secret_token": None,
        "output_json": ".run/reports/agent-channel-session-matrix.json",
        "output_markdown": ".run/reports/agent-channel-session-matrix.md",
        "forbid_log_regex": ["tools/call: Mcp error"],
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_expected_session_key() -> None:
    module = _load_matrix_module()
    assert module.expected_session_key(100, 7, None) == "100:7"
    assert module.expected_session_key(-100228, 7, 42) == "-100228:42:7"


def test_build_config_infers_chat_user_from_runtime_log(tmp_path: Path, monkeypatch) -> None:
    module = _load_matrix_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=1304799691:1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(tmp_path / "missing.env"))
    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.chat_id == 1304799691
    assert cfg.user_a == 1304799691
    assert cfg.user_b == 1304799692


def test_build_config_prefers_group_profile_file(tmp_path: Path, monkeypatch) -> None:
    module = _load_matrix_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n"
        "OMNI_TEST_USER_ID=1304799691\n"
        "OMNI_TEST_USER_B=1304799692\n"
        "OMNI_TEST_USER_C=1304799693\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    args = _make_args(log_file=str(tmp_path / "missing.log"))
    cfg = module.build_config(args)
    assert cfg.chat_id == -5101776367
    assert cfg.chat_b == -5020317863
    assert cfg.chat_c == -5292802281
    assert cfg.user_a == 1304799691
    assert cfg.user_b == 1304799692
    assert cfg.user_c == 1304799693


def test_build_config_defaults_thread_ids_for_chat_thread_user(tmp_path: Path, monkeypatch) -> None:
    module = _load_matrix_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_thread_user")
    args = _make_args(
        log_file=str(log_file),
        chat_id=-5101776367,
        chat_b=-5020317863,
        chat_c=-5292802281,
        user_a=1304799691,
        user_b=1304799692,
        user_c=1304799693,
        thread_a=None,
        thread_b=None,
        thread_c=None,
    )

    cfg = module.build_config(args)
    assert cfg.thread_a == 0
    assert cfg.thread_b == 0
    assert cfg.thread_c == 0


def test_build_matrix_steps_contains_cross_reset_resume() -> None:
    module = _load_matrix_module()
    cfg = module.ProbeConfig(
        max_wait=35,
        max_idle_secs=25,
        webhook_url="http://127.0.0.1:8081/telegram/webhook",
        log_file=Path(".run/logs/omni-agent-webhook.log"),
        chat_id=130,
        chat_b=130,
        chat_c=130,
        user_a=1,
        user_b=2,
        user_c=3,
        username="tester",
        thread_a=None,
        thread_b=None,
        thread_c=None,
        mixed_plain_prompt="hello",
        secret_token=None,
        output_json=Path(".run/reports/agent-channel-session-matrix.json"),
        output_markdown=Path(".run/reports/agent-channel-session-matrix.md"),
        forbid_log_regexes=("tools/call: Mcp error",),
    )
    steps = module.build_matrix_steps(cfg)
    names = [step.name for step in steps]
    assert names[0] == "reset_session_a"
    assert "resume_status_session_a" in names
    assert "session_status_session_b_after_a_reset" in names
    assert "session_status_session_c_after_a_reset" in names
    assert "resume_status_session_b" in names
    assert names[-2:] == ["resume_drop_session_a", "resume_drop_session_b"]


def test_render_markdown_includes_failure_tail() -> None:
    module = _load_matrix_module()
    report = {
        "started_at": "2026-02-18T12:00:00+00:00",
        "finished_at": "2026-02-18T12:00:10+00:00",
        "duration_ms": 10000,
        "overall_passed": False,
        "summary": {"total": 2, "passed": 1, "failed": 1},
        "config": {
            "chat_id": 130,
            "chat_b": 130,
            "chat_c": 130,
            "user_a": 1,
            "user_b": 2,
            "user_c": 3,
            "thread_a": None,
            "thread_b": None,
            "thread_c": None,
            "log_file": ".run/logs/omni-agent-webhook.log",
        },
        "steps": [
            {
                "name": "concurrent_baseline",
                "kind": "concurrent",
                "session_key": "130:1 | 130:2",
                "prompt": "/session json (concurrent)",
                "event": "telegram.command.session_status_json.replied",
                "duration_ms": 123,
                "passed": True,
                "stdout_tail": "ok",
                "stderr_tail": "",
            },
            {
                "name": "resume_status_session_a",
                "kind": "blackbox",
                "session_key": "130:1",
                "prompt": "/resume status",
                "event": "telegram.command.session_resume_status.replied",
                "duration_ms": 456,
                "passed": False,
                "stdout_tail": "",
                "stderr_tail": "timeout",
            },
        ],
    }
    markdown = module.render_markdown(report)
    assert "Agent Channel Session Matrix Report" in markdown
    assert "FAIL" in markdown
    assert "resume_status_session_a" in markdown
    assert "timeout" in markdown


def test_build_report_summarizes_step_results() -> None:
    module = _load_matrix_module()
    cfg = module.ProbeConfig(
        max_wait=35,
        max_idle_secs=25,
        webhook_url="http://127.0.0.1:8081/telegram/webhook",
        log_file=Path(".run/logs/omni-agent-webhook.log"),
        chat_id=130,
        chat_b=130,
        chat_c=130,
        user_a=1,
        user_b=2,
        user_c=3,
        username="tester",
        thread_a=None,
        thread_b=None,
        thread_c=None,
        mixed_plain_prompt="hello",
        secret_token=None,
        output_json=Path(".run/reports/agent-channel-session-matrix.json"),
        output_markdown=Path(".run/reports/agent-channel-session-matrix.md"),
        forbid_log_regexes=("tools/call: Mcp error",),
    )
    results = [
        module.StepResult(
            name="concurrent_baseline",
            kind="concurrent",
            session_key="130:1 | 130:2",
            prompt="/session json (concurrent)",
            event="telegram.command.session_status_json.replied",
            command=("python", "x.py"),
            returncode=0,
            duration_ms=100,
            passed=True,
            stdout_tail="ok",
            stderr_tail="",
        ),
        module.StepResult(
            name="reset_session_a",
            kind="blackbox",
            session_key="130:1",
            prompt="/reset",
            event="telegram.command.session_reset.replied",
            command=("python", "x.py"),
            returncode=1,
            duration_ms=200,
            passed=False,
            stdout_tail="",
            stderr_tail="failed",
        ),
    ]
    report = module.build_report(
        cfg=cfg,
        results=results,
        started_dt=datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC),
        started_mono=0.0,
    )
    assert report["summary"]["total"] == 2
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 1
    assert report["overall_passed"] is False


def test_build_config_auto_assigns_thread_b_and_session_b_for_cross_thread(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_matrix_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=-1001:42:1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(tmp_path / "missing.env"))
    args = _make_args(log_file=str(log_file), thread_a=42)
    cfg = module.build_config(args)
    assert cfg.thread_b == 43
    assert cfg.user_b == cfg.user_a


def test_build_config_rejects_non_unique_session_keys() -> None:
    module = _load_matrix_module()
    args = _make_args(
        chat_id=-5101776367,
        chat_b=-5101776367,
        chat_c=-5292802281,
        user_a=1304799691,
        user_b=1304799691,
        user_c=1304799693,
        thread_a=None,
        thread_b=None,
        thread_c=None,
    )
    try:
        module.build_config(args)
        assert False, "expected duplicate session-key validation to fail"
    except ValueError as error:
        assert "three distinct session identities" in str(error)


def test_build_matrix_steps_with_thread_scope_emit_thread_partition_keys() -> None:
    module = _load_matrix_module()
    cfg = module.ProbeConfig(
        max_wait=35,
        max_idle_secs=25,
        webhook_url="http://127.0.0.1:8081/telegram/webhook",
        log_file=Path(".run/logs/omni-agent-webhook.log"),
        chat_id=-5101776367,
        chat_b=-5101776367,
        chat_c=-5292802281,
        user_a=1304799691,
        user_b=1304799691,
        user_c=1304799693,
        username="tester",
        thread_a=42,
        thread_b=43,
        thread_c=99,
        mixed_plain_prompt="hello",
        secret_token=None,
        output_json=Path(".run/reports/agent-channel-session-matrix.json"),
        output_markdown=Path(".run/reports/agent-channel-session-matrix.md"),
        forbid_log_regexes=("tools/call: Mcp error",),
    )
    steps = {step.name: step for step in module.build_matrix_steps(cfg)}
    assert "json_partition_key=-5101776367:42:1304799691" in (
        steps["session_status_session_a_after_reset"].expect_reply_json_fields
    )
    assert "json_partition_key=-5101776367:43:1304799691" in (
        steps["session_status_session_b_after_a_reset"].expect_reply_json_fields
    )
    assert "json_partition_key=-5292802281:99:1304799693" in (
        steps["session_status_session_c_after_a_reset"].expect_reply_json_fields
    )


def test_should_retry_on_restart_noise_detects_webhook_bootstrap_output() -> None:
    module = _load_matrix_module()
    stdout = (
        "Telegram webhook listening on 0.0.0.0:8081/telegram/webhook (Ctrl+C to stop)\n"
        "Webhook dedup backend: valkey (ttl=600s)\n"
    )
    assert module.should_retry_on_restart_noise(3, stdout, "") is True
    assert module.should_retry_on_restart_noise(0, stdout, "") is False


def test_run_command_with_restart_retry_retries_once_on_restart_noise(monkeypatch) -> None:
    module = _load_matrix_module()
    calls: list[int] = []

    def fake_run(_cmd: list[str]) -> tuple[int, int, str, str]:
        calls.append(1)
        if len(calls) == 1:
            return (
                3,
                12,
                "Telegram webhook listening on 0.0.0.0:8081/telegram/webhook (Ctrl+C to stop)\n",
                "",
            )
        return (0, 8, "ok\n", "")

    monkeypatch.setattr(module, "_run_command", fake_run)
    returncode, duration_ms, stdout, stderr = module.run_command_with_restart_retry(
        ["python", "x.py"]
    )
    assert len(calls) == 2
    assert returncode == 0
    assert duration_ms == 20
    assert "matrix-retry" in stdout
    assert "ok" in stdout
    assert stderr == ""
