#!/usr/bin/env python3
"""
Run complex multi-step Telegram black-box scenarios with explicit dependency graphs.

Complexity is defined by workflow structure, not by a single prompt:
- number of steps
- dependency edges
- critical path length
- number of parallel execution waves

Each scenario is defined in JSON (default fixture under scripts/channel/fixtures).
The runner executes the scenario by posting synthetic Telegram updates through
agent_channel_blackbox.py and emits JSON/Markdown reports.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

try:
    from test_config_resolver import (
        allowed_users_from_settings,
        normalize_telegram_session_partition_mode,
        session_ids_from_runtime_log,
        session_partition_mode_from_runtime_log,
        telegram_session_partition_mode,
        telegram_webhook_secret_token,
        username_from_runtime_log,
        username_from_settings,
    )
except ModuleNotFoundError as import_err:
    _resolver_path = Path(__file__).resolve().with_name("test_config_resolver.py")
    _resolver_spec = importlib.util.spec_from_file_location("test_config_resolver", _resolver_path)
    if _resolver_spec is None or _resolver_spec.loader is None:
        raise RuntimeError(f"failed to load resolver module from {_resolver_path}") from import_err
    _resolver_module = importlib.util.module_from_spec(_resolver_spec)
    sys.modules.setdefault(_resolver_spec.name, _resolver_module)
    _resolver_spec.loader.exec_module(_resolver_module)
    allowed_users_from_settings = _resolver_module.allowed_users_from_settings
    normalize_telegram_session_partition_mode = (
        _resolver_module.normalize_telegram_session_partition_mode
    )
    session_ids_from_runtime_log = _resolver_module.session_ids_from_runtime_log
    session_partition_mode_from_runtime_log = (
        _resolver_module.session_partition_mode_from_runtime_log
    )
    telegram_session_partition_mode = _resolver_module.telegram_session_partition_mode
    telegram_webhook_secret_token = _resolver_module.telegram_webhook_secret_token
    username_from_runtime_log = _resolver_module.username_from_runtime_log
    username_from_settings = _resolver_module.username_from_settings


DEFAULT_MAX_WAIT = int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "40"))
DEFAULT_MAX_IDLE_SECS = int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "30"))
DEFAULT_LOG_FILE = os.environ.get("OMNI_CHANNEL_LOG_FILE", ".run/logs/omni-agent-webhook.log")

DEFAULT_FORBID_LOG_REGEXES = (
    "tools/call: Mcp error",
    "Telegram sendMessage failed",
)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
MEMORY_PLANNED_BIAS_RE = re.compile(
    r'event\s*=\s*"agent\.memory\.recall\.planned".*?\brecall_feedback_bias\b\s*=\s*([\-0-9.eE]+)'
)
MEMORY_DECISION_RE = re.compile(r'event\s*=\s*"agent\.memory\.recall\.(injected|skipped)"')
MEMORY_FEEDBACK_RE = re.compile(
    r'event\s*=\s*"agent\.memory\.recall\.feedback_updated".*?'
    r'feedback_source\s*=\s*"([^"]+)".*?'
    r"recall_feedback_bias_before\s*=\s*([\-0-9.eE]+).*?"
    r"recall_feedback_bias_after\s*=\s*([\-0-9.eE]+)"
)
MEMORY_RECALL_CREDIT_RE = re.compile(r'event\s*=\s*"agent\.memory\.recall\.credit_applied"')
MEMORY_DECAY_RE = re.compile(r'event\s*=\s*"agent\.memory\.decay\.applied"')
MCP_LAST_EVENT_RE = re.compile(r"^\s*mcp_last_event=(.*)$")
MCP_WAITING_SEEN_RE = re.compile(r"^\s*mcp_waiting_seen=(true|false)$")
MCP_EVENT_COUNTS_RE = re.compile(r"^\s*mcp_event_counts=(\{.*\})$")


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return int(raw)


def _parse_numeric_user_ids(entries: list[str]) -> list[int]:
    numeric_ids: list[int] = []
    for entry in entries:
        token = entry.strip()
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if value not in numeric_ids:
                numeric_ids.append(value)
    return numeric_ids


def _pick_default_peer_user_id(
    *,
    primary_user: int,
    preferred_offset: int,
    used: set[int],
    allowlisted_numeric_ids: list[int],
) -> int:
    preferred = primary_user + preferred_offset
    if preferred not in used and (
        not allowlisted_numeric_ids or preferred in allowlisted_numeric_ids
    ):
        return preferred

    for candidate in allowlisted_numeric_ids:
        if candidate not in used:
            return candidate

    fallback = preferred
    while fallback in used:
        fallback += 1
    return fallback


@dataclass(frozen=True)
class SessionIdentity:
    alias: str
    chat_id: int
    user_id: int
    thread_id: int | None
    chat_title: str | None


@dataclass(frozen=True)
class ScenarioStepSpec:
    step_id: str
    session_alias: str
    prompt: str
    expect_event: str | None
    expect_reply_json_fields: tuple[str, ...]
    expect_log_regexes: tuple[str, ...]
    expect_bot_regexes: tuple[str, ...]
    forbid_log_regexes: tuple[str, ...]
    allow_no_bot: bool
    tags: tuple[str, ...]
    depends_on: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class ComplexityRequirement:
    steps: int
    dependency_edges: int
    critical_path_len: int
    parallel_waves: int


@dataclass(frozen=True)
class QualityRequirement:
    min_error_signals: int
    min_negative_feedback_events: int
    min_correction_checks: int
    min_successful_corrections: int
    min_planned_hits: int
    min_natural_language_steps: int
    min_recall_credit_events: int
    min_decay_events: int


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    description: str
    steps: tuple[ScenarioStepSpec, ...]
    required_complexity: ComplexityRequirement | None
    required_quality: QualityRequirement | None


@dataclass(frozen=True)
class ComplexityProfile:
    step_count: int
    dependency_edges: int
    critical_path_len: int
    wave_count: int
    parallel_waves: int
    max_wave_width: int
    branch_nodes: int
    complexity_score: float


@dataclass(frozen=True)
class QualityProfile:
    error_signal_steps: int
    negative_feedback_events: int
    correction_check_steps: int
    successful_corrections: int
    planned_hits: int
    natural_language_steps: int
    recall_credit_events: int
    decay_events: int
    quality_score: float


@dataclass(frozen=True)
class StepRunResult:
    scenario_id: str
    step_id: str
    session_alias: str
    session_key: str
    wave_index: int
    depends_on: tuple[str, ...]
    prompt: str
    event: str | None
    command: tuple[str, ...]
    returncode: int
    duration_ms: int
    passed: bool
    skipped: bool
    skip_reason: str | None
    bot_excerpt: str | None
    memory_planned_seen: bool
    memory_injected_seen: bool
    memory_skipped_seen: bool
    memory_feedback_updated_seen: bool
    memory_recall_credit_seen: bool
    memory_decay_seen: bool
    memory_recall_credit_count: int
    memory_decay_count: int
    memory_planned_bias: float | None
    memory_decision: str | None
    mcp_last_event: str | None
    mcp_waiting_seen: bool
    mcp_event_counts: dict[str, int]
    feedback_command_bias_before: float | None
    feedback_command_bias_after: float | None
    feedback_command_bias_delta: float | None
    feedback_heuristic_bias_before: float | None
    feedback_heuristic_bias_after: float | None
    feedback_heuristic_bias_delta: float | None
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True)
class ScenarioRunResult:
    scenario_id: str
    description: str
    requirement: ComplexityRequirement
    complexity: ComplexityProfile
    complexity_passed: bool
    complexity_failures: tuple[str, ...]
    quality_requirement: QualityRequirement
    quality: QualityProfile
    quality_passed: bool
    quality_failures: tuple[str, ...]
    duration_ms: int
    steps: tuple[StepRunResult, ...]
    passed: bool


@dataclass(frozen=True)
class RunnerConfig:
    dataset_path: Path
    scenario_id: str | None
    blackbox_script: Path
    webhook_url: str
    log_file: Path
    username: str | None
    secret_token: str | None
    max_wait: int
    max_idle_secs: int
    max_parallel: int
    execute_wave_parallel: bool
    runtime_partition_mode: str | None
    sessions: tuple[SessionIdentity, ...]
    output_json: Path
    output_markdown: Path
    forbid_log_regexes: tuple[str, ...]
    global_requirement: ComplexityRequirement
    global_quality_requirement: QualityRequirement


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Run complex black-box workflow scenarios for omni-agent Telegram runtime "
            "and enforce structural complexity gates."
        )
    )
    parser.add_argument(
        "--dataset",
        default=str(script_dir / "fixtures" / "complex_blackbox_scenarios.json"),
        help="Complex scenario dataset JSON path.",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Optional scenario id filter.",
    )
    parser.add_argument(
        "--blackbox-script",
        default=str(script_dir / "agent_channel_blackbox.py"),
        help="Path to one-turn black-box probe script.",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get(
            "OMNI_WEBHOOK_URL",
            f"http://127.0.0.1:{os.environ.get('WEBHOOK_PORT', '8081')}/telegram/webhook",
        ),
        help="Telegram webhook endpoint.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"Runtime log path (default: {DEFAULT_LOG_FILE}).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME", ""),
        help="Synthetic Telegram username for allowlist checks.",
    )
    parser.add_argument(
        "--secret-token",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
        help="Webhook secret token.",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=DEFAULT_MAX_WAIT,
        help=f"Per-step max wait in seconds (default: {DEFAULT_MAX_WAIT}).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=DEFAULT_MAX_IDLE_SECS,
        help=f"Per-step max idle seconds (default: {DEFAULT_MAX_IDLE_SECS}).",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="Maximum concurrent probes per execution wave.",
    )
    parser.add_argument(
        "--execute-wave-parallel",
        action="store_true",
        help=(
            "Execute independent steps in the same wave concurrently. "
            "Default is sequential-in-wave for deterministic log attribution."
        ),
    )

    parser.add_argument(
        "--chat-a",
        type=int,
        default=_env_int("OMNI_TEST_CHAT_ID"),
        help="Session A chat id (default: $OMNI_TEST_CHAT_ID).",
    )
    parser.add_argument(
        "--chat-b",
        type=int,
        default=_env_int("OMNI_TEST_CHAT_B"),
        help="Session B chat id (default: $OMNI_TEST_CHAT_B).",
    )
    parser.add_argument(
        "--chat-c",
        type=int,
        default=_env_int("OMNI_TEST_CHAT_C"),
        help="Session C chat id (default: $OMNI_TEST_CHAT_C).",
    )
    parser.add_argument(
        "--user-a",
        type=int,
        default=_env_int("OMNI_TEST_USER_ID"),
        help="Session A user id (default: $OMNI_TEST_USER_ID).",
    )
    parser.add_argument(
        "--user-b",
        type=int,
        default=_env_int("OMNI_TEST_USER_B"),
        help="Session B user id (default: $OMNI_TEST_USER_B).",
    )
    parser.add_argument(
        "--user-c",
        type=int,
        default=_env_int("OMNI_TEST_USER_C"),
        help="Session C user id (default: $OMNI_TEST_USER_C).",
    )
    parser.add_argument(
        "--thread-a",
        type=int,
        default=_env_int("OMNI_TEST_THREAD_ID"),
        help="Session A thread id (default: $OMNI_TEST_THREAD_ID).",
    )
    parser.add_argument(
        "--thread-b",
        type=int,
        default=_env_int("OMNI_TEST_THREAD_B"),
        help="Session B thread id (default: $OMNI_TEST_THREAD_B).",
    )
    parser.add_argument(
        "--thread-c",
        type=int,
        default=_env_int("OMNI_TEST_THREAD_C"),
        help="Session C thread id (default: $OMNI_TEST_THREAD_C).",
    )
    parser.add_argument("--chat-title-a", default=None, help="Synthetic chat title for session A.")
    parser.add_argument("--chat-title-b", default=None, help="Synthetic chat title for session B.")
    parser.add_argument("--chat-title-c", default=None, help="Synthetic chat title for session C.")

    parser.add_argument(
        "--forbid-log-regex",
        action="append",
        default=[],
        help="Regex pattern that must not appear in probe logs (repeatable).",
    )

    parser.add_argument(
        "--min-steps",
        type=int,
        default=14,
        help="Global minimum workflow steps.",
    )
    parser.add_argument(
        "--min-dependency-edges",
        type=int,
        default=14,
        help="Global minimum dependency edges.",
    )
    parser.add_argument(
        "--min-critical-path",
        type=int,
        default=6,
        help="Global minimum critical path length.",
    )
    parser.add_argument(
        "--min-parallel-waves",
        type=int,
        default=3,
        help="Global minimum count of parallel execution waves.",
    )
    parser.add_argument(
        "--min-error-signals",
        type=int,
        default=2,
        help="Global minimum error-signal steps (tag=error_signal).",
    )
    parser.add_argument(
        "--min-negative-feedback-events",
        type=int,
        default=1,
        help="Global minimum negative feedback events (feedback delta < 0).",
    )
    parser.add_argument(
        "--min-correction-checks",
        type=int,
        default=2,
        help="Global minimum correction-check steps (tag=correction_check).",
    )
    parser.add_argument(
        "--min-successful-corrections",
        type=int,
        default=1,
        help="Global minimum successful correction-check steps after error signals.",
    )
    parser.add_argument(
        "--min-planned-hits",
        type=int,
        default=2,
        help="Global minimum steps where memory recall planning is observed.",
    )
    parser.add_argument(
        "--min-natural-language-steps",
        type=int,
        default=6,
        help="Global minimum count of non-command (natural language) steps.",
    )
    parser.add_argument(
        "--min-recall-credit-events",
        type=int,
        default=0,
        help="Global minimum observed memory recall credit events.",
    )
    parser.add_argument(
        "--min-decay-events",
        type=int,
        default=0,
        help="Global minimum observed memory decay events.",
    )

    parser.add_argument(
        "--output-json",
        default=".run/reports/agent-channel-complex-scenarios.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=".run/reports/agent-channel-complex-scenarios.md",
        help="Output Markdown report path.",
    )
    return parser.parse_args()


def expected_session_keys(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    partition_mode: str | None = None,
) -> tuple[str, ...]:
    partition = normalize_telegram_session_partition_mode(partition_mode)
    if partition == "chat":
        return (str(chat_id),)
    if partition == "chat_user":
        return (f"{chat_id}:{user_id}",)
    if partition == "user":
        return (str(user_id),)
    if partition == "chat_thread_user":
        if thread_id is None:
            return (f"{chat_id}:0:{user_id}", f"{chat_id}:{user_id}")
        return (f"{chat_id}:{thread_id}:{user_id}",)

    if thread_id is None:
        return (f"{chat_id}:{user_id}", f"{chat_id}:0:{user_id}")
    return (f"{chat_id}:{thread_id}:{user_id}",)


def expected_session_key(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    partition_mode: str | None = None,
) -> str:
    return expected_session_keys(chat_id, user_id, thread_id, partition_mode)[0]


def expected_session_log_regex(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    partition_mode: str | None = None,
) -> str:
    escaped = [
        re.escape(key) for key in expected_session_keys(chat_id, user_id, thread_id, partition_mode)
    ]
    body = escaped[0] if len(escaped) == 1 else f"(?:{'|'.join(escaped)})"
    return rf'session_key="?{body}"?'


def resolve_runtime_partition_mode(log_file: Path) -> str | None:
    override = os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "").strip()
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(log_file)
    if mode_from_log:
        return mode_from_log

    return telegram_session_partition_mode()


def apply_runtime_partition_defaults(
    sessions: tuple[SessionIdentity, ...], partition_mode: str | None
) -> tuple[SessionIdentity, ...]:
    if partition_mode != "chat_thread_user":
        return sessions
    return tuple(
        session if session.thread_id is not None else replace(session, thread_id=0)
        for session in sessions
    )


def tail_text(value: str, limit_lines: int = 40) -> str:
    lines = value.splitlines()
    if len(lines) <= limit_lines:
        return value
    return "\n".join(lines[-limit_lines:])


def parse_requirement(raw: dict[str, object] | None) -> ComplexityRequirement | None:
    if raw is None:
        return None
    return ComplexityRequirement(
        steps=int(raw.get("steps", 0)),
        dependency_edges=int(raw.get("dependency_edges", 0)),
        critical_path_len=int(raw.get("critical_path_len", 0)),
        parallel_waves=int(raw.get("parallel_waves", 0)),
    )


def parse_quality_requirement(raw: dict[str, object] | None) -> QualityRequirement | None:
    if raw is None:
        return None
    return QualityRequirement(
        min_error_signals=int(raw.get("min_error_signals", 0)),
        min_negative_feedback_events=int(raw.get("min_negative_feedback_events", 0)),
        min_correction_checks=int(raw.get("min_correction_checks", 0)),
        min_successful_corrections=int(raw.get("min_successful_corrections", 0)),
        min_planned_hits=int(raw.get("min_planned_hits", 0)),
        min_natural_language_steps=int(raw.get("min_natural_language_steps", 0)),
        min_recall_credit_events=int(raw.get("min_recall_credit_events", 0)),
        min_decay_events=int(raw.get("min_decay_events", 0)),
    )


def merge_requirements(
    global_requirement: ComplexityRequirement,
    scenario_requirement: ComplexityRequirement | None,
) -> ComplexityRequirement:
    if scenario_requirement is None:
        return global_requirement
    return ComplexityRequirement(
        steps=max(global_requirement.steps, scenario_requirement.steps),
        dependency_edges=max(
            global_requirement.dependency_edges,
            scenario_requirement.dependency_edges,
        ),
        critical_path_len=max(
            global_requirement.critical_path_len,
            scenario_requirement.critical_path_len,
        ),
        parallel_waves=max(
            global_requirement.parallel_waves,
            scenario_requirement.parallel_waves,
        ),
    )


def merge_quality_requirements(
    global_requirement: QualityRequirement,
    scenario_requirement: QualityRequirement | None,
) -> QualityRequirement:
    if scenario_requirement is None:
        return global_requirement
    return QualityRequirement(
        min_error_signals=max(
            global_requirement.min_error_signals,
            scenario_requirement.min_error_signals,
        ),
        min_negative_feedback_events=max(
            global_requirement.min_negative_feedback_events,
            scenario_requirement.min_negative_feedback_events,
        ),
        min_correction_checks=max(
            global_requirement.min_correction_checks,
            scenario_requirement.min_correction_checks,
        ),
        min_successful_corrections=max(
            global_requirement.min_successful_corrections,
            scenario_requirement.min_successful_corrections,
        ),
        min_planned_hits=max(
            global_requirement.min_planned_hits,
            scenario_requirement.min_planned_hits,
        ),
        min_natural_language_steps=max(
            global_requirement.min_natural_language_steps,
            scenario_requirement.min_natural_language_steps,
        ),
        min_recall_credit_events=max(
            global_requirement.min_recall_credit_events,
            scenario_requirement.min_recall_credit_events,
        ),
        min_decay_events=max(
            global_requirement.min_decay_events,
            scenario_requirement.min_decay_events,
        ),
    )


def _required_str_field(obj: dict[str, object], key: str, *, ctx: str) -> str:
    value = str(obj.get(key, "")).strip()
    if not value:
        raise ValueError(f"{ctx}: missing non-empty '{key}'")
    return value


def load_scenarios(path: Path) -> tuple[ScenarioSpec, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("dataset must provide a non-empty 'scenarios' array")

    scenarios: list[ScenarioSpec] = []
    seen_scenario_ids: set[str] = set()

    for scenario_index, scenario_obj in enumerate(scenarios_raw):
        if not isinstance(scenario_obj, dict):
            raise ValueError(f"scenario[{scenario_index}] must be an object")

        scenario_id = _required_str_field(scenario_obj, "id", ctx=f"scenario[{scenario_index}]")
        if scenario_id in seen_scenario_ids:
            raise ValueError(f"duplicate scenario id: {scenario_id}")
        seen_scenario_ids.add(scenario_id)

        description = str(scenario_obj.get("description", "")).strip() or scenario_id
        required_complexity = parse_requirement(
            scenario_obj.get("required_complexity")
            if isinstance(scenario_obj.get("required_complexity"), dict)
            else None
        )
        required_quality = parse_quality_requirement(
            scenario_obj.get("required_quality")
            if isinstance(scenario_obj.get("required_quality"), dict)
            else None
        )

        steps_raw = scenario_obj.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ValueError(f"scenario '{scenario_id}' requires non-empty steps")

        steps: list[ScenarioStepSpec] = []
        seen_step_ids: set[str] = set()

        for step_index, step_obj in enumerate(steps_raw):
            if not isinstance(step_obj, dict):
                raise ValueError(f"scenario '{scenario_id}' step[{step_index}] must be an object")
            step_ctx = f"scenario '{scenario_id}' step[{step_index}]"
            step_id = _required_str_field(step_obj, "id", ctx=step_ctx)
            if step_id in seen_step_ids:
                raise ValueError(f"scenario '{scenario_id}' duplicate step id: {step_id}")
            seen_step_ids.add(step_id)

            session_alias = _required_str_field(step_obj, "session", ctx=step_ctx).lower()
            if session_alias not in {"a", "b", "c"}:
                raise ValueError(f"{step_ctx}: session must be one of a|b|c")

            prompt = _required_str_field(step_obj, "prompt", ctx=step_ctx)
            expect_event_raw = step_obj.get("expect_event")
            expect_event = None
            if expect_event_raw is not None:
                expect_event = str(expect_event_raw).strip() or None

            expect_reply_json_fields_raw = step_obj.get("expect_reply_json_fields", [])
            if not isinstance(expect_reply_json_fields_raw, list):
                raise ValueError(f"{step_ctx}: expect_reply_json_fields must be an array")
            expect_reply_json_fields = tuple(
                str(item).strip() for item in expect_reply_json_fields_raw if str(item).strip()
            )

            expect_log_regexes_raw = step_obj.get("expect_log_regexes", [])
            if not isinstance(expect_log_regexes_raw, list):
                raise ValueError(f"{step_ctx}: expect_log_regexes must be an array")
            expect_log_regexes = tuple(
                str(item).strip() for item in expect_log_regexes_raw if str(item).strip()
            )

            expect_bot_regexes_raw = step_obj.get("expect_bot_regexes", [])
            if not isinstance(expect_bot_regexes_raw, list):
                raise ValueError(f"{step_ctx}: expect_bot_regexes must be an array")
            expect_bot_regexes = tuple(
                str(item).strip() for item in expect_bot_regexes_raw if str(item).strip()
            )

            forbid_log_regexes_raw = step_obj.get("forbid_log_regexes", [])
            if not isinstance(forbid_log_regexes_raw, list):
                raise ValueError(f"{step_ctx}: forbid_log_regexes must be an array")
            forbid_log_regexes = tuple(
                str(item).strip() for item in forbid_log_regexes_raw if str(item).strip()
            )

            depends_on_raw = step_obj.get("depends_on", [])
            if not isinstance(depends_on_raw, list):
                raise ValueError(f"{step_ctx}: depends_on must be an array")
            depends_on = tuple(str(item).strip() for item in depends_on_raw if str(item).strip())
            if step_id in depends_on:
                raise ValueError(f"{step_ctx}: step cannot depend on itself")

            allow_no_bot = bool(step_obj.get("allow_no_bot", False))
            tags_raw = step_obj.get("tags", [])
            if not isinstance(tags_raw, list):
                raise ValueError(f"{step_ctx}: tags must be an array")
            tags = tuple(str(item).strip().lower() for item in tags_raw if str(item).strip())

            steps.append(
                ScenarioStepSpec(
                    step_id=step_id,
                    session_alias=session_alias,
                    prompt=prompt,
                    expect_event=expect_event,
                    expect_reply_json_fields=expect_reply_json_fields,
                    expect_log_regexes=expect_log_regexes,
                    expect_bot_regexes=expect_bot_regexes,
                    forbid_log_regexes=forbid_log_regexes,
                    allow_no_bot=allow_no_bot,
                    tags=tags,
                    depends_on=depends_on,
                    order=step_index,
                )
            )

        step_ids = {step.step_id for step in steps}
        for step in steps:
            missing = [dep for dep in step.depends_on if dep not in step_ids]
            if missing:
                raise ValueError(
                    f"scenario '{scenario_id}' step '{step.step_id}' has unknown dependencies: {missing}"
                )

        scenario = ScenarioSpec(
            scenario_id=scenario_id,
            description=description,
            steps=tuple(steps),
            required_complexity=required_complexity,
            required_quality=required_quality,
        )

        # Detect cycles early so misconfigured scenarios fail fast.
        build_execution_waves(scenario)

        scenarios.append(scenario)

    return tuple(scenarios)


def select_scenarios(
    scenarios: tuple[ScenarioSpec, ...],
    scenario_id: str | None,
) -> tuple[ScenarioSpec, ...]:
    if scenario_id is None:
        return scenarios
    filtered = tuple(s for s in scenarios if s.scenario_id == scenario_id)
    if not filtered:
        raise ValueError(f"scenario not found: {scenario_id}")
    return filtered


def build_execution_waves(scenario: ScenarioSpec) -> tuple[tuple[ScenarioStepSpec, ...], ...]:
    pending: dict[str, ScenarioStepSpec] = {step.step_id: step for step in scenario.steps}
    completed: set[str] = set()
    waves: list[tuple[ScenarioStepSpec, ...]] = []

    while pending:
        ready = [
            step for step in pending.values() if all(dep in completed for dep in step.depends_on)
        ]
        if not ready:
            unresolved = sorted(pending)
            raise ValueError(
                f"scenario '{scenario.scenario_id}' has a dependency cycle or deadlock: {unresolved}"
            )
        ready.sort(key=lambda step: step.order)
        waves.append(tuple(ready))
        for step in ready:
            completed.add(step.step_id)
            pending.pop(step.step_id, None)

    return tuple(waves)


def compute_complexity_profile(scenario: ScenarioSpec) -> ComplexityProfile:
    waves = build_execution_waves(scenario)
    dependency_edges = sum(len(step.depends_on) for step in scenario.steps)

    children: dict[str, list[str]] = {step.step_id: [] for step in scenario.steps}
    longest_path: dict[str, int] = {}

    for step in scenario.steps:
        for dep in step.depends_on:
            children.setdefault(dep, []).append(step.step_id)

    for wave in waves:
        for step in wave:
            if not step.depends_on:
                longest_path[step.step_id] = 1
            else:
                longest_path[step.step_id] = max(longest_path[dep] for dep in step.depends_on) + 1

    critical_path_len = max(longest_path.values(), default=0)
    parallel_waves = sum(1 for wave in waves if len(wave) > 1)
    max_wave_width = max((len(wave) for wave in waves), default=0)
    branch_nodes = sum(1 for targets in children.values() if len(targets) > 1)

    complexity_score = (
        len(scenario.steps)
        + (dependency_edges * 1.5)
        + (critical_path_len * 2.0)
        + (parallel_waves * 3.0)
        + max_wave_width
        + branch_nodes
    )

    return ComplexityProfile(
        step_count=len(scenario.steps),
        dependency_edges=dependency_edges,
        critical_path_len=critical_path_len,
        wave_count=len(waves),
        parallel_waves=parallel_waves,
        max_wave_width=max_wave_width,
        branch_nodes=branch_nodes,
        complexity_score=round(complexity_score, 2),
    )


def evaluate_complexity(
    profile: ComplexityProfile,
    requirement: ComplexityRequirement,
) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    if profile.step_count < requirement.steps:
        failures.append(f"step_count={profile.step_count} < required={requirement.steps}")
    if profile.dependency_edges < requirement.dependency_edges:
        failures.append(
            f"dependency_edges={profile.dependency_edges} < required={requirement.dependency_edges}"
        )
    if profile.critical_path_len < requirement.critical_path_len:
        failures.append(
            "critical_path_len="
            f"{profile.critical_path_len} < required={requirement.critical_path_len}"
        )
    if profile.parallel_waves < requirement.parallel_waves:
        failures.append(
            f"parallel_waves={profile.parallel_waves} < required={requirement.parallel_waves}"
        )

    return (len(failures) == 0, tuple(failures))


def _has_ancestor_with_tag(
    step_id: str,
    steps_by_id: dict[str, ScenarioStepSpec],
    tag: str,
) -> bool:
    target = tag.lower()
    visited: set[str] = set()
    stack = list(steps_by_id[step_id].depends_on)
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        current_step = steps_by_id.get(current)
        if current_step is None:
            continue
        if target in current_step.tags:
            return True
        stack.extend(current_step.depends_on)
    return False


def compute_quality_profile(
    scenario: ScenarioSpec,
    results: tuple[StepRunResult, ...],
) -> QualityProfile:
    steps_by_id = {step.step_id: step for step in scenario.steps}
    results_by_id = {result.step_id: result for result in results}

    error_signal_steps = [step for step in scenario.steps if "error_signal" in step.tags]
    correction_check_steps = [step for step in scenario.steps if "correction_check" in step.tags]
    natural_language_steps = [
        step for step in scenario.steps if not step.prompt.strip().startswith("/")
    ]

    negative_feedback_events = 0
    for step in error_signal_steps:
        result = results_by_id.get(step.step_id)
        if result is None:
            continue
        delta = result.feedback_command_bias_delta
        if isinstance(delta, (int, float)) and delta < 0:
            negative_feedback_events += 1

    successful_corrections = 0
    for step in correction_check_steps:
        result = results_by_id.get(step.step_id)
        if result is None or not result.passed:
            continue
        if not _has_ancestor_with_tag(step.step_id, steps_by_id, "error_signal"):
            continue
        if not result.memory_planned_seen:
            continue
        successful_corrections += 1

    planned_hits = sum(1 for result in results if result.memory_planned_seen)
    recall_credit_events = sum(result.memory_recall_credit_count for result in results)
    decay_events = sum(result.memory_decay_count for result in results)

    quality_score = (
        len(error_signal_steps) * 2.0
        + negative_feedback_events * 3.0
        + len(correction_check_steps) * 2.0
        + successful_corrections * 4.0
        + planned_hits * 1.0
        + len(natural_language_steps) * 0.5
        + recall_credit_events * 0.5
        + decay_events * 1.0
    )

    return QualityProfile(
        error_signal_steps=len(error_signal_steps),
        negative_feedback_events=negative_feedback_events,
        correction_check_steps=len(correction_check_steps),
        successful_corrections=successful_corrections,
        planned_hits=planned_hits,
        natural_language_steps=len(natural_language_steps),
        recall_credit_events=recall_credit_events,
        decay_events=decay_events,
        quality_score=round(quality_score, 2),
    )


def evaluate_quality(
    profile: QualityProfile,
    requirement: QualityRequirement,
) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    if profile.error_signal_steps < requirement.min_error_signals:
        failures.append(
            f"error_signal_steps={profile.error_signal_steps} < required={requirement.min_error_signals}"
        )
    if profile.negative_feedback_events < requirement.min_negative_feedback_events:
        failures.append(
            "negative_feedback_events="
            f"{profile.negative_feedback_events} < required={requirement.min_negative_feedback_events}"
        )
    if profile.correction_check_steps < requirement.min_correction_checks:
        failures.append(
            "correction_check_steps="
            f"{profile.correction_check_steps} < required={requirement.min_correction_checks}"
        )
    if profile.successful_corrections < requirement.min_successful_corrections:
        failures.append(
            "successful_corrections="
            f"{profile.successful_corrections} < required={requirement.min_successful_corrections}"
        )
    if profile.planned_hits < requirement.min_planned_hits:
        failures.append(
            f"planned_hits={profile.planned_hits} < required={requirement.min_planned_hits}"
        )
    if profile.natural_language_steps < requirement.min_natural_language_steps:
        failures.append(
            "natural_language_steps="
            f"{profile.natural_language_steps} < required={requirement.min_natural_language_steps}"
        )
    if profile.recall_credit_events < requirement.min_recall_credit_events:
        failures.append(
            "recall_credit_events="
            f"{profile.recall_credit_events} < required={requirement.min_recall_credit_events}"
        )
    if profile.decay_events < requirement.min_decay_events:
        failures.append(
            f"decay_events={profile.decay_events} < required={requirement.min_decay_events}"
        )
    return (len(failures) == 0, tuple(failures))


def run_cmd(cmd: list[str]) -> tuple[int, int, str, str]:
    started = time.monotonic()
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration_ms = int((time.monotonic() - started) * 1000)
    return completed.returncode, duration_ms, completed.stdout, completed.stderr


def extract_bot_excerpt(stdout: str) -> str | None:
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "Observed outbound bot log:" and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value:
                return value
    bot_lines = [line.strip() for line in lines if "→ Bot:" in line]
    if bot_lines:
        return bot_lines[-1]
    return None


def detect_memory_event_flags(stdout: str) -> tuple[bool, bool, bool, bool]:
    return (
        "agent.memory.recall.planned" in stdout,
        "agent.memory.recall.injected" in stdout,
        "agent.memory.recall.skipped" in stdout,
        "agent.memory.recall.feedback_updated" in stdout,
    )


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_memory_metrics(stdout: str) -> dict[str, float | str | int | None]:
    normalized_lines = [ANSI_ESCAPE_RE.sub("", line) for line in stdout.splitlines()]
    planned_bias: float | None = None
    memory_decision: str | None = None
    recall_credit_count = 0
    decay_count = 0

    feedback_command_before: float | None = None
    feedback_command_after: float | None = None
    feedback_heuristic_before: float | None = None
    feedback_heuristic_after: float | None = None

    for line in normalized_lines:
        planned_match = MEMORY_PLANNED_BIAS_RE.search(line)
        if planned_match:
            planned_bias = _as_float(planned_match.group(1))

        decision_match = MEMORY_DECISION_RE.search(line)
        if decision_match:
            memory_decision = decision_match.group(1)
        if MEMORY_RECALL_CREDIT_RE.search(line):
            recall_credit_count += 1
        if MEMORY_DECAY_RE.search(line):
            decay_count += 1

        feedback_match = MEMORY_FEEDBACK_RE.search(line)
        if feedback_match:
            source = feedback_match.group(1).strip()
            before = _as_float(feedback_match.group(2))
            after = _as_float(feedback_match.group(3))
            if source == "session_feedback_command":
                feedback_command_before = before
                feedback_command_after = after
            elif source == "assistant_heuristic":
                feedback_heuristic_before = before
                feedback_heuristic_after = after

    command_delta = None
    if feedback_command_before is not None and feedback_command_after is not None:
        command_delta = feedback_command_after - feedback_command_before

    heuristic_delta = None
    if feedback_heuristic_before is not None and feedback_heuristic_after is not None:
        heuristic_delta = feedback_heuristic_after - feedback_heuristic_before

    return {
        "memory_planned_bias": planned_bias,
        "memory_decision": memory_decision,
        "memory_recall_credit_count": recall_credit_count,
        "memory_decay_count": decay_count,
        "feedback_command_bias_before": feedback_command_before,
        "feedback_command_bias_after": feedback_command_after,
        "feedback_command_bias_delta": command_delta,
        "feedback_heuristic_bias_before": feedback_heuristic_before,
        "feedback_heuristic_bias_after": feedback_heuristic_after,
        "feedback_heuristic_bias_delta": heuristic_delta,
    }


def extract_mcp_metrics(stdout: str) -> dict[str, object]:
    normalized_lines = [ANSI_ESCAPE_RE.sub("", line) for line in stdout.splitlines()]
    last_event: str | None = None
    waiting_seen = False
    event_counts: dict[str, int] = {}

    for line in normalized_lines:
        stripped = line.strip()
        last_event_match = MCP_LAST_EVENT_RE.match(stripped)
        if last_event_match:
            parsed = last_event_match.group(1).strip()
            last_event = parsed or None
            continue

        waiting_match = MCP_WAITING_SEEN_RE.match(stripped)
        if waiting_match:
            waiting_seen = waiting_match.group(1) == "true"
            continue

        counts_match = MCP_EVENT_COUNTS_RE.match(stripped)
        if not counts_match:
            continue
        try:
            parsed_counts = json.loads(counts_match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed_counts, dict):
            continue
        normalized_counts: dict[str, int] = {}
        for key, value in parsed_counts.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                normalized_counts[key] = value
            elif isinstance(value, float):
                normalized_counts[key] = int(value)
            elif isinstance(value, str):
                try:
                    normalized_counts[key] = int(value)
                except ValueError:
                    continue
        event_counts = normalized_counts

    if not waiting_seen and (
        int(event_counts.get("mcp.pool.connect.waiting", 0)) > 0
        or int(event_counts.get("mcp.pool.call.waiting", 0)) > 0
    ):
        waiting_seen = True

    return {
        "mcp_last_event": last_event,
        "mcp_waiting_seen": waiting_seen,
        "mcp_event_counts": event_counts,
    }


def run_step(
    cfg: RunnerConfig,
    scenario_id: str,
    step: ScenarioStepSpec,
    session: SessionIdentity,
    wave_index: int,
) -> StepRunResult:
    session_key = expected_session_key(
        session.chat_id,
        session.user_id,
        session.thread_id,
        cfg.runtime_partition_mode,
    )
    allowed_chat_ids = tuple(dict.fromkeys(identity.chat_id for identity in cfg.sessions))

    cmd = [
        sys.executable,
        str(cfg.blackbox_script),
        "--prompt",
        step.prompt,
        "--max-wait",
        str(cfg.max_wait),
        "--max-idle-secs",
        str(cfg.max_idle_secs),
        "--webhook-url",
        cfg.webhook_url,
        "--log-file",
        str(cfg.log_file),
        "--chat-id",
        str(session.chat_id),
        "--user-id",
        str(session.user_id),
        "--expect-log-regex",
        expected_session_log_regex(
            session.chat_id,
            session.user_id,
            session.thread_id,
            cfg.runtime_partition_mode,
        ),
    ]
    for allowed_chat_id in allowed_chat_ids:
        cmd.extend(["--allow-chat-id", str(allowed_chat_id)])

    if cfg.runtime_partition_mode:
        cmd.extend(["--session-partition", cfg.runtime_partition_mode])
    if step.expect_event:
        cmd.extend(["--expect-event", step.expect_event])
    if session.thread_id is not None:
        cmd.extend(["--thread-id", str(session.thread_id)])
    if cfg.username:
        cmd.extend(["--username", cfg.username])
    if session.chat_title:
        cmd.extend(["--chat-title", session.chat_title])
    if cfg.secret_token:
        cmd.extend(["--secret-token", cfg.secret_token])
    for field in step.expect_reply_json_fields:
        cmd.extend(["--expect-reply-json-field", field])
    for pattern in step.expect_log_regexes:
        cmd.extend(["--expect-log-regex", pattern])
    for pattern in step.expect_bot_regexes:
        cmd.extend(["--expect-bot-regex", pattern])
    for pattern in cfg.forbid_log_regexes:
        cmd.extend(["--forbid-log-regex", pattern])
    for pattern in step.forbid_log_regexes:
        cmd.extend(["--forbid-log-regex", pattern])
    if step.allow_no_bot:
        cmd.append("--allow-no-bot")

    returncode, duration_ms, stdout, stderr = run_cmd(cmd)
    passed = returncode == 0
    memory_planned_seen, memory_injected_seen, memory_skipped_seen, memory_feedback_updated_seen = (
        detect_memory_event_flags(stdout)
    )
    memory_metrics = extract_memory_metrics(stdout)
    mcp_metrics = extract_mcp_metrics(stdout)
    recall_credit_count = int(memory_metrics.get("memory_recall_credit_count") or 0)
    decay_count = int(memory_metrics.get("memory_decay_count") or 0)

    return StepRunResult(
        scenario_id=scenario_id,
        step_id=step.step_id,
        session_alias=step.session_alias,
        session_key=session_key,
        wave_index=wave_index,
        depends_on=step.depends_on,
        prompt=step.prompt,
        event=step.expect_event,
        command=tuple(cmd),
        returncode=returncode,
        duration_ms=duration_ms,
        passed=passed,
        skipped=False,
        skip_reason=None,
        bot_excerpt=extract_bot_excerpt(stdout),
        memory_planned_seen=memory_planned_seen,
        memory_injected_seen=memory_injected_seen,
        memory_skipped_seen=memory_skipped_seen,
        memory_feedback_updated_seen=memory_feedback_updated_seen,
        memory_recall_credit_seen=recall_credit_count > 0,
        memory_decay_seen=decay_count > 0,
        memory_recall_credit_count=recall_credit_count,
        memory_decay_count=decay_count,
        memory_planned_bias=memory_metrics["memory_planned_bias"],  # type: ignore[arg-type]
        memory_decision=memory_metrics["memory_decision"],  # type: ignore[arg-type]
        mcp_last_event=mcp_metrics["mcp_last_event"],  # type: ignore[arg-type]
        mcp_waiting_seen=bool(mcp_metrics["mcp_waiting_seen"]),
        mcp_event_counts=dict(mcp_metrics["mcp_event_counts"]),  # type: ignore[arg-type]
        feedback_command_bias_before=memory_metrics["feedback_command_bias_before"],  # type: ignore[arg-type]
        feedback_command_bias_after=memory_metrics["feedback_command_bias_after"],  # type: ignore[arg-type]
        feedback_command_bias_delta=memory_metrics["feedback_command_bias_delta"],  # type: ignore[arg-type]
        feedback_heuristic_bias_before=memory_metrics["feedback_heuristic_bias_before"],  # type: ignore[arg-type]
        feedback_heuristic_bias_after=memory_metrics["feedback_heuristic_bias_after"],  # type: ignore[arg-type]
        feedback_heuristic_bias_delta=memory_metrics["feedback_heuristic_bias_delta"],  # type: ignore[arg-type]
        stdout_tail=tail_text(stdout),
        stderr_tail=tail_text(stderr),
    )


def skipped_step_result(
    scenario_id: str,
    step: ScenarioStepSpec,
    session: SessionIdentity,
    wave_index: int,
    reason: str,
    runtime_partition_mode: str | None = None,
) -> StepRunResult:
    return StepRunResult(
        scenario_id=scenario_id,
        step_id=step.step_id,
        session_alias=step.session_alias,
        session_key=expected_session_key(
            session.chat_id,
            session.user_id,
            session.thread_id,
            runtime_partition_mode,
        ),
        wave_index=wave_index,
        depends_on=step.depends_on,
        prompt=step.prompt,
        event=step.expect_event,
        command=(),
        returncode=1,
        duration_ms=0,
        passed=False,
        skipped=True,
        skip_reason=reason,
        bot_excerpt=None,
        memory_planned_seen=False,
        memory_injected_seen=False,
        memory_skipped_seen=False,
        memory_feedback_updated_seen=False,
        memory_recall_credit_seen=False,
        memory_decay_seen=False,
        memory_recall_credit_count=0,
        memory_decay_count=0,
        memory_planned_bias=None,
        memory_decision=None,
        mcp_last_event=None,
        mcp_waiting_seen=False,
        mcp_event_counts={},
        feedback_command_bias_before=None,
        feedback_command_bias_after=None,
        feedback_command_bias_delta=None,
        feedback_heuristic_bias_before=None,
        feedback_heuristic_bias_after=None,
        feedback_heuristic_bias_delta=None,
        stdout_tail="",
        stderr_tail="",
    )


def run_scenario(cfg: RunnerConfig, scenario: ScenarioSpec) -> ScenarioRunResult:
    started = time.monotonic()

    requirement = merge_requirements(cfg.global_requirement, scenario.required_complexity)
    quality_requirement = merge_quality_requirements(
        cfg.global_quality_requirement,
        scenario.required_quality,
    )
    complexity = compute_complexity_profile(scenario)
    complexity_passed, complexity_failures = evaluate_complexity(complexity, requirement)

    if not complexity_passed:
        duration_ms = int((time.monotonic() - started) * 1000)
        quality = QualityProfile(
            error_signal_steps=0,
            negative_feedback_events=0,
            correction_check_steps=0,
            successful_corrections=0,
            planned_hits=0,
            natural_language_steps=0,
            recall_credit_events=0,
            decay_events=0,
            quality_score=0.0,
        )
        return ScenarioRunResult(
            scenario_id=scenario.scenario_id,
            description=scenario.description,
            requirement=requirement,
            complexity=complexity,
            complexity_passed=False,
            complexity_failures=complexity_failures,
            quality_requirement=quality_requirement,
            quality=quality,
            quality_passed=False,
            quality_failures=("quality_skipped_due_to_complexity_failure",),
            duration_ms=duration_ms,
            steps=(),
            passed=False,
        )

    sessions = {session.alias: session for session in cfg.sessions}
    waves = build_execution_waves(scenario)

    results: list[StepRunResult] = []
    completed: set[str] = set()
    failed: set[str] = set()

    for wave_index, wave in enumerate(waves):
        executable: list[ScenarioStepSpec] = []
        skipped: list[ScenarioStepSpec] = []

        for step in wave:
            blocked_deps = [dep for dep in step.depends_on if dep in failed]
            if blocked_deps:
                skipped.append(step)
            else:
                executable.append(step)

        for step in skipped:
            session = sessions[step.session_alias]
            reason = f"blocked_by_failed_dependencies={','.join(step.depends_on)}"
            result = skipped_step_result(
                scenario.scenario_id,
                step,
                session,
                wave_index,
                reason,
                cfg.runtime_partition_mode,
            )
            results.append(result)
            failed.add(step.step_id)

        if not executable:
            continue

        if cfg.execute_wave_parallel and len(executable) > 1:
            workers = min(max(cfg.max_parallel, 1), len(executable))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(
                        run_step,
                        cfg,
                        scenario.scenario_id,
                        step,
                        sessions[step.session_alias],
                        wave_index,
                    )
                    for step in executable
                ]
                wave_results = [future.result() for future in futures]
        else:
            wave_results = [
                run_step(
                    cfg,
                    scenario.scenario_id,
                    step,
                    sessions[step.session_alias],
                    wave_index,
                )
                for step in executable
            ]

        for result in wave_results:
            results.append(result)
            if result.passed:
                completed.add(result.step_id)
            else:
                failed.add(result.step_id)

    step_ids = {step.step_id for step in scenario.steps}
    already_recorded = {result.step_id for result in results}
    remaining = sorted(step_ids - already_recorded)
    if remaining:
        steps_by_id = {step.step_id: step for step in scenario.steps}
        for step_id in remaining:
            step = steps_by_id[step_id]
            session = sessions[step.session_alias]
            results.append(
                skipped_step_result(
                    scenario.scenario_id,
                    step,
                    session,
                    wave_index=len(waves),
                    reason="not_reached_after_upstream_failure",
                )
            )

    duration_ms = int((time.monotonic() - started) * 1000)
    passed = complexity_passed and all(step_result.passed for step_result in results)

    # Keep output order stable: scenario step order first.
    order = {step.step_id: step.order for step in scenario.steps}
    ordered_results = tuple(sorted(results, key=lambda result: order.get(result.step_id, 99999)))
    quality = compute_quality_profile(scenario, ordered_results)
    quality_passed, quality_failures = evaluate_quality(quality, quality_requirement)

    return ScenarioRunResult(
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        requirement=requirement,
        complexity=complexity,
        complexity_passed=complexity_passed,
        complexity_failures=complexity_failures,
        quality_requirement=quality_requirement,
        quality=quality,
        quality_passed=quality_passed,
        quality_failures=quality_failures,
        duration_ms=duration_ms,
        steps=ordered_results,
        passed=passed and quality_passed,
    )


def build_config(args: argparse.Namespace) -> RunnerConfig:
    if args.max_wait <= 0:
        raise ValueError("--max-wait must be positive")
    if args.max_idle_secs <= 0:
        raise ValueError("--max-idle-secs must be positive")
    if args.max_parallel <= 0:
        raise ValueError("--max-parallel must be positive")

    log_file = Path(args.log_file)
    dataset_path = Path(args.dataset)
    blackbox_script = Path(args.blackbox_script)
    if not dataset_path.exists():
        raise ValueError(f"dataset not found: {dataset_path}")
    if not blackbox_script.exists():
        raise ValueError(f"blackbox script not found: {blackbox_script}")

    chat_a = args.chat_a
    user_a = args.user_a
    thread_a = args.thread_a
    if chat_a is None or user_a is None:
        inferred_chat, inferred_user, inferred_thread = session_ids_from_runtime_log(log_file)
        if chat_a is None:
            chat_a = inferred_chat
        if user_a is None:
            user_a = inferred_user
        if thread_a is None:
            thread_a = inferred_thread

    if chat_a is None or user_a is None:
        raise ValueError(
            "chat_a/user_a are required. Use --chat-a/--user-a or emit one live message first "
            "so ids can be inferred from runtime logs."
        )

    chat_b = int(args.chat_b if args.chat_b is not None else chat_a)
    chat_c = int(args.chat_c if args.chat_c is not None else chat_a)

    user_a_int = int(user_a)
    allowlisted_numeric_users = _parse_numeric_user_ids(allowed_users_from_settings())
    used_users = {user_a_int}

    if args.user_b is not None:
        user_b = int(args.user_b)
    else:
        user_b = _pick_default_peer_user_id(
            primary_user=user_a_int,
            preferred_offset=1,
            used=used_users,
            allowlisted_numeric_ids=allowlisted_numeric_users,
        )
    used_users.add(user_b)

    if args.user_c is not None:
        user_c = int(args.user_c)
    else:
        user_c = _pick_default_peer_user_id(
            primary_user=user_a_int,
            preferred_offset=2,
            used=used_users,
            allowlisted_numeric_ids=allowlisted_numeric_users,
        )

    thread_b = args.thread_b
    thread_c = args.thread_c

    username = args.username.strip() if args.username else None
    if not username:
        username = username_from_settings()
    if not username:
        username = username_from_runtime_log(log_file)

    sessions = (
        SessionIdentity(
            alias="a",
            chat_id=int(chat_a),
            user_id=int(user_a),
            thread_id=thread_a,
            chat_title=(args.chat_title_a.strip() if args.chat_title_a else None),
        ),
        SessionIdentity(
            alias="b",
            chat_id=chat_b,
            user_id=user_b,
            thread_id=thread_b,
            chat_title=(args.chat_title_b.strip() if args.chat_title_b else None),
        ),
        SessionIdentity(
            alias="c",
            chat_id=chat_c,
            user_id=user_c,
            thread_id=thread_c,
            chat_title=(args.chat_title_c.strip() if args.chat_title_c else None),
        ),
    )
    runtime_partition_mode = resolve_runtime_partition_mode(log_file)
    sessions = apply_runtime_partition_defaults(sessions, runtime_partition_mode)

    key_sets = [
        set(
            expected_session_keys(
                session.chat_id,
                session.user_id,
                session.thread_id,
                runtime_partition_mode,
            )
        )
        for session in sessions
    ]
    if key_sets[0] & key_sets[1] or key_sets[0] & key_sets[2] or key_sets[1] & key_sets[2]:
        keys = [
            expected_session_key(
                session.chat_id,
                session.user_id,
                session.thread_id,
                runtime_partition_mode,
            )
            for session in sessions
        ]
        raise ValueError(
            "sessions a/b/c must map to distinct identities. "
            f"got keys={keys}; adjust chat/user/thread values."
        )

    secret_token: str | None = args.secret_token.strip() if args.secret_token else None
    if not secret_token:
        secret_token = telegram_webhook_secret_token()

    merged_forbidden = tuple(dict.fromkeys([*DEFAULT_FORBID_LOG_REGEXES, *args.forbid_log_regex]))

    return RunnerConfig(
        dataset_path=dataset_path,
        scenario_id=(args.scenario.strip() if args.scenario else None),
        blackbox_script=blackbox_script,
        webhook_url=args.webhook_url,
        log_file=log_file,
        username=username,
        secret_token=secret_token,
        max_wait=int(args.max_wait),
        max_idle_secs=int(args.max_idle_secs),
        max_parallel=int(args.max_parallel),
        execute_wave_parallel=bool(args.execute_wave_parallel),
        runtime_partition_mode=runtime_partition_mode,
        sessions=sessions,
        output_json=Path(args.output_json),
        output_markdown=Path(args.output_markdown),
        forbid_log_regexes=merged_forbidden,
        global_requirement=ComplexityRequirement(
            steps=int(args.min_steps),
            dependency_edges=int(args.min_dependency_edges),
            critical_path_len=int(args.min_critical_path),
            parallel_waves=int(args.min_parallel_waves),
        ),
        global_quality_requirement=QualityRequirement(
            min_error_signals=int(args.min_error_signals),
            min_negative_feedback_events=int(args.min_negative_feedback_events),
            min_correction_checks=int(args.min_correction_checks),
            min_successful_corrections=int(args.min_successful_corrections),
            min_planned_hits=int(args.min_planned_hits),
            min_natural_language_steps=int(args.min_natural_language_steps),
            min_recall_credit_events=int(args.min_recall_credit_events),
            min_decay_events=int(args.min_decay_events),
        ),
    )


def render_markdown(report: dict[str, object]) -> str:
    lines: list[str] = [
        "# Agent Channel Complex Scenario Report",
        "",
        "## Overview",
        f"- started_at: `{report['started_at']}`",
        f"- finished_at: `{report['finished_at']}`",
        f"- duration_ms: `{report['duration_ms']}`",
        f"- overall: `{'PASS' if report['overall_passed'] else 'FAIL'}`",
        f"- scenarios: `{report['summary']['passed']}/{report['summary']['total']}` passed",
        f"- runtime_partition_mode: `{report['config']['runtime_partition_mode']}`",
        "",
        "## Sessions",
    ]

    for session in report["config"]["sessions"]:
        lines.append(
            "- `{alias}` -> chat_id=`{chat}` user_id=`{user}` thread_id=`{thread}` "
            "chat_title=`{title}`".format(
                alias=session["alias"],
                chat=session["chat_id"],
                user=session["user_id"],
                thread=session["thread_id"],
                title=session["chat_title"],
            )
        )

    lines.extend(["", "## Scenario Results", ""])

    for scenario in report["scenarios"]:
        natural_language_steps = [
            step for step in scenario["steps"] if not str(step["prompt"]).strip().startswith("/")
        ]
        with_bot_excerpt = [step for step in scenario["steps"] if step.get("bot_excerpt")]
        planned_hits = sum(1 for step in scenario["steps"] if step.get("memory_planned_seen"))
        injected_hits = sum(1 for step in scenario["steps"] if step.get("memory_injected_seen"))
        skipped_hits = sum(1 for step in scenario["steps"] if step.get("memory_skipped_seen"))
        feedback_hits = sum(
            1 for step in scenario["steps"] if step.get("memory_feedback_updated_seen")
        )
        recall_credit_steps = sum(
            1 for step in scenario["steps"] if step.get("memory_recall_credit_seen")
        )
        decay_steps = sum(1 for step in scenario["steps"] if step.get("memory_decay_seen"))
        recall_credit_events = sum(
            int(step.get("memory_recall_credit_count") or 0) for step in scenario["steps"]
        )
        decay_events = sum(int(step.get("memory_decay_count") or 0) for step in scenario["steps"])
        mcp_waiting_steps = sum(1 for step in scenario["steps"] if step.get("mcp_waiting_seen"))
        mcp_waiting_events = 0
        for step in scenario["steps"]:
            counts = step.get("mcp_event_counts")
            if not isinstance(counts, dict):
                continue
            mcp_waiting_events += int(counts.get("mcp.pool.connect.waiting", 0) or 0)
            mcp_waiting_events += int(counts.get("mcp.pool.call.waiting", 0) or 0)
        lines.extend(
            [
                f"### {scenario['scenario_id']}",
                f"- description: {scenario['description']}",
                f"- result: `{'PASS' if scenario['passed'] else 'FAIL'}`",
                f"- duration_ms: `{scenario['duration_ms']}`",
                (
                    "- behavioral_evidence: "
                    f"natural_language_steps={len(natural_language_steps)}, "
                    f"steps_with_bot_excerpt={len(with_bot_excerpt)}, "
                    f"planned_hits={planned_hits}, injected_hits={injected_hits}, "
                    f"skipped_hits={skipped_hits}, feedback_updated_hits={feedback_hits}, "
                    f"recall_credit_steps={recall_credit_steps}, decay_steps={decay_steps}, "
                    f"recall_credit_events={recall_credit_events}, decay_events={decay_events}, "
                    f"mcp_waiting_steps={mcp_waiting_steps}, mcp_waiting_events={mcp_waiting_events}"
                ),
                (
                    "- complexity: "
                    "steps={steps}, edges={edges}, critical_path={critical}, "
                    "parallel_waves={parallel}, score={score}"
                ).format(
                    steps=scenario["complexity"]["step_count"],
                    edges=scenario["complexity"]["dependency_edges"],
                    critical=scenario["complexity"]["critical_path_len"],
                    parallel=scenario["complexity"]["parallel_waves"],
                    score=scenario["complexity"]["complexity_score"],
                ),
                (
                    "- requirement: "
                    "steps>={steps}, edges>={edges}, critical_path>={critical}, "
                    "parallel_waves>={parallel}"
                ).format(
                    steps=scenario["requirement"]["steps"],
                    edges=scenario["requirement"]["dependency_edges"],
                    critical=scenario["requirement"]["critical_path_len"],
                    parallel=scenario["requirement"]["parallel_waves"],
                ),
                (
                    "- quality: "
                    "error_signals={es}, negative_feedback_events={ne}, "
                    "correction_checks={cc}, successful_corrections={sc}, "
                    "planned_hits={ph}, natural_language_steps={nl}, "
                    "recall_credit_events={rc}, decay_events={de}, score={score}"
                ).format(
                    es=scenario["quality"]["error_signal_steps"],
                    ne=scenario["quality"]["negative_feedback_events"],
                    cc=scenario["quality"]["correction_check_steps"],
                    sc=scenario["quality"]["successful_corrections"],
                    ph=scenario["quality"]["planned_hits"],
                    nl=scenario["quality"]["natural_language_steps"],
                    rc=scenario["quality"]["recall_credit_events"],
                    de=scenario["quality"]["decay_events"],
                    score=scenario["quality"]["quality_score"],
                ),
                (
                    "- quality_requirement: "
                    "error_signals>={es}, negative_feedback_events>={ne}, "
                    "correction_checks>={cc}, successful_corrections>={sc}, "
                    "planned_hits>={ph}, natural_language_steps>={nl}, "
                    "recall_credit_events>={rc}, decay_events>={de}"
                ).format(
                    es=scenario["quality_requirement"]["min_error_signals"],
                    ne=scenario["quality_requirement"]["min_negative_feedback_events"],
                    cc=scenario["quality_requirement"]["min_correction_checks"],
                    sc=scenario["quality_requirement"]["min_successful_corrections"],
                    ph=scenario["quality_requirement"]["min_planned_hits"],
                    nl=scenario["quality_requirement"]["min_natural_language_steps"],
                    rc=scenario["quality_requirement"]["min_recall_credit_events"],
                    de=scenario["quality_requirement"]["min_decay_events"],
                ),
            ]
        )

        if scenario["complexity_failures"]:
            lines.append("- complexity_failures:")
            for issue in scenario["complexity_failures"]:
                lines.append(f"  - {issue}")
        if scenario["quality_failures"]:
            lines.append("- quality_failures:")
            for issue in scenario["quality_failures"]:
                lines.append(f"  - {issue}")

        lines.extend(
            [
                "",
                "| Step | Session | Wave | Event | Result | Duration (ms) |",
                "|---|---|---:|---|---|---:|",
            ]
        )

        for step in scenario["steps"]:
            status = "PASS" if step["passed"] else ("SKIP" if step["skipped"] else "FAIL")
            lines.append(
                "| `{step}` | `{session}` | {wave} | `{event}` | {status} | {duration} |".format(
                    step=step["step_id"],
                    session=step["session_key"],
                    wave=step["wave_index"],
                    event=step["event"] or "-",
                    status=status,
                    duration=step["duration_ms"],
                )
            )

        lines.extend(
            [
                "",
                "Natural-language trace:",
                "",
                "| Step | Prompt | Bot Reply |",
                "|---|---|---|",
            ]
        )
        for step in scenario["steps"]:
            if str(step["prompt"]).strip().startswith("/"):
                continue
            prompt = str(step["prompt"]).replace("|", "\\|")
            bot_excerpt = str(step.get("bot_excerpt") or "").replace("|", "\\|")
            lines.append(f"| `{step['step_id']}` | {prompt} | {bot_excerpt} |")

        lines.extend(
            [
                "",
                "Memory adaptation evidence:",
                "",
                "| Step | planned_bias | decision | recall_credit_count | decay_count | cmd_feedback_delta | heuristic_feedback_delta |",
                "|---|---:|---|---:|---:|---:|---:|",
            ]
        )
        for step in scenario["steps"]:
            planned_bias = step.get("memory_planned_bias")
            decision = step.get("memory_decision") or "-"
            recall_credit_count = int(step.get("memory_recall_credit_count") or 0)
            decay_count = int(step.get("memory_decay_count") or 0)
            cmd_delta = step.get("feedback_command_bias_delta")
            heur_delta = step.get("feedback_heuristic_bias_delta")
            lines.append(
                "| `{sid}` | {pb} | {dec} | {rc} | {de} | {cd} | {hd} |".format(
                    sid=step["step_id"],
                    pb=f"{planned_bias:.6f}" if isinstance(planned_bias, (int, float)) else "-",
                    dec=decision,
                    rc=recall_credit_count,
                    de=decay_count,
                    cd=f"{cmd_delta:.6f}" if isinstance(cmd_delta, (int, float)) else "-",
                    hd=f"{heur_delta:.6f}" if isinstance(heur_delta, (int, float)) else "-",
                )
            )

        lines.extend(
            [
                "",
                "MCP stage diagnostics:",
                "",
                "| Step | mcp_last_event | waiting_seen | mcp_event_counts |",
                "|---|---|---|---|",
            ]
        )
        for step in scenario["steps"]:
            mcp_last_event = str(step.get("mcp_last_event") or "-")
            waiting_seen = "true" if step.get("mcp_waiting_seen") else "false"
            counts = step.get("mcp_event_counts")
            counts_text = "-"
            if isinstance(counts, dict):
                pairs: list[tuple[str, int]] = []
                for key, value in counts.items():
                    if not isinstance(key, str):
                        continue
                    if isinstance(value, bool):
                        continue
                    if isinstance(value, int):
                        parsed_value = value
                    elif isinstance(value, float):
                        parsed_value = int(value)
                    elif isinstance(value, str):
                        try:
                            parsed_value = int(value)
                        except ValueError:
                            continue
                    else:
                        continue
                    if parsed_value > 0:
                        pairs.append((key, parsed_value))
                if pairs:
                    pairs.sort(key=lambda item: item[0])
                    counts_text = ",".join(f"{key}:{value}" for key, value in pairs)
            lines.append(
                "| `{sid}` | `{last}` | {waiting} | `{counts}` |".format(
                    sid=step["step_id"],
                    last=mcp_last_event.replace("|", "\\|"),
                    waiting=waiting_seen,
                    counts=counts_text.replace("|", "\\|"),
                )
            )

        failure_steps = [
            step for step in scenario["steps"] if not step["passed"] and not step["skipped"]
        ]
        if failure_steps:
            lines.append("")
            lines.append("Failure tails:")
            for step in failure_steps:
                lines.extend(
                    [
                        f"- `{step['step_id']}`",
                        "```text",
                        step["stderr_tail"] or step["stdout_tail"] or "(no output)",
                        "```",
                    ]
                )

        lines.append("")

    return "\n".join(lines)


def build_report(
    cfg: RunnerConfig,
    scenario_results: tuple[ScenarioRunResult, ...],
    started_mono: float,
    started_dt: datetime,
) -> dict[str, object]:
    finished_dt = datetime.now(UTC)
    duration_ms = int((time.monotonic() - started_mono) * 1000)

    scenario_payloads = []
    passed_count = 0

    for result in scenario_results:
        if result.passed:
            passed_count += 1
        payload = {
            "scenario_id": result.scenario_id,
            "description": result.description,
            "requirement": asdict(result.requirement),
            "complexity": asdict(result.complexity),
            "complexity_passed": result.complexity_passed,
            "complexity_failures": list(result.complexity_failures),
            "quality_requirement": asdict(result.quality_requirement),
            "quality": asdict(result.quality),
            "quality_passed": result.quality_passed,
            "quality_failures": list(result.quality_failures),
            "duration_ms": result.duration_ms,
            "passed": result.passed,
            "steps": [asdict(step) for step in result.steps],
        }
        scenario_payloads.append(payload)

    overall_passed = passed_count == len(scenario_payloads) and len(scenario_payloads) > 0

    return {
        "started_at": started_dt.isoformat(),
        "finished_at": finished_dt.isoformat(),
        "duration_ms": duration_ms,
        "overall_passed": overall_passed,
        "summary": {
            "total": len(scenario_payloads),
            "passed": passed_count,
            "failed": len(scenario_payloads) - passed_count,
        },
        "config": {
            "dataset": str(cfg.dataset_path),
            "scenario_filter": cfg.scenario_id,
            "blackbox_script": str(cfg.blackbox_script),
            "webhook_url": cfg.webhook_url,
            "log_file": str(cfg.log_file),
            "max_wait": cfg.max_wait,
            "max_idle_secs": cfg.max_idle_secs,
            "max_parallel": cfg.max_parallel,
            "execute_wave_parallel": cfg.execute_wave_parallel,
            "runtime_partition_mode": cfg.runtime_partition_mode,
            "username": cfg.username,
            "forbid_log_regexes": list(cfg.forbid_log_regexes),
            "global_requirement": asdict(cfg.global_requirement),
            "global_quality_requirement": asdict(cfg.global_quality_requirement),
            "sessions": [asdict(session) for session in cfg.sessions],
        },
        "scenarios": scenario_payloads,
    }


def write_outputs(report: dict[str, object], output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    try:
        cfg = build_config(parse_args())
        scenarios = select_scenarios(load_scenarios(cfg.dataset_path), cfg.scenario_id)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    started_dt = datetime.now(UTC)
    started_mono = time.monotonic()

    scenario_results = tuple(run_scenario(cfg, scenario) for scenario in scenarios)
    report = build_report(cfg, scenario_results, started_mono, started_dt)
    write_outputs(report, cfg.output_json, cfg.output_markdown)

    print("Complex scenario suite completed.")
    print(f"  overall={'PASS' if report['overall_passed'] else 'FAIL'}")
    print(
        "  scenarios={passed}/{total}".format(
            passed=report["summary"]["passed"],
            total=report["summary"]["total"],
        )
    )
    print(f"  json_report={cfg.output_json}")
    print(f"  markdown_report={cfg.output_markdown}")

    if not report["overall_passed"]:
        failed = [
            scenario["scenario_id"] for scenario in report["scenarios"] if not scenario["passed"]
        ]
        print(f"  failed_scenarios={failed}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
