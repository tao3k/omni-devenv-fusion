"""Tests for scripts/channel/test_omni_agent_dedup_events.py."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_dedup_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_dedup_events.py"
    spec = importlib.util.spec_from_file_location("omni_agent_channel_dedup_probe", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "max_wait": 25,
        "webhook_url": "http://127.0.0.1:8081/telegram/webhook",
        "log_file": ".run/logs/omni-agent-webhook.log",
        "chat_id": 1001,
        "user_id": 2002,
        "username": "tao3k",
        "thread_id": None,
        "secret_token": None,
        "text": "/session json",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_build_config_uses_resolver_secret_when_cli_secret_missing(monkeypatch) -> None:
    module = _load_dedup_module()
    monkeypatch.setattr(module, "telegram_webhook_secret_token", lambda: "resolver-secret")
    monkeypatch.setattr(module, "username_from_settings", lambda: None)
    monkeypatch.setattr(module, "username_from_runtime_log", lambda *_: "tao3k")

    cfg = module.build_config(_make_args(secret_token=None, username=None))
    assert cfg.secret_token == "resolver-secret"


def test_build_config_prefers_explicit_secret_over_resolver(monkeypatch) -> None:
    module = _load_dedup_module()
    monkeypatch.setattr(module, "telegram_webhook_secret_token", lambda: "resolver-secret")
    monkeypatch.setattr(module, "username_from_settings", lambda: None)
    monkeypatch.setattr(module, "username_from_runtime_log", lambda *_: "tao3k")

    cfg = module.build_config(_make_args(secret_token="explicit-secret", username=None))
    assert cfg.secret_token == "explicit-secret"
