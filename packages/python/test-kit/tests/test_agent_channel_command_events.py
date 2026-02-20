"""Tests for scripts/channel/test_omni_agent_command_events.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _load_command_events_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_command_events.py"
    spec = importlib.util.spec_from_file_location("omni_agent_command_events", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_allow_chat_ids_uses_group_profile(tmp_path: Path, monkeypatch) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.delenv("OMNI_BLACKBOX_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("OMNI_TEST_CHAT_ID", raising=False)

    allow = module.resolve_allow_chat_ids(())
    assert allow == ("-5101776367", "-5020317863", "-5292802281")


def test_resolve_group_chat_id_prefers_profile(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text("OMNI_TEST_CHAT_ID=-5101776367\n", encoding="utf-8")
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.delenv("OMNI_TEST_GROUP_CHAT_ID", raising=False)

    resolved = module.resolve_group_chat_id(explicit_group_chat_id=None, allow_chat_ids=())
    assert resolved == -5101776367


def test_infer_group_thread_id_from_runtime_log(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    log_file = tmp_path / "agent.log"
    log_file.write_text(
        "2026-02-20 INFO Parsed message, forwarding to agent "
        "session_key=-5101776367:42:1304799691 "
        "chat_id=Some(-5101776367) message_thread_id=Some(42) content_preview=/session json\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_CHANNEL_LOG_FILE", str(log_file))

    assert module.infer_group_thread_id_from_runtime_log(-5101776367) == 42


def test_resolve_admin_matrix_chat_ids_merges_and_dedups(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))

    ids = module.resolve_admin_matrix_chat_ids(
        explicit_matrix_chat_ids=(-5101776367, -6000000001),
        group_chat_id=-5020317863,
        allow_chat_ids=("-5292802281", "1304799691"),
    )
    assert ids == (-5101776367, -6000000001, -5020317863, -5292802281)


def test_main_admin_suite_uses_profile_group_by_default(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\nOMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("OMNI_TEST_GROUP_CHAT_ID", raising=False)

    observed_chat_ids: list[int] = []

    def _fake_run_case(**kwargs):
        case = kwargs["case"]
        if case.chat_id is not None:
            observed_chat_ids.append(case.chat_id)
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
        ],
    )
    assert module.main() == 0
    assert observed_chat_ids == [-5101776367, -5101776367, -5101776367]


def test_main_admin_suite_infers_group_thread_for_chat_thread_user(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\nOMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    runtime_log = tmp_path / "runtime.log"
    runtime_log.write_text(
        "2026-02-20 INFO Parsed message, forwarding to agent "
        "session_key=-5101776367:42:1304799691 "
        "chat_id=Some(-5101776367) message_thread_id=Some(42) content_preview=/session admin add\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("OMNI_CHANNEL_LOG_FILE", str(runtime_log))
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_thread_user")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("OMNI_TEST_GROUP_CHAT_ID", raising=False)
    monkeypatch.delenv("OMNI_TEST_GROUP_THREAD_ID", raising=False)

    observed_threads: list[int | None] = []

    def _fake_run_case(**kwargs):
        case = kwargs["case"]
        observed_threads.append(case.thread_id)
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
        ],
    )
    assert module.main() == 0
    assert observed_threads == [42, 42, 42]


def test_main_admin_matrix_runs_all_profile_groups(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n"
        "OMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("OMNI_TEST_GROUP_CHAT_ID", raising=False)

    observed_chat_ids: list[int] = []

    def _fake_run_case(**kwargs):
        case = kwargs["case"]
        if case.chat_id is not None:
            observed_chat_ids.append(case.chat_id)
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
            "--admin-matrix",
        ],
    )
    assert module.main() == 0
    assert observed_chat_ids == [
        -5101776367,
        -5101776367,
        -5101776367,
        -5020317863,
        -5020317863,
        -5020317863,
        -5292802281,
        -5292802281,
        -5292802281,
    ]


def test_main_uses_secret_fallback_from_resolver(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\nOMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(module, "telegram_webhook_secret_token", lambda: "fallback-secret")

    observed_secret_tokens: list[str] = []

    def _fake_run_case(**kwargs):
        observed_secret_tokens.append(kwargs["secret_token"])
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
        ],
    )
    assert module.main() == 0
    assert observed_secret_tokens == ["fallback-secret", "fallback-secret", "fallback-secret"]


def test_run_case_with_retry_retries_transient_failures(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    case = module.ProbeCase(
        case_id="session_admin_list_json",
        prompt="/session admin list json",
        event_name="telegram.command.session_admin_json.replied",
        suites=("admin",),
        chat_id=-5101776367,
    )
    statuses = [3, 7, 0]
    calls: list[int] = []
    sleep_calls: list[float] = []

    def _fake_run_case(**kwargs):
        calls.append(1)
        return statuses[len(calls) - 1]

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    status = module.run_case_with_retry(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        case=case,
        username="",
        allow_chat_ids=("-5101776367",),
        max_wait=25,
        max_idle_secs=25,
        secret_token="",
        retries=3,
        backoff_secs=1.5,
    )
    assert status == 0
    assert len(calls) == 3
    assert sleep_calls == [1.5, 3.0]


def test_run_case_with_retry_retries_dedup_duplicate_failure(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    case = module.ProbeCase(
        case_id="session_admin_list_json",
        prompt="/session admin list json",
        event_name="telegram.command.session_admin_json.replied",
        suites=("admin",),
        chat_id=-5101776367,
    )
    statuses = [4, 0]
    calls: list[int] = []
    sleep_calls: list[float] = []

    def _fake_run_case(**kwargs):
        calls.append(1)
        return statuses[len(calls) - 1]

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    status = module.run_case_with_retry(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        case=case,
        username="",
        allow_chat_ids=("-5101776367",),
        max_wait=25,
        max_idle_secs=25,
        secret_token="",
        retries=2,
        backoff_secs=1.0,
    )
    assert status == 0
    assert len(calls) == 2
    assert sleep_calls == [1.0]


def test_apply_runtime_partition_defaults_sets_thread_zero_for_chat_thread_user() -> None:
    module = _load_command_events_module()
    case = module.ProbeCase(
        case_id="session_status_json",
        prompt="/session json",
        event_name="telegram.command.session_status_json.replied",
        suites=("core",),
        thread_id=None,
    )

    updated = module.apply_runtime_partition_defaults(case, "chat_thread_user")
    assert updated.thread_id == 0


def test_run_case_with_retry_applies_partition_mode_override(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    case = module.ProbeCase(
        case_id="session_status_json",
        prompt="/session json",
        event_name="telegram.command.session_status_json.replied",
        suites=("core",),
    )
    observed_thread_ids: list[int | None] = []

    def _fake_run_case(**kwargs):
        observed_thread_ids.append(kwargs["case"].thread_id)
        return 0

    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_thread_user")
    monkeypatch.setattr(module, "run_case", _fake_run_case)

    status = module.run_case_with_retry(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        case=case,
        username="",
        allow_chat_ids=("-5101776367",),
        max_wait=25,
        max_idle_secs=25,
        secret_token="",
        retries=0,
        backoff_secs=0.0,
    )
    assert status == 0
    assert observed_thread_ids == [0]


def test_run_case_with_retry_does_not_retry_non_transient_failure(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_command_events_module()
    case = module.ProbeCase(
        case_id="session_admin_clear",
        prompt="/session admin clear",
        event_name="telegram.command.session_admin.replied",
        suites=("admin",),
        chat_id=-5101776367,
    )
    calls: list[int] = []
    sleep_calls: list[float] = []

    def _fake_run_case(**kwargs):
        calls.append(1)
        return 5

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    status = module.run_case_with_retry(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        case=case,
        username="",
        allow_chat_ids=("-5101776367",),
        max_wait=25,
        max_idle_secs=25,
        secret_token="",
        retries=4,
        backoff_secs=2.0,
    )
    assert status == 5
    assert len(calls) == 1
    assert sleep_calls == []


def test_build_cases_admin_cases_propagate_group_thread_id() -> None:
    module = _load_command_events_module()
    cases = module.build_cases(
        admin_user_id=1304799691,
        group_chat_id=-5101776367,
        group_thread_id=42,
    )
    by_case_id = {case.case_id: case for case in cases}
    for case_id in ("session_admin_add", "session_admin_list_json", "session_admin_clear"):
        case = by_case_id[case_id]
        assert case.chat_id == -5101776367
        assert case.thread_id == 42


def test_build_admin_list_isolation_case_includes_thread_and_count() -> None:
    module = _load_command_events_module()
    case = module.build_admin_list_isolation_case(
        chat_id=-5101776367,
        admin_user_id=1304799691,
        thread_id=99,
        expected_override_count=1,
    )
    assert case.thread_id == 99
    assert "json_override_admin_count=1" in case.extra_args


def test_resolve_topic_thread_pair_defaults_secondary() -> None:
    module = _load_command_events_module()
    pair = module.resolve_topic_thread_pair(primary_thread_id=42, secondary_thread_id=None)
    assert pair == (42, 43)


def test_resolve_topic_thread_pair_requires_distinct_threads() -> None:
    module = _load_command_events_module()
    try:
        module.resolve_topic_thread_pair(primary_thread_id=42, secondary_thread_id=42)
        raise AssertionError("expected duplicate thread id validation to fail")
    except ValueError as error:
        assert "distinct thread ids" in str(error)


def test_build_admin_list_topic_isolation_case_includes_thread_and_count() -> None:
    module = _load_command_events_module()
    case = module.build_admin_list_topic_isolation_case(
        chat_id=-5101776367,
        admin_user_id=1304799691,
        thread_id=77,
        expected_override_count=0,
    )
    assert case.thread_id == 77
    assert "json_override_admin_count=0" in case.extra_args
    assert "topic_isolation" in case.case_id


def test_main_writes_structured_reports(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\nOMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    output_json = tmp_path / "report.json"
    output_markdown = tmp_path / "report.md"
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("OMNI_TEST_GROUP_CHAT_ID", raising=False)

    def _fake_run_case(**kwargs):
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )
    assert module.main() == 0
    assert output_json.exists()
    assert output_markdown.exists()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["failed"] == 0


def test_main_admin_matrix_isolation_report_preserves_thread_scope(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n"
        "OMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    output_json = tmp_path / "report.matrix.json"
    output_markdown = tmp_path / "report.matrix.md"
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")

    def _fake_run_case(**kwargs):
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
            "--admin-matrix",
            "--assert-admin-isolation",
            "--group-thread-id",
            "42",
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )
    assert module.main() == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["config"]["assert_admin_isolation"] is True
    assert payload["config"]["matrix_chat_ids"] == [-5101776367, -5020317863, -5292802281]
    assert payload["summary"]["total"] == 33
    for attempt in payload["attempts"]:
        if "session_admin" in str(attempt["case_id"]):
            assert attempt["thread_id"] == 42


def test_run_admin_isolation_assertions_emits_count_checks(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    attempted_case_ids: list[str] = []
    attempted_case_extra_args: list[tuple[str, ...]] = []

    def _fake_run_case(**kwargs):
        case = kwargs["case"]
        attempted_case_ids.append(case.case_id)
        attempted_case_extra_args.append(case.extra_args)
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)

    status = module.run_admin_isolation_assertions(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        matrix_chat_ids=(-5101776367, -5020317863),
        admin_user_id=1304799691,
        group_thread_id=None,
        username="",
        allow_chat_ids=("-5101776367", "-5020317863"),
        max_wait=25,
        max_idle_secs=25,
        secret_token="test-secret",
        retries=0,
        backoff_secs=0.0,
        attempt_records=[],
        runtime_partition_mode=None,
    )
    assert status == 0
    isolation_cases = [case_id for case_id in attempted_case_ids if "isolation_" in case_id]
    assert isolation_cases
    assert any(case_id.endswith("_1") for case_id in isolation_cases)
    assert any(case_id.endswith("_0") for case_id in isolation_cases)
    assert any(
        "json_override_admin_count=1" in extra_args or "json_override_admin_count=0" in extra_args
        for extra_args in attempted_case_extra_args
    )


def test_run_admin_topic_isolation_assertions_emits_cross_thread_count_checks(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_command_events_module()
    attempts: list[tuple[str, int | None, tuple[str, ...]]] = []

    def _fake_run_case(**kwargs):
        case = kwargs["case"]
        attempts.append((case.case_id, case.thread_id, case.extra_args))
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)

    status = module.run_admin_topic_isolation_assertions(
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        group_chat_id=-5101776367,
        admin_user_id=1304799691,
        thread_a=42,
        thread_b=43,
        username="",
        allow_chat_ids=("-5101776367",),
        max_wait=25,
        max_idle_secs=25,
        secret_token="test-secret",
        retries=0,
        backoff_secs=0.0,
        attempt_records=[],
        runtime_partition_mode=None,
    )
    assert status == 0
    thread_42 = [record for record in attempts if record[1] == 42]
    thread_43 = [record for record in attempts if record[1] == 43]
    assert thread_42 and thread_43
    assert any("json_override_admin_count=1" in record[2] for record in thread_42)
    assert any("json_override_admin_count=1" in record[2] for record in thread_43)
    assert any("json_override_admin_count=0" in record[2] for record in thread_42)
    assert any("json_override_admin_count=0" in record[2] for record in thread_43)


def test_main_topic_isolation_report_uses_thread_pair(monkeypatch, tmp_path: Path) -> None:
    module = _load_command_events_module()
    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\nOMNI_TEST_USER_ID=1304799691\n",
        encoding="utf-8",
    )
    output_json = tmp_path / "report.topic.json"
    output_markdown = tmp_path / "report.topic.md"
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")

    def _fake_run_case(**kwargs):
        return 0

    monkeypatch.setattr(module, "run_case", _fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_command_events.py",
            "--suite",
            "admin",
            "--assert-admin-topic-isolation",
            "--group-thread-id",
            "42",
            "--group-thread-id-b",
            "43",
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )
    assert module.main() == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["config"]["assert_admin_topic_isolation"] is True
    assert payload["config"]["group_thread_id"] == 42
    assert payload["config"]["group_thread_id_b"] == 43
    assert payload["summary"]["total"] == 17
    assert any(attempt["thread_id"] == 42 for attempt in payload["attempts"])
    assert any(attempt["thread_id"] == 43 for attempt in payload["attempts"])
