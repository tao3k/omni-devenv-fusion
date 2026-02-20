"""Tests for scripts/channel/test_omni_agent_memory_suite.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_memory_suite_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_memory_suite.py"
    spec = importlib.util.spec_from_file_location("omni_agent_memory_suite", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blackbox_cases_quick_mode_has_command_probes() -> None:
    module = _load_memory_suite_module()
    cases = module.blackbox_cases(require_live_turn=False)
    assert len(cases) == 3
    assert cases[0].prompt == "/session memory json"
    assert cases[0].expected_event == "telegram.command.session_memory_json.replied"
    assert cases[1].prompt == "/session feedback up json"
    assert cases[2].prompt == "/session feedback down json"


def test_blackbox_cases_live_turn_adds_memory_recall_probe() -> None:
    module = _load_memory_suite_module()
    cases = module.blackbox_cases(require_live_turn=True)
    assert len(cases) == 4
    live_case = cases[-1]
    assert live_case.expected_event == "agent.memory.recall.planned"
    assert "--expect-log-regex" in live_case.extra_args


def test_parse_args_accepts_skip_blackbox_flag(monkeypatch) -> None:
    module = _load_memory_suite_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_memory_suite.py",
            "--suite",
            "full",
            "--skip-blackbox",
        ],
    )
    args = module.parse_args()
    assert args.suite == "full"
    assert args.skip_blackbox is True
    assert args.skip_rust is False


def test_resolve_runtime_partition_mode_prefers_override(monkeypatch) -> None:
    module = _load_memory_suite_module()
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat-thread-user")
    monkeypatch.setattr(module, "session_partition_mode_from_runtime_log", lambda _path: "chat")
    monkeypatch.setattr(module, "telegram_session_partition_mode", lambda: "chat_user")
    assert module.resolve_runtime_partition_mode() == "chat_thread_user"


def test_run_blackbox_suite_passes_resolved_session_partition(monkeypatch, tmp_path: Path) -> None:
    module = _load_memory_suite_module()
    script_dir = tmp_path
    (script_dir / "agent_channel_blackbox.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )

    observed_commands: list[list[str]] = []

    def _capture(cmd: list[str], *, title: str, env=None) -> None:
        del title, env
        observed_commands.append(cmd)

    monkeypatch.setattr(module, "resolve_runtime_partition_mode", lambda: "chat")
    monkeypatch.setattr(module, "run_command", _capture)
    monkeypatch.delenv("OMNI_BLACKBOX_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "1304799691")

    module.run_blackbox_suite(
        script_dir=script_dir,
        max_wait=25,
        max_idle_secs=25,
        username="ci-user",
        require_live_turn=False,
    )

    assert observed_commands, "expected at least one black-box command"
    for cmd in observed_commands:
        assert "--session-partition" in cmd
        idx = cmd.index("--session-partition")
        assert cmd[idx + 1] == "chat"
