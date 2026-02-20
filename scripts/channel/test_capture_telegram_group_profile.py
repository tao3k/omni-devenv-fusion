#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_log(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_capture(
    log_file: Path, output_json: Path, output_env: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/channel/capture_telegram_group_profile.py",
            "--titles",
            "Test1,Test2,Test3",
            "--log-file",
            str(log_file),
            "--output-json",
            str(output_json),
            "--output-env",
            str(output_env),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_capture_group_profile_success(tmp_path: Path) -> None:
    log_file = tmp_path / "webhook.log"
    output_json = tmp_path / "groups.json"
    output_env = tmp_path / "groups.env"

    _write_log(
        log_file,
        [
            "2026-02-20T00:00:01Z INFO omni_agent::channels::telegram::runtime::webhook: "
            "Parsed message, forwarding to agent session_key=-5101776367:1304799691 "
            'chat_id=Some(-5101776367) chat_title=Some("Test1") chat_type=Some("group") '
            "message_thread_id=None content_preview=/help",
            "2026-02-20T00:00:02Z INFO omni_agent::channels::telegram::runtime::webhook: "
            "Parsed message, forwarding to agent session_key=-5020317863:1304799691 "
            'chat_id=Some(-5020317863) chat_title=Some("Test2") chat_type=Some("group") '
            "message_thread_id=None content_preview=/help",
            "2026-02-20T00:00:03Z INFO omni_agent::channels::telegram::runtime::webhook: "
            "Parsed message, forwarding to agent session_key=-5292802281:1304799691 "
            'chat_id=Some(-5292802281) chat_title=Some("Test3") chat_type=Some("group") '
            "message_thread_id=None content_preview=/help",
        ],
    )

    completed = _run_capture(log_file=log_file, output_json=output_json, output_env=output_env)
    assert completed.returncode == 0, completed.stderr
    assert output_json.exists()
    assert output_env.exists()

    profile = json.loads(output_json.read_text(encoding="utf-8"))
    assert profile["present_titles"] == ["Test1", "Test2", "Test3"]
    assert profile["sessions"]["a"]["chat_id"] == -5101776367
    assert profile["sessions"]["b"]["chat_id"] == -5020317863
    assert profile["sessions"]["c"]["chat_id"] == -5292802281

    env_text = output_env.read_text(encoding="utf-8")
    assert "OMNI_TEST_CHAT_ID=-5101776367" in env_text
    assert "OMNI_TEST_CHAT_B=-5020317863" in env_text
    assert "OMNI_TEST_CHAT_C=-5292802281" in env_text
    assert "OMNI_TEST_USER_ID=1304799691" in env_text
    assert "OMNI_TEST_USER_B=1304799692" in env_text
    assert "OMNI_TEST_USER_C=1304799693" in env_text


def test_capture_group_profile_missing_title_fails(tmp_path: Path) -> None:
    log_file = tmp_path / "webhook.log"
    output_json = tmp_path / "groups.json"
    output_env = tmp_path / "groups.env"

    _write_log(
        log_file,
        [
            "2026-02-20T00:00:01Z INFO omni_agent::channels::telegram::runtime::webhook: "
            "Parsed message, forwarding to agent session_key=-5101776367:1304799691 "
            'chat_id=Some(-5101776367) chat_title=Some("Test1") chat_type=Some("group") '
            "message_thread_id=None content_preview=/help",
            "2026-02-20T00:00:02Z INFO omni_agent::channels::telegram::runtime::webhook: "
            "Parsed message, forwarding to agent session_key=-5020317863:1304799691 "
            'chat_id=Some(-5020317863) chat_title=Some("Test2") chat_type=Some("group") '
            "message_thread_id=None content_preview=/help",
        ],
    )

    completed = _run_capture(log_file=log_file, output_json=output_json, output_env=output_env)
    assert completed.returncode != 0
    assert "missing group titles in log: Test3" in (completed.stderr + completed.stdout)
