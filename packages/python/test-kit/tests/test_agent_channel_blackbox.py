"""Tests for scripts/channel/agent_channel_blackbox.py."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _load_probe_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "agent_channel_blackbox.py"
    spec = importlib.util.spec_from_file_location("omni_agent_channel_blackbox_probe", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "prompt": "hello",
        "max_wait": None,
        "timeout": None,
        "max_idle_secs": None,
        "webhook_url": "http://127.0.0.1:8081/telegram/webhook",
        "log_file": ".run/logs/omni-agent-webhook.log",
        "chat_id": None,
        "user_id": None,
        "username": None,
        "chat_title": None,
        "thread_id": None,
        "secret_token": None,
        "no_follow": False,
        "expect_event": [],
        "expect_reply_json_field": [],
        "expect_log_regex": [],
        "expect_bot_regex": [],
        "forbid_log_regex": [],
        "no_fail_fast_error_log": False,
        "allow_no_bot": False,
        "allow_chat_id": [],
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_config(module: ModuleType, log_file: Path, **overrides: object):
    base = {
        "prompt": "hello",
        "max_wait_secs": 5,
        "max_idle_secs": None,
        "webhook_url": "http://127.0.0.1:8081/telegram/webhook",
        "log_file": log_file,
        "chat_id": 1001,
        "user_id": 2002,
        "username": None,
        "chat_title": None,
        "thread_id": None,
        "secret_token": None,
        "follow_logs": False,
        "expect_events": (),
        "expect_reply_json_fields": (),
        "expect_log_regexes": (),
        "expect_bot_regexes": (),
        "forbid_log_regexes": (),
        "fail_fast_error_logs": True,
        "allow_no_bot": False,
        "allow_chat_ids": (),
    }
    base.update(overrides)
    return module.ProbeConfig(**base)


def _sequence_reader(chunks: list[list[str]]):
    state = {"idx": 0}

    def _read_new_lines(_: Path, cursor: int) -> tuple[int, list[str]]:
        if state["idx"] >= len(chunks):
            return cursor, []
        chunk = chunks[state["idx"]]
        state["idx"] += 1
        return cursor + len(chunk), chunk

    return _read_new_lines


def _fake_clock(step: float = 0.5):
    state = {"now": 0.0}

    def _monotonic() -> float:
        state["now"] += step
        return state["now"]

    return _monotonic


def test_build_config_defaults_to_event_driven_wait(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "2026-02-18 INFO Parsed message, forwarding to agent session_key=-1002286094098:1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.max_wait_secs is None
    assert cfg.max_idle_secs is None
    assert cfg.chat_id == -1002286094098
    assert cfg.user_id == 1304799691


def test_build_config_infers_ids_from_ansi_colored_log(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        (
            "2026-02-18 INFO Parsed message, forwarding to agent "
            "\x1b[3msession_key\x1b[0m\x1b[2m=\x1b[0m-1002286094098:1304799691 "
            "\x1b[3mcontent_preview\x1b[0m\x1b[2m=\x1b[0m/session json\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.chat_id == -1002286094098
    assert cfg.user_id == 1304799691


def test_build_config_infers_ids_from_quoted_session_key_log(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        (
            "2026-02-18 INFO Parsed message, forwarding to agent "
            'session_key="1304799691:1304799691" content_preview=/session json\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.chat_id == 1304799691
    assert cfg.user_id == 1304799691


def test_extract_session_key_token_from_quoted_field() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-18 INFO Parsed message, forwarding to agent "
        'session_key="1304799691:1304799691" content_preview=/session json'
    )
    assert module.extract_session_key_token(line) == "1304799691:1304799691"


def test_expected_session_key_formats_with_optional_thread() -> None:
    module = _load_probe_module()
    assert module.expected_session_key(1304799691, 1304799695, None) == "1304799691:1304799695"
    assert (
        module.expected_session_key(-1002286094098, 1304799695, 42)
        == "-1002286094098:42:1304799695"
    )


def test_expected_session_keys_accept_zero_thread_alias_when_thread_is_none() -> None:
    module = _load_probe_module()
    assert module.expected_session_keys(1304799691, 1304799695, None) == (
        "1304799691:1304799695",
        "1304799691:0:1304799695",
    )
    assert module.expected_session_keys(-1002286094098, 1304799695, 42) == (
        "-1002286094098:42:1304799695",
    )


def test_expected_recipient_key_formats_with_optional_thread() -> None:
    module = _load_probe_module()
    assert module.expected_recipient_key(1304799691, None) == "1304799691"
    assert module.expected_recipient_key(-1002286094098, 42) == "-1002286094098:42"


def test_infer_username_from_log_from_allowed_users_command(tmp_path) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        (
            "2026-02-18 INFO Running `target/debug/omni-agent channel --mode webhook "
            "--verbose --webhook-bind 0.0.0.0:8081 --allowed-users tao3k --allowed-groups ''`\n"
        ),
        encoding="utf-8",
    )
    assert module.infer_username_from_log(log_file) == "tao3k"


def test_build_config_infers_username_from_log_when_missing(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        (
            "2026-02-18 INFO Running `target/debug/omni-agent channel --mode webhook "
            "--verbose --webhook-bind 0.0.0.0:8081 --allowed-users tao3k --allowed-groups ''`\n"
            "2026-02-18 INFO Parsed message, forwarding to agent session_key=-1002286094098:1304799691\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    monkeypatch.setattr(module, "username_from_settings", lambda: None)
    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.username == "tao3k"


def test_build_config_parses_expect_reply_json_fields(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "2026-02-18 INFO Parsed message, forwarding to agent session_key=1001:2002\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(
        log_file=str(log_file),
        expect_reply_json_field=["json_kind=session_budget", "json_available=false"],
    )
    cfg = module.build_config(args)
    assert cfg.expect_reply_json_fields == (
        ("json_kind", "session_budget"),
        ("json_available", "false"),
    )


def test_build_config_applies_allow_chat_id_filter(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "2026-02-18 INFO Parsed message, forwarding to agent session_key=1001:2002\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(log_file=str(log_file), allow_chat_id=["1001", "1002"])
    cfg = module.build_config(args)
    assert cfg.allow_chat_ids == (1001, 1002)
    assert cfg.strong_update_id is True


def test_next_update_id_legacy_mode_uses_epoch_ms(monkeypatch) -> None:
    module = _load_probe_module()
    monkeypatch.setattr(module.time, "time", lambda: 1_700_000_001.234)
    assert module.next_update_id(False) == 1_700_000_001_234


def test_next_update_id_strong_mode_adds_pid_nonce(monkeypatch) -> None:
    module = _load_probe_module()
    monkeypatch.setattr(module.time, "time", lambda: 1_700_000_001.000)
    monkeypatch.setattr(module.os, "getpid", lambda: 4242)
    monkeypatch.setattr(module, "_LAST_STRONG_UPDATE_ID", 0)

    update_id = module.next_update_id(True)
    assert update_id == 1_700_000_001_000 + 4242


def test_next_update_id_strong_mode_monotonic(monkeypatch) -> None:
    module = _load_probe_module()
    monkeypatch.setattr(module.time, "time", lambda: 1_700_000_001.000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module, "_LAST_STRONG_UPDATE_ID", 1_700_000_005_000)

    update_id = module.next_update_id(True)
    assert update_id == 1_700_000_005_001


def test_build_config_rejects_chat_id_outside_allowlist(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "2026-02-18 INFO Parsed message, forwarding to agent session_key=1001:2002\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_WAIT_SECS", raising=False)
    monkeypatch.delenv("OMNI_BLACKBOX_MAX_IDLE_SECS", raising=False)
    args = _make_args(log_file=str(log_file), allow_chat_id=["2001"])
    try:
        module.build_config(args)
    except ValueError as error:
        assert "not in allowlist" in str(error)
        return
    raise AssertionError("expected ValueError for chat id outside allowlist")


def test_build_update_payload_includes_username_when_provided() -> None:
    module = _load_probe_module()
    payload = module.build_update_payload(
        update_id=1_700_000_000_000,
        chat_id=123,
        user_id=456,
        username="tao3k",
        chat_title=None,
        text="hello",
        thread_id=None,
    )
    parsed = json.loads(payload)
    assert parsed["message"]["from"]["username"] == "tao3k"


def test_build_update_payload_includes_chat_title_when_provided() -> None:
    module = _load_probe_module()
    payload = module.build_update_payload(
        update_id=1_700_000_000_001,
        chat_id=-5101776367,
        user_id=456,
        username="tao3k",
        chat_title="Test1",
        text="hello",
        thread_id=None,
    )
    parsed = json.loads(payload)
    assert parsed["message"]["chat"]["title"] == "Test1"


def test_build_probe_message_keeps_slash_command_unchanged() -> None:
    module = _load_probe_module()
    message = module.build_probe_message("/reset", "bbx-1")
    assert message == "/reset"


def test_build_probe_message_prefixes_non_command_prompt() -> None:
    module = _load_probe_module()
    message = module.build_probe_message("hello", "bbx-2")
    assert message == "[bbx-2] hello"


def test_extract_event_token_allows_spaces_around_equals() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
        'event = "telegram.command.session_status_json.replied" '
        "telegram command reply sent"
    )
    token = module.extract_event_token(line)
    assert token == "telegram.command.session_status_json.replied"


def test_parse_command_reply_event_line_extracts_core_fields() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
        "telegram command reply sent "
        'event="telegram.command.session_budget_json.replied" '
        'session_key="1304799691:1304799691" '
        'recipient="1304799691" reply_chars=131 reply_bytes=131'
    )
    parsed = module.parse_command_reply_event_line(line)
    assert parsed is not None
    assert parsed["event"] == "telegram.command.session_budget_json.replied"
    assert parsed["session_key"] == "1304799691:1304799691"
    assert parsed["recipient"] == "1304799691"
    assert parsed["reply_chars"] == 131
    assert parsed["reply_bytes"] == 131


def test_parse_command_reply_event_line_returns_none_for_non_reply_line() -> None:
    module = _load_probe_module()
    line = "2026-02-18 INFO omni_agent::channels::telegram::runtime::webhook: Webhook received"
    assert module.parse_command_reply_event_line(line) is None


def test_parse_expected_field_parses_key_value() -> None:
    module = _load_probe_module()
    assert module.parse_expected_field("json_kind=session_budget") == (
        "json_kind",
        "session_budget",
    )


def test_parse_expected_field_rejects_invalid_value() -> None:
    module = _load_probe_module()
    try:
        module.parse_expected_field("json_kind")
    except ValueError:
        return
    raise AssertionError("expected ValueError for malformed expected field")


def test_parse_command_reply_json_summary_line_extracts_fields() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
        "telegram command reply json summary "
        'event="telegram.command.session_budget_json.replied" '
        'session_key="1304799691:1304799691" '
        'recipient="1304799691" json_kind=session_budget json_available=false '
        "json_status=not_found json_found= json_decision= json_keys=4"
    )
    parsed = module.parse_command_reply_json_summary_line(line)
    assert parsed is not None
    assert parsed["event"] == "telegram.command.session_budget_json.replied"
    assert parsed["json_kind"] == "session_budget"
    assert parsed["json_available"] == "false"
    assert parsed["json_status"] == "not_found"
    assert parsed["json_keys"] == "4"


def test_parse_command_reply_json_summary_line_returns_none_for_non_summary_line() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
        "telegram command reply sent "
        'event="telegram.command.session_budget_json.replied"'
    )
    assert module.parse_command_reply_json_summary_line(line) is None


def test_telegram_send_retry_grace_seconds_prefers_delay_ms() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-20 WARN omni_agent::channels::telegram::channel::send_api: "
        "Telegram API transient failure; retrying attempt=0 max_retries=2 "
        'delay_ms=36000 method="sendMessage" error=status=429 retry_after=36s'
    )
    assert module.telegram_send_retry_grace_seconds(line) == 36.0


def test_telegram_send_retry_grace_seconds_returns_none_for_unrelated_line() -> None:
    module = _load_probe_module()
    line = (
        "2026-02-20 INFO omni_agent::channels::telegram::runtime::webhook: "
        "Parsed message, forwarding to agent session_key=1001:2002"
    )
    assert module.telegram_send_retry_grace_seconds(line) is None


def test_run_probe_fails_fast_on_known_error_line(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(module, log_file, max_wait_secs=5)

    update_id = 1_700_000_001_000
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ["2026-02-18 ERROR Foreground message handling failed: boom"],
            ]
        ),
    )

    assert module.run_probe(cfg) == 6


def test_run_probe_rejects_forbidden_regex(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        forbid_log_regexes=("tools/call: Mcp error",),
    )

    update_id = 1_700_000_002_000
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ["2026-02-18 ERROR tools/call: Mcp error: -32603: boom"],
            ]
        ),
    )

    assert module.run_probe(cfg) == 5


def test_run_probe_does_not_fail_when_duplicate_is_observed_after_dispatch(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session admin list json",
        max_wait_secs=5,
        expect_events=("telegram.command.session_admin_json.replied",),
        expect_reply_json_fields=(
            ("json_kind", "session_admin"),
            ("json_override_admin_count", "0"),
        ),
    )

    update_id = 1_700_000_002_250
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    f"2026-02-18 INFO Webhook received Telegram update update_id=Some({update_id})",
                    (
                        "2026-02-18 DEBUG telegram webhook duplicate update detected "
                        f'event="telegram.dedup.duplicate_detected" update_id={update_id}'
                    ),
                    (
                        "2026-02-18 INFO Parsed message, forwarding to agent "
                        "session_key=1001:2002 content_preview=/session admin list json"
                    ),
                    (
                        "2026-02-18 INFO telegram command reply sent "
                        'event="telegram.command.session_admin_json.replied" '
                        'session_key="1001:2002" recipient="1001" reply_chars=120 reply_bytes=120'
                    ),
                    (
                        "2026-02-18 INFO telegram command reply json summary "
                        'event="telegram.command.session_admin_json.replied" '
                        'session_key="1001:2002" recipient="1001" '
                        "json_kind=session_admin json_override_admin_count=0 json_keys=6"
                    ),
                    '2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs::observability: → Bot: "ok"',
                ]
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_fails_when_duplicate_drops_update_before_dispatch(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session admin list json",
        max_wait_secs=1,
    )

    update_id = 1_700_000_002_500
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.5))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    f"2026-02-18 INFO Webhook received Telegram update update_id=Some({update_id})",
                    (
                        "2026-02-18 DEBUG telegram webhook duplicate update detected "
                        f'event="telegram.dedup.duplicate_detected" update_id={update_id}'
                    ),
                ]
            ]
        ),
    )

    assert module.run_probe(cfg) == 4


def test_run_probe_allow_no_bot_with_expect_log_regex(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        allow_no_bot=True,
        expect_log_regexes=("skill_tool_duration",),
    )

    update_id = 1_700_000_003_000
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ["2026-02-18 INFO skill_tool_duration tool=knowledge.recall duration_ms=468.22"],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_emits_mcp_diagnostics(tmp_path, monkeypatch, capsys) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        allow_no_bot=True,
        expect_log_regexes=("session.context_window.reset",),
    )

    update_id = 1_700_000_003_250
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 DEBUG event="mcp.pool.connect.waiting" elapsed_ms=5000'],
                [
                    '2026-02-18 DEBUG event="mcp.pool.call.waiting" tool=research elapsed_ms=5000',
                    "2026-02-18 DEBUG session context window reset event=session.context_window.reset",
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0
    stdout = capsys.readouterr().out
    assert "mcp_last_event=mcp.pool.call.waiting" in stdout
    assert "mcp_waiting_seen=true" in stdout
    assert '"mcp.pool.connect.waiting":1' in stdout
    assert '"mcp.pool.call.waiting":1' in stdout


def test_run_probe_allow_no_bot_command_mode_uses_parsed_marker(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/reset",
        max_wait_secs=5,
        allow_no_bot=True,
        expect_log_regexes=("session.context_window.reset",),
    )

    update_id = 1_700_000_003_500
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                ["2026-02-18 INFO Parsed message, forwarding to agent content_preview=/reset"],
                [
                    "2026-02-18 DEBUG session context window reset event=session.context_window.reset"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_allow_no_bot_with_expect_event(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/reset",
        max_wait_secs=5,
        allow_no_bot=True,
        expect_events=("session.context_window.reset",),
    )

    update_id = 1_700_000_003_700
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                ["2026-02-18 INFO Parsed message, forwarding to agent content_preview=/reset"],
                ["2026-02-18 DEBUG event=session.context_window.reset session_id=telegram:abc"],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_allow_no_bot_with_expect_reply_json_field(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session budget json",
        max_wait_secs=5,
        allow_no_bot=True,
        expect_reply_json_fields=(("json_kind", "session_budget"), ("json_available", "false")),
    )

    update_id = 1_700_000_003_900
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    "content_preview=/session budget json"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_budget_json.replied" '
                    'session_key="1001:2002" recipient="1001" '
                    "json_kind=session_budget json_available=false "
                    "json_status=not_found json_found= json_decision= json_keys=4"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_fails_on_command_reply_session_key_mismatch(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session budget json",
        max_wait_secs=5,
        allow_no_bot=True,
        expect_reply_json_fields=(("json_kind", "session_budget"),),
    )

    update_id = 1_700_000_003_950
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    "content_preview=/session budget json"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_budget_json.replied" '
                    'session_key="1001:9999" recipient="1001" '
                    "json_kind=session_budget json_available=false "
                    "json_status=not_found json_found= json_decision= json_keys=4"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_budget_json.replied" '
                    'session_key="1001:9999" recipient="1001" '
                    "reply_chars=50 reply_bytes=50"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 10


def test_run_probe_succeeds_on_bot_reply_and_expect_bot_regex(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_bot_regexes=("research",),
    )

    update_id = 1_700_000_004_000
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "research complete"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_reports_expect_bot_regex_mismatch_when_no_match_arrives(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=20,
        max_idle_secs=20,
        expect_bot_regexes=("ACK FOUNDATIONDB",),
    )

    update_id = 1_700_000_004_250
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "DYNAMODB"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 11


def test_run_probe_waits_for_late_expect_bot_regex_match(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=20,
        max_idle_secs=20,
        expect_bot_regexes=("ACK FOUNDATIONDB",),
    )

    update_id = 1_700_000_004_300
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "DYNAMODB"'],
                ['2026-02-18 INFO → Bot: "ACK FOUNDATIONDB"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_reports_missing_expect_event_when_bot_replied(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("session.context_window.reset",),
    )

    update_id = 1_700_000_004_500
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "done"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_respects_telegram_retry_grace_before_idle_timeout(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=20,
        max_idle_secs=3,
        expect_events=("telegram.command.session_status_json.replied",),
    )

    update_id = 1_700_000_004_520
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    f'2026-02-18 INFO ← User: "[{trace_id}] hello"',
                    (
                        "2026-02-18 INFO Parsed message, forwarding to agent "
                        f"session_key=1001:2002 content_preview=[{trace_id}] hello"
                    ),
                    (
                        "2026-02-18 WARN Telegram API transient failure; retrying "
                        "attempt=0 max_retries=2 delay_ms=5000 method=sendMessage "
                        "error=status=429 retry_after=5s"
                    ),
                ],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [
                    (
                        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                        "telegram command reply sent "
                        'event="telegram.command.session_status_json.replied" '
                        'session_key="1001:2002" recipient="1001" '
                        "reply_chars=40 reply_bytes=40"
                    ),
                    '2026-02-18 INFO → Bot: "done"',
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_does_not_match_expect_event_from_other_recipient(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("telegram.command.session_status_json.replied",),
    )

    update_id = 1_700_000_004_550
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] /session json"'],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="9999:2002" recipient="9999" '
                    "reply_chars=40 reply_bytes=40"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_matches_expect_event_with_thread_scoped_recipient(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session admin add 1001",
        max_wait_secs=5,
        thread_id=42,
        expect_events=("telegram.command.session_admin.replied",),
    )

    update_id = 1_700_000_004_565
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    "session_key=1001:42:2002 content_preview=/session admin add 1001"
                ],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_admin.replied" '
                    'session_key="1001:42:2002" recipient="1001:42" '
                    "reply_chars=40 reply_bytes=40"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_thread_probe_does_not_match_chat_only_recipient(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session admin add 1001",
        max_wait_secs=5,
        thread_id=42,
        expect_events=("telegram.command.session_admin.replied",),
    )

    update_id = 1_700_000_004_566
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    "session_key=1001:42:2002 content_preview=/session admin add 1001"
                ],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_admin.replied" '
                    'session_key="1001:42:2002" recipient="1001" '
                    "reply_chars=40 reply_bytes=40"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_reports_missing_expect_reply_json_field_when_bot_replied(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_reply_json_fields=(("json_kind", "session_budget"),),
    )

    update_id = 1_700_000_004_600
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "done"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_does_not_match_reply_json_field_from_other_recipient(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("telegram.command.session_status_json.replied",),
        expect_reply_json_fields=(("json_kind", "session_context"),),
    )

    update_id = 1_700_000_004_575
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] /session json"'],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="9999:2002" recipient="9999" '
                    "reply_chars=40 reply_bytes=40"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="9999:2002" recipient="9999" '
                    "json_kind=session_context json_available=false json_status=not_found "
                    "json_found= json_decision= json_keys=4"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_expect_reply_json_field_scoped_to_expected_event(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("telegram.command.session_resume_status.replied",),
        expect_reply_json_fields=(("json_kind", "session_context"),),
    )

    update_id = 1_700_000_004_650
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] /resume status"'],
                ['2026-02-18 INFO → Bot: "No saved session context snapshot found."'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="1001:2002" recipient="1001" '
                    "json_kind=session_context json_available= json_status= "
                    "json_found= json_decision= json_keys=7"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply sent "
                    'event="telegram.command.session_resume_status.replied" '
                    'session_key="1001:2002" recipient="1001" '
                    "reply_chars=40 reply_bytes=40"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 8


def test_run_probe_expect_reply_json_field_passes_with_matching_event_summary(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("telegram.command.session_budget_json.replied",),
        expect_reply_json_fields=(("json_kind", "session_budget"),),
    )

    update_id = 1_700_000_004_680
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] /session budget json"'],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="1001:2002" recipient="1001" '
                    "json_kind=session_context json_available= json_status= "
                    "json_found= json_decision= json_keys=7"
                ],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    "telegram command reply json summary "
                    'event="telegram.command.session_budget_json.replied" '
                    'session_key="1001:2002" recipient="1001" '
                    "json_kind=session_budget json_available=false json_status=not_found "
                    "json_found= json_decision= json_keys=4"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_waits_for_expect_event_after_bot_reply(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        max_wait_secs=5,
        expect_events=("telegram.command.session_status_json.replied",),
    )

    update_id = 1_700_000_004_700
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.1))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f'2026-02-18 INFO ← User: "[{trace_id}] hello"'],
                ['2026-02-18 INFO → Bot: "done"'],
                [
                    "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
                    'event = "telegram.command.session_status_json.replied" '
                    "telegram command reply sent"
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_times_out_without_inbound_marker(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(module, log_file, max_wait_secs=1)

    update_id = 1_700_000_005_000
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.2))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(module, "read_new_lines", _sequence_reader([[]]))

    assert module.run_probe(cfg) == 2


def test_run_probe_fails_when_dispatch_session_key_mismatches_target(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(module, log_file, max_wait_secs=5)

    update_id = 1_700_000_005_500
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.2))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    f'session_key="1001:9999" content_preview=[{trace_id}] hello'
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 10


def test_run_probe_non_trace_ignores_unrelated_dispatch_session_mismatch(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(
        module,
        log_file,
        prompt="/session json",
        max_wait_secs=5,
        expect_events=("telegram.command.session_status_json.replied",),
    )

    update_id = 1_700_000_005_510
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.2))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [f"2026-02-18 INFO Webhook received Telegram update update_id=Some({update_id})"],
                [
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    'session_key="1001:42:2002" content_preview=/session json',
                    "2026-02-18 INFO telegram command reply sent "
                    'event="telegram.command.session_status_json.replied" '
                    'session_key="1001:2002" recipient="1001" reply_chars=10 reply_bytes=10',
                    '2026-02-18 INFO → Bot: "done"',
                ],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_accepts_dispatch_session_key_with_zero_thread_alias(
    tmp_path, monkeypatch
) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(module, log_file, max_wait_secs=5)

    update_id = 1_700_000_005_520
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.2))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    f'2026-02-18 INFO ← User: "[{trace_id}] hello"',
                    "2026-02-18 INFO Parsed message, forwarding to agent "
                    f'session_key="1001:0:2002" content_preview=[{trace_id}] hello',
                ],
                ['2026-02-18 INFO → Bot: "done"'],
            ]
        ),
    )

    assert module.run_probe(cfg) == 0


def test_run_probe_ignores_stale_bot_before_dispatch_marker(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text("", encoding="utf-8")
    cfg = _make_config(module, log_file, max_wait_secs=1)

    update_id = 1_700_000_006_000
    trace_id = f"bbx-{update_id}-42"
    monkeypatch.setattr(module.time, "time", lambda: update_id / 1000)
    monkeypatch.setattr(module.os, "getpid", lambda: 42)
    monkeypatch.setattr(module.time, "monotonic", _fake_clock(step=0.2))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module, "post_webhook_update", lambda *_: (200, "ok"))
    monkeypatch.setattr(
        module,
        "read_new_lines",
        _sequence_reader(
            [
                [
                    f"2026-02-18 INFO Parsed message, forwarding to agent content_preview=[{trace_id}] /x"
                ],
                ['2026-02-18 INFO → Bot: "previous command reply"'],
                [],
            ]
        ),
    )

    assert module.run_probe(cfg) == 9
