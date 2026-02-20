"""Tests for scripts/channel/test_omni_agent_concurrent_sessions.py."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from typing import TYPE_CHECKING

import pytest

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_probe_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_concurrent_sessions.py"
    spec = importlib.util.spec_from_file_location("omni_agent_concurrent_probe", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "max_wait": 30,
        "webhook_url": "http://127.0.0.1:8081/telegram/webhook",
        "log_file": ".run/logs/omni-agent-webhook.log",
        "chat_id": None,
        "chat_b": None,
        "user_a": None,
        "user_b": None,
        "username": None,
        "thread_a": None,
        "thread_b": None,
        "secret_token": None,
        "prompt": "/session json",
        "forbid_log_regex": ["tools/call: Mcp error"],
        "allow_send_failure": False,
        "session_partition": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_expected_session_key_formats_with_thread() -> None:
    module = _load_probe_module()
    assert module.expected_session_key(130, 7, None) == "130:7"
    assert module.expected_session_key(-1001, 7, 42) == "-1001:42:7"


def test_expected_session_keys_include_zero_thread_alias_for_none_thread() -> None:
    module = _load_probe_module()
    assert module.expected_session_keys(130, 7, None) == ("130:7", "130:0:7")
    assert module.expected_session_keys(-1001, 7, 42) == ("-1001:42:7",)


def test_build_config_infers_chat_user_from_log(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=1304799691:1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(tmp_path / "missing.env"))

    args = _make_args(log_file=str(log_file))
    cfg = module.build_config(args)
    assert cfg.chat_id == 1304799691
    assert cfg.chat_b == 1304799691
    assert cfg.user_a == 1304799691
    assert cfg.user_b == 1304799692


def test_build_config_prefers_group_profile_file(tmp_path, monkeypatch) -> None:
    module = _load_probe_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_USER_ID=1304799691\n"
        "OMNI_TEST_USER_B=1304799692\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))

    args = _make_args(log_file=str(tmp_path / "missing.log"))
    cfg = module.build_config(args)
    assert cfg.chat_id == -5101776367
    assert cfg.chat_b == -5020317863
    assert cfg.user_a == 1304799691
    assert cfg.user_b == 1304799692


def test_build_config_allows_same_user_when_chat_differs(tmp_path) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=1304799691:1304799691\n",
        encoding="utf-8",
    )

    args = _make_args(
        log_file=str(log_file),
        chat_id=1304799691,
        chat_b=1304799701,
        user_a=1304799691,
        user_b=1304799691,
    )
    cfg = module.build_config(args)
    assert cfg.chat_id == 1304799691
    assert cfg.chat_b == 1304799701
    assert cfg.user_a == cfg.user_b == 1304799691


def test_build_config_rejects_identical_session_target(tmp_path) -> None:
    module = _load_probe_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=1304799691:1304799691\n",
        encoding="utf-8",
    )

    args = _make_args(
        log_file=str(log_file),
        chat_id=1304799691,
        chat_b=1304799691,
        user_a=1304799691,
        user_b=1304799691,
    )
    with pytest.raises(ValueError, match="same session_key"):
        module.build_config(args)


def test_build_config_allows_filtering_send_failure_regex() -> None:
    module = _load_probe_module()
    args = _make_args(
        chat_id=130,
        user_a=1,
        user_b=2,
        forbid_log_regex=["tools/call: Mcp error", "Telegram sendMessage failed"],
        allow_send_failure=True,
    )
    cfg = module.build_config(args)
    assert "tools/call: Mcp error" in cfg.forbid_log_regexes
    assert "Telegram sendMessage failed" not in cfg.forbid_log_regexes
    assert cfg.allow_send_failure is True


def test_build_config_uses_resolver_secret_when_missing(monkeypatch) -> None:
    module = _load_probe_module()
    monkeypatch.setattr(module, "group_profile_int", lambda *_: None)
    monkeypatch.setattr(module, "session_ids_from_runtime_log", lambda *_: (130, 1, None))
    monkeypatch.setattr(module, "username_from_settings", lambda: "tao3k")
    monkeypatch.setattr(module, "telegram_webhook_secret_token", lambda: "resolver-secret")

    cfg = module.build_config(_make_args(chat_b=131))
    assert cfg.secret_token == "resolver-secret"


def test_collect_observation_counts_expected_events() -> None:
    module = _load_probe_module()
    lines = [
        'DEBUG event="telegram.dedup.update_accepted" update_id=101',
        'DEBUG event="telegram.dedup.update_accepted" update_id=202',
        "INFO Parsed message, forwarding to agent session_key=130:1",
        "INFO Parsed message, forwarding to agent session_key=130:2",
        (
            'INFO telegram command reply sent event="telegram.command.session_status_json.replied" '
            'session_key="130:1" recipient="130"'
        ),
        (
            'INFO telegram command reply sent event="telegram.command.session_status_json.replied" '
            'session_key="130:2" recipient="130"'
        ),
    ]

    obs = module.collect_observation(
        lines,
        update_a=101,
        update_b=202,
        key_a_candidates=("130:1",),
        key_b_candidates=("130:2",),
        forbid_log_regexes=("tools/call: Mcp error",),
    )
    assert obs.accepted_a == 1
    assert obs.accepted_b == 1
    assert obs.parsed_a == 1
    assert obs.parsed_b == 1
    assert obs.replied_a == 1
    assert obs.replied_b == 1
    assert obs.duplicate_a == 0
    assert obs.duplicate_b == 0
    assert obs.forbidden_hits == ()


def test_collect_observation_matches_zero_thread_alias() -> None:
    module = _load_probe_module()
    lines = [
        'DEBUG event="telegram.dedup.update_accepted" update_id=101',
        'DEBUG event="telegram.dedup.update_accepted" update_id=202',
        "INFO Parsed message, forwarding to agent session_key=130:0:1",
        "INFO Parsed message, forwarding to agent session_key=130:0:2",
        (
            'INFO telegram command reply sent event="telegram.command.session_status_json.replied" '
            'session_key="130:0:1" recipient="130"'
        ),
        (
            'INFO telegram command reply sent event="telegram.command.session_status_json.replied" '
            'session_key="130:0:2" recipient="130"'
        ),
    ]

    obs = module.collect_observation(
        lines,
        update_a=101,
        update_b=202,
        key_a_candidates=("130:1", "130:0:1"),
        key_b_candidates=("130:2", "130:0:2"),
        forbid_log_regexes=(),
    )
    assert obs.parsed_a == 1
    assert obs.parsed_b == 1
    assert obs.replied_a == 1
    assert obs.replied_b == 1
