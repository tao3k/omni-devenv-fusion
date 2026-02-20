"""Tests for scripts/channel/test_omni_agent_complex_scenarios.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _load_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_complex_scenarios.py"
    spec = importlib.util.spec_from_file_location("omni_agent_complex_scenarios", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_scenarios_from_default_fixture_has_complexity_requirements() -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )
    scenarios = module.load_scenarios(fixture_path)
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.scenario_id == "cross_group_control_plane_stress"
    assert len(scenario.steps) >= 18
    assert scenario.required_complexity is not None
    assert scenario.required_complexity.critical_path_len >= 8


def test_expected_session_log_regex_supports_zero_thread_alias() -> None:
    module = _load_module()
    pattern = module.expected_session_log_regex(-5101776367, 1304799691, None)
    regex = module.re.compile(pattern)
    assert regex.search('session_key="-5101776367:1304799691"')
    assert regex.search('session_key="-5101776367:0:1304799691"')


def test_expected_session_keys_respects_partition_mode() -> None:
    module = _load_module()
    assert module.expected_session_keys(-5101776367, 1304799691, None, "chat") == ("-5101776367",)
    assert module.expected_session_keys(-5101776367, 1304799691, None, "chat_user") == (
        "-5101776367:1304799691",
    )
    assert module.expected_session_keys(-5101776367, 1304799691, None, "user") == ("1304799691",)
    assert module.expected_session_keys(-5101776367, 1304799691, None, "chat_thread_user") == (
        "-5101776367:0:1304799691",
        "-5101776367:1304799691",
    )
    assert module.expected_session_keys(-5101776367, 1304799691, 42, "chat_thread_user") == (
        "-5101776367:42:1304799691",
    )


def test_resolve_runtime_partition_mode_prefers_override(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_thread_user")
    monkeypatch.setattr(
        module, "session_partition_mode_from_runtime_log", lambda _log_file: "chat_user"
    )
    monkeypatch.setattr(module, "telegram_session_partition_mode", lambda: "chat_user")

    assert module.resolve_runtime_partition_mode(tmp_path / "runtime.log") == "chat_thread_user"


def test_compute_complexity_profile_counts_parallel_waves() -> None:
    module = _load_module()
    scenario = module.ScenarioSpec(
        scenario_id="synthetic",
        description="synthetic scenario",
        steps=(
            module.ScenarioStepSpec(
                step_id="s1",
                session_alias="a",
                prompt="/reset",
                expect_event="telegram.command.session_reset.replied",
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=(),
                depends_on=(),
                order=0,
            ),
            module.ScenarioStepSpec(
                step_id="s2",
                session_alias="b",
                prompt="/reset",
                expect_event="telegram.command.session_reset.replied",
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=(),
                depends_on=(),
                order=1,
            ),
            module.ScenarioStepSpec(
                step_id="s3",
                session_alias="a",
                prompt="/resume status",
                expect_event="telegram.command.session_resume_status.replied",
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=(),
                depends_on=("s1",),
                order=2,
            ),
            module.ScenarioStepSpec(
                step_id="s4",
                session_alias="b",
                prompt="/resume status",
                expect_event="telegram.command.session_resume_status.replied",
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=(),
                depends_on=("s1", "s2"),
                order=3,
            ),
            module.ScenarioStepSpec(
                step_id="s5",
                session_alias="c",
                prompt="/session json",
                expect_event="telegram.command.session_status_json.replied",
                expect_reply_json_fields=("json_kind=session_context",),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=(),
                depends_on=("s3", "s4"),
                order=4,
            ),
        ),
        required_complexity=None,
        required_quality=None,
    )

    profile = module.compute_complexity_profile(scenario)
    assert profile.step_count == 5
    assert profile.dependency_edges == 5
    assert profile.critical_path_len == 3
    assert profile.parallel_waves == 2
    assert profile.max_wave_width == 2


def test_load_scenarios_rejects_unknown_dependency(tmp_path: Path) -> None:
    module = _load_module()
    fixture = {
        "scenarios": [
            {
                "id": "bad",
                "steps": [
                    {
                        "id": "s1",
                        "session": "a",
                        "prompt": "/reset",
                        "depends_on": ["missing"],
                    }
                ],
            }
        ]
    }
    dataset = tmp_path / "bad.json"
    dataset.write_text(json.dumps(fixture), encoding="utf-8")

    try:
        module.load_scenarios(dataset)
    except ValueError as exc:
        assert "unknown dependencies" in str(exc)
        return

    raise AssertionError("expected ValueError for unknown dependency")


def test_merge_requirements_prefers_stricter_thresholds() -> None:
    module = _load_module()
    global_req = module.ComplexityRequirement(
        steps=14,
        dependency_edges=14,
        critical_path_len=6,
        parallel_waves=3,
    )
    scenario_req = module.ComplexityRequirement(
        steps=18,
        dependency_edges=10,
        critical_path_len=8,
        parallel_waves=4,
    )

    merged = module.merge_requirements(global_req, scenario_req)
    assert merged.steps == 18
    assert merged.dependency_edges == 14
    assert merged.critical_path_len == 8
    assert merged.parallel_waves == 4


def test_build_config_prefers_env_session_a_over_log_inference(monkeypatch) -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )

    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "-5101776367")
    monkeypatch.setenv("OMNI_TEST_USER_ID", "1304799692")
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_user")
    monkeypatch.delenv("OMNI_TEST_USER_B", raising=False)
    monkeypatch.delenv("OMNI_TEST_USER_C", raising=False)
    monkeypatch.setattr(
        module,
        "session_ids_from_runtime_log",
        lambda _log_file: (-1, -1, None),
    )
    monkeypatch.setattr(
        module,
        "allowed_users_from_settings",
        lambda: ["1304799691", "1304799692", "1304799693", "1304799694"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_complex_scenarios.py",
            "--dataset",
            str(fixture_path),
        ],
    )

    args = module.parse_args()
    cfg = module.build_config(args)

    assert cfg.sessions[0].chat_id == -5101776367
    assert cfg.sessions[0].user_id == 1304799692
    assert cfg.sessions[1].user_id == 1304799693
    assert cfg.sessions[2].user_id == 1304799694


def test_build_config_uses_resolver_secret_when_missing(monkeypatch) -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )

    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "-5101776367")
    monkeypatch.setenv("OMNI_TEST_USER_ID", "1304799691")
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_user")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(module, "allowed_users_from_settings", lambda: ["1304799691", "1304799692"])
    monkeypatch.setattr(module, "session_ids_from_runtime_log", lambda _log_file: (-1, -1, None))
    monkeypatch.setattr(module, "telegram_webhook_secret_token", lambda: "resolver-secret")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_complex_scenarios.py",
            "--dataset",
            str(fixture_path),
        ],
    )

    args = module.parse_args()
    cfg = module.build_config(args)
    assert cfg.secret_token == "resolver-secret"


def test_build_config_prefers_allowlisted_peers_over_unlisted_plus_two(monkeypatch) -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )

    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "-5101776367")
    monkeypatch.setenv("OMNI_TEST_USER_ID", "1304799693")
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_user")
    monkeypatch.delenv("OMNI_TEST_USER_B", raising=False)
    monkeypatch.delenv("OMNI_TEST_USER_C", raising=False)
    monkeypatch.setattr(
        module,
        "allowed_users_from_settings",
        lambda: ["1304799691", "1304799692", "1304799693", "1304799694"],
    )
    monkeypatch.setattr(
        module,
        "session_ids_from_runtime_log",
        lambda _log_file: (-1, -1, None),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_complex_scenarios.py",
            "--dataset",
            str(fixture_path),
        ],
    )

    args = module.parse_args()
    cfg = module.build_config(args)

    assert cfg.sessions[0].user_id == 1304799693
    assert cfg.sessions[1].user_id == 1304799694
    assert cfg.sessions[2].user_id in {1304799691, 1304799692}
    assert cfg.sessions[2].user_id != 1304799695


def test_build_config_defaults_thread_ids_for_chat_thread_user(monkeypatch) -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )

    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "-5101776367")
    monkeypatch.setenv("OMNI_TEST_USER_ID", "1304799691")
    monkeypatch.setenv("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "chat_thread_user")
    monkeypatch.delenv("OMNI_TEST_THREAD_ID", raising=False)
    monkeypatch.delenv("OMNI_TEST_THREAD_B", raising=False)
    monkeypatch.delenv("OMNI_TEST_THREAD_C", raising=False)
    monkeypatch.setattr(
        module, "allowed_users_from_settings", lambda: ["1304799691", "1304799692", "1304799693"]
    )
    monkeypatch.setattr(module, "session_ids_from_runtime_log", lambda _log_file: (-1, -1, None))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_omni_agent_complex_scenarios.py",
            "--dataset",
            str(fixture_path),
        ],
    )

    args = module.parse_args()
    cfg = module.build_config(args)

    assert cfg.runtime_partition_mode == "chat_thread_user"
    assert all(session.thread_id == 0 for session in cfg.sessions)


def test_quality_evaluation_uses_error_signal_and_correction_tags() -> None:
    module = _load_module()
    scenario = module.ScenarioSpec(
        scenario_id="quality",
        description="quality",
        steps=(
            module.ScenarioStepSpec(
                step_id="seed",
                session_alias="a",
                prompt="seed",
                expect_event=None,
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=("seed",),
                depends_on=(),
                order=0,
            ),
            module.ScenarioStepSpec(
                step_id="error_signal",
                session_alias="a",
                prompt="/session feedback down json",
                expect_event="telegram.command.session_feedback_json.replied",
                expect_reply_json_fields=("json_kind=session_feedback",),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=("error_signal",),
                depends_on=("seed",),
                order=1,
            ),
            module.ScenarioStepSpec(
                step_id="correction",
                session_alias="a",
                prompt="corrected answer",
                expect_event=None,
                expect_reply_json_fields=(),
                expect_log_regexes=(),
                expect_bot_regexes=(),
                forbid_log_regexes=(),
                allow_no_bot=False,
                tags=("correction_check",),
                depends_on=("error_signal",),
                order=2,
            ),
        ),
        required_complexity=None,
        required_quality=None,
    )
    results = (
        module.StepRunResult(
            scenario_id="quality",
            step_id="seed",
            session_alias="a",
            session_key="1:1",
            wave_index=0,
            depends_on=(),
            prompt="seed",
            event=None,
            command=(),
            returncode=0,
            duration_ms=10,
            passed=True,
            skipped=False,
            skip_reason=None,
            bot_excerpt="ACK",
            memory_planned_seen=True,
            memory_injected_seen=True,
            memory_skipped_seen=False,
            memory_feedback_updated_seen=True,
            memory_recall_credit_seen=True,
            memory_decay_seen=False,
            memory_recall_credit_count=1,
            memory_decay_count=0,
            memory_planned_bias=0.1,
            memory_decision="injected",
            mcp_last_event="mcp.pool.call.slow",
            mcp_waiting_seen=True,
            mcp_event_counts={"mcp.pool.call.waiting": 1, "mcp.pool.call.slow": 1},
            feedback_command_bias_before=None,
            feedback_command_bias_after=None,
            feedback_command_bias_delta=None,
            feedback_heuristic_bias_before=0.0,
            feedback_heuristic_bias_after=0.1,
            feedback_heuristic_bias_delta=0.1,
            stdout_tail="",
            stderr_tail="",
        ),
        module.StepRunResult(
            scenario_id="quality",
            step_id="error_signal",
            session_alias="a",
            session_key="1:1",
            wave_index=1,
            depends_on=("seed",),
            prompt="/session feedback down json",
            event="telegram.command.session_feedback_json.replied",
            command=(),
            returncode=0,
            duration_ms=10,
            passed=True,
            skipped=False,
            skip_reason=None,
            bot_excerpt="ACK",
            memory_planned_seen=False,
            memory_injected_seen=False,
            memory_skipped_seen=False,
            memory_feedback_updated_seen=True,
            memory_recall_credit_seen=False,
            memory_decay_seen=False,
            memory_recall_credit_count=0,
            memory_decay_count=0,
            memory_planned_bias=None,
            memory_decision=None,
            mcp_last_event="mcp.pool.connect.succeeded",
            mcp_waiting_seen=False,
            mcp_event_counts={"mcp.pool.connect.succeeded": 1},
            feedback_command_bias_before=0.2,
            feedback_command_bias_after=-0.1,
            feedback_command_bias_delta=-0.3,
            feedback_heuristic_bias_before=None,
            feedback_heuristic_bias_after=None,
            feedback_heuristic_bias_delta=None,
            stdout_tail="",
            stderr_tail="",
        ),
        module.StepRunResult(
            scenario_id="quality",
            step_id="correction",
            session_alias="a",
            session_key="1:1",
            wave_index=2,
            depends_on=("error_signal",),
            prompt="corrected answer",
            event=None,
            command=(),
            returncode=0,
            duration_ms=10,
            passed=True,
            skipped=False,
            skip_reason=None,
            bot_excerpt="VALKEY POSTGRES",
            memory_planned_seen=True,
            memory_injected_seen=True,
            memory_skipped_seen=False,
            memory_feedback_updated_seen=True,
            memory_recall_credit_seen=True,
            memory_decay_seen=True,
            memory_recall_credit_count=2,
            memory_decay_count=1,
            memory_planned_bias=-0.1,
            memory_decision="injected",
            mcp_last_event="mcp.pool.call.waiting",
            mcp_waiting_seen=True,
            mcp_event_counts={"mcp.pool.call.waiting": 2, "mcp.pool.call.slow": 1},
            feedback_command_bias_before=None,
            feedback_command_bias_after=None,
            feedback_command_bias_delta=None,
            feedback_heuristic_bias_before=-0.1,
            feedback_heuristic_bias_after=0.05,
            feedback_heuristic_bias_delta=0.15,
            stdout_tail="",
            stderr_tail="",
        ),
    )

    quality = module.compute_quality_profile(scenario, results)
    req = module.QualityRequirement(
        min_error_signals=1,
        min_negative_feedback_events=1,
        min_correction_checks=1,
        min_successful_corrections=1,
        min_planned_hits=2,
        min_natural_language_steps=2,
        min_recall_credit_events=1,
        min_decay_events=1,
    )
    passed, failures = module.evaluate_quality(quality, req)

    assert quality.error_signal_steps == 1
    assert quality.negative_feedback_events == 1
    assert quality.correction_check_steps == 1
    assert quality.successful_corrections == 1
    assert quality.recall_credit_events == 3
    assert quality.decay_events == 1
    assert passed is True
    assert failures == ()


def test_select_scenarios_returns_target_only() -> None:
    module = _load_module()
    fixture_path = (
        get_project_root() / "scripts" / "channel" / "fixtures" / "complex_blackbox_scenarios.json"
    )
    scenarios = module.load_scenarios(fixture_path)

    selected = module.select_scenarios(scenarios, "cross_group_control_plane_stress")
    assert len(selected) == 1
    assert selected[0].scenario_id == "cross_group_control_plane_stress"


def test_extract_mcp_metrics_parses_blackbox_diagnostics() -> None:
    module = _load_module()
    stdout = "\n".join(
        [
            "Blackbox probe succeeded.",
            "MCP diagnostics:",
            "  mcp_last_event=mcp.pool.call.waiting",
            "  mcp_waiting_seen=true",
            '  mcp_event_counts={"mcp.pool.call.waiting":2,"mcp.pool.connect.succeeded":1}',
        ]
    )

    metrics = module.extract_mcp_metrics(stdout)
    assert metrics["mcp_last_event"] == "mcp.pool.call.waiting"
    assert metrics["mcp_waiting_seen"] is True
    assert metrics["mcp_event_counts"] == {
        "mcp.pool.call.waiting": 2,
        "mcp.pool.connect.succeeded": 1,
    }


def test_run_step_passes_runtime_partition_to_blackbox(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    recorded_cmd: list[str] = []

    def _fake_run_cmd(cmd: list[str]) -> tuple[int, int, str, str]:
        recorded_cmd[:] = cmd
        return 0, 7, "Observed outbound bot log:\nACK", ""

    monkeypatch.setattr(module, "run_cmd", _fake_run_cmd)

    session = module.SessionIdentity(
        alias="a",
        chat_id=-5101776367,
        user_id=1304799691,
        thread_id=None,
        chat_title=None,
    )
    cfg = module.RunnerConfig(
        dataset_path=tmp_path / "dataset.json",
        scenario_id=None,
        blackbox_script=tmp_path / "agent_channel_blackbox.py",
        webhook_url="http://127.0.0.1:8081/telegram/webhook",
        log_file=tmp_path / "runtime.log",
        username="tao3k",
        secret_token="secret",
        max_wait=20,
        max_idle_secs=20,
        max_parallel=1,
        execute_wave_parallel=False,
        runtime_partition_mode="chat",
        sessions=(session,),
        output_json=tmp_path / "out.json",
        output_markdown=tmp_path / "out.md",
        forbid_log_regexes=(),
        global_requirement=module.ComplexityRequirement(
            steps=0,
            dependency_edges=0,
            critical_path_len=0,
            parallel_waves=0,
        ),
        global_quality_requirement=module.QualityRequirement(
            min_error_signals=0,
            min_negative_feedback_events=0,
            min_correction_checks=0,
            min_successful_corrections=0,
            min_planned_hits=0,
            min_natural_language_steps=0,
            min_recall_credit_events=0,
            min_decay_events=0,
        ),
    )
    step = module.ScenarioStepSpec(
        step_id="s1",
        session_alias="a",
        prompt="hello world",
        expect_event=None,
        expect_reply_json_fields=(),
        expect_log_regexes=(),
        expect_bot_regexes=(),
        forbid_log_regexes=(),
        allow_no_bot=False,
        tags=(),
        depends_on=(),
        order=0,
    )

    result = module.run_step(cfg, "scenario", step, session, 0)

    assert result.passed is True
    assert result.session_key == "-5101776367"
    assert "--session-partition" in recorded_cmd
    partition_index = recorded_cmd.index("--session-partition")
    assert recorded_cmd[partition_index + 1] == "chat"
    regex_index = recorded_cmd.index("--expect-log-regex")
    assert recorded_cmd[regex_index + 1] == module.expected_session_log_regex(
        -5101776367,
        1304799691,
        None,
        "chat",
    )
