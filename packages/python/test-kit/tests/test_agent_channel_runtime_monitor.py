"""Tests for scripts/channel/agent_channel_runtime_monitor.py."""

from __future__ import annotations

import json
import importlib.util
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

from omni.foundation.runtime.gitops import get_project_root


def _load_monitor_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "agent_channel_runtime_monitor.py"
    spec = importlib.util.spec_from_file_location("omni_agent_channel_runtime_monitor", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_exit_code_maps_signals() -> None:
    module = _load_monitor_module()
    assert module.normalize_exit_code(0) == 0
    assert module.normalize_exit_code(3) == 3
    assert module.normalize_exit_code(-15) == 143


def test_classify_exit_for_success_and_signal() -> None:
    module = _load_monitor_module()
    ok = module.classify_exit(0)
    assert ok["kind"] == "ok"
    assert ok["exit_code"] == 0

    sig = module.classify_exit(-15)
    assert sig["kind"] == "signal"
    assert sig["exit_code"] == 143
    assert sig["signal"] == 15
    assert sig["signal_name"] == "SIGTERM"


def test_extract_event_token_parses_structured_log() -> None:
    module = _load_monitor_module()
    line = (
        "2026-02-18 INFO omni_agent::channels::telegram::runtime::jobs: "
        'telegram command reply sent event="telegram.command.session_reset.replied"'
    )
    assert module.extract_event_token(line) == "telegram.command.session_reset.replied"


def test_run_monitored_process_writes_success_report(tmp_path: Path) -> None:
    module = _load_monitor_module()
    log_file = tmp_path / "runtime.log"
    report_file = tmp_path / "runtime.exit.json"
    report_jsonl = tmp_path / "runtime.exit.jsonl"

    exit_code = module.run_monitored_process(
        command=[sys.executable, "-c", "print('event=\"demo.event\"'); print('ok')"],
        log_file=log_file,
        report_file=report_file,
        report_jsonl=report_jsonl,
        tail_lines=5,
    )
    assert exit_code == 0
    assert log_file.exists()
    assert report_file.exists()
    assert report_jsonl.exists()

    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["exit"]["kind"] == "ok"
    assert report["exit"]["exit_code"] == 0
    assert report["stats"]["total_lines"] >= 2
    assert report["events"]["last_event"] == "demo.event"


def test_run_monitored_process_writes_nonzero_report(tmp_path: Path) -> None:
    module = _load_monitor_module()
    log_file = tmp_path / "runtime.log"
    report_file = tmp_path / "runtime.exit.json"

    exit_code = module.run_monitored_process(
        command=[sys.executable, "-c", "print('error: boom'); raise SystemExit(7)"],
        log_file=log_file,
        report_file=report_file,
        report_jsonl=None,
        tail_lines=5,
    )
    assert exit_code == 7

    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["exit"]["kind"] == "nonzero"
    assert report["exit"]["exit_code"] == 7
    assert report["stats"]["error_lines"] >= 1
    assert "error: boom" in report["stats"]["first_error_line"]


def test_runtime_monitor_writes_report_when_monitor_gets_sigterm(tmp_path: Path) -> None:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "agent_channel_runtime_monitor.py"
    log_file = tmp_path / "runtime.log"
    report_file = tmp_path / "runtime.exit.json"

    monitor = subprocess.Popen(
        [
            sys.executable,
            str(script_path),
            "--log-file",
            str(log_file),
            "--report-file",
            str(report_file),
            "--",
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(60)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.6)
        monitor.send_signal(signal.SIGTERM)
        stdout, stderr = monitor.communicate(timeout=20)
    except Exception:
        monitor.kill()
        monitor.wait(timeout=5)
        raise

    assert monitor.returncode == 143, (stdout, stderr)
    assert report_file.exists()
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["exit"]["kind"] == "signal"
    assert report["exit"]["exit_code"] == 143
    assert report["exit"]["signal_name"] == "SIGTERM"
    assert report["termination"]["requested_signal_name"] == "SIGTERM"
