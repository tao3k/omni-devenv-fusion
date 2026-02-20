#!/usr/bin/env python3
"""
Run strict Telegram command black-box probes against local webhook runtime.

This script is the Python implementation for `test-omni-agent-command-events.sh`.
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
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

try:
    from test_config_resolver import (
        group_profile_chat_ids,
        group_profile_int,
        normalize_telegram_session_partition_mode,
        session_partition_mode_from_runtime_log,
        telegram_session_partition_mode,
        telegram_webhook_secret_token,
    )
except ModuleNotFoundError as import_err:
    _resolver_path = Path(__file__).resolve().with_name("test_config_resolver.py")
    _resolver_spec = importlib.util.spec_from_file_location("test_config_resolver", _resolver_path)
    if _resolver_spec is None or _resolver_spec.loader is None:
        raise RuntimeError(f"failed to load resolver module from {_resolver_path}") from import_err
    _resolver_module = importlib.util.module_from_spec(_resolver_spec)
    sys.modules.setdefault(_resolver_spec.name, _resolver_module)
    _resolver_spec.loader.exec_module(_resolver_module)
    group_profile_chat_ids = _resolver_module.group_profile_chat_ids
    group_profile_int = _resolver_module.group_profile_int
    normalize_telegram_session_partition_mode = (
        _resolver_module.normalize_telegram_session_partition_mode
    )
    session_partition_mode_from_runtime_log = (
        _resolver_module.session_partition_mode_from_runtime_log
    )
    telegram_session_partition_mode = _resolver_module.telegram_session_partition_mode
    telegram_webhook_secret_token = _resolver_module.telegram_webhook_secret_token

FORBIDDEN_LOG_PATTERN = "tools/call: Mcp error"
SUITES = ("core", "control", "admin", "all")
MATRIX_TRANSIENT_EXIT_CODES = frozenset({2, 3, 4, 6, 7})
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
SESSION_KEY_RE = re.compile(r"\bsession_key\s*=\s*(?:\"|')?([-\d]+(?::[-\d]+){1,2})(?:\"|')?")
PARSED_MESSAGE_CHAT_ID_RE = re.compile(r"\bchat_id\s*=\s*Some\((-?\d+)\)")
MESSAGE_THREAD_ID_RE = re.compile(r"\bmessage_thread_id\s*=\s*Some\((\d+)\)")


@dataclass(frozen=True)
class ProbeCase:
    case_id: str
    prompt: str
    event_name: str
    suites: tuple[str, ...]
    extra_args: tuple[str, ...] = ()
    user_id: int | None = None
    chat_id: int | None = None
    thread_id: int | None = None


@dataclass(frozen=True)
class ProbeAttemptRecord:
    mode: str
    case_id: str
    prompt: str
    event_name: str
    suites: tuple[str, ...]
    chat_id: int | None
    user_id: int | None
    thread_id: int | None
    attempt: int
    max_attempts: int
    returncode: int
    passed: bool
    duration_ms: int
    retry_scheduled: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a strict Telegram command black-box matrix against local webhook runtime. "
            "Each probe requires a command-specific event and forbids MCP tool-call errors."
        )
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "25")),
        help="Overall wait upper-bound per probe in seconds (default: 25).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "25")),
        help="Max idle wait for new logs per probe in seconds (default: 25).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME", ""),
        help="Synthetic Telegram username (default: $OMNI_TEST_USERNAME).",
    )
    parser.add_argument(
        "--allow-chat-id",
        action="append",
        default=[],
        help=("Allowlisted chat id passed through to agent_channel_blackbox.py (repeatable)."),
    )
    parser.add_argument(
        "--admin-user-id",
        type=int,
        default=None,
        help=(
            "Optional Telegram user_id used for admin-only probes "
            "(`/reset`, `/resume drop`, `/session admin ...`). "
            "Falls back to $OMNI_TEST_ADMIN_USER_ID when omitted."
        ),
    )
    parser.add_argument(
        "--group-chat-id",
        type=int,
        default=None,
        help=(
            "Optional group chat_id for admin suite probes (`/session admin ...`). "
            "Falls back to $OMNI_TEST_GROUP_CHAT_ID when omitted."
        ),
    )
    parser.add_argument(
        "--admin-group-chat-id",
        action="append",
        type=int,
        default=[],
        help=("Repeatable admin-suite chat id for matrix runs. Used only with --admin-matrix."),
    )
    parser.add_argument(
        "--admin-matrix",
        action="store_true",
        help=(
            "Run selected admin cases across multiple group chats "
            "(from --admin-group-chat-id or group profile env file)."
        ),
    )
    parser.add_argument(
        "--matrix-retries",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MATRIX_RETRIES", "2")),
        help=(
            "Retry count for transient admin-matrix probe failures "
            "(default: 2, from $OMNI_BLACKBOX_MATRIX_RETRIES)."
        ),
    )
    parser.add_argument(
        "--matrix-backoff-secs",
        type=float,
        default=float(os.environ.get("OMNI_BLACKBOX_MATRIX_BACKOFF_SECS", "2")),
        help=(
            "Base backoff seconds for admin-matrix retries "
            "(default: 2, exponential: base*2^attempt)."
        ),
    )
    parser.add_argument(
        "--assert-admin-isolation",
        action="store_true",
        help=(
            "When used with --admin-matrix, run extra recipient-isolation checks: "
            "per-group add/list/clear plus cross-group zero-count assertions."
        ),
    )
    parser.add_argument(
        "--assert-admin-topic-isolation",
        action="store_true",
        help=(
            "Run extra same-group cross-topic isolation checks: delegated admins "
            "set in thread A must not leak into thread B."
        ),
    )
    parser.add_argument(
        "--group-thread-id",
        type=int,
        default=None,
        help=(
            "Optional topic thread id for admin suite probes. "
            "Falls back to $OMNI_TEST_GROUP_THREAD_ID when omitted."
        ),
    )
    parser.add_argument(
        "--group-thread-id-b",
        type=int,
        default=None,
        help=(
            "Optional secondary topic thread id for cross-topic isolation checks. "
            "Falls back to $OMNI_TEST_GROUP_THREAD_B; defaults to thread A + 1."
        ),
    )
    parser.add_argument(
        "--secret-token",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
        help=(
            "Webhook secret token passed through to agent_channel_blackbox.py. "
            "Defaults to $TELEGRAM_WEBHOOK_SECRET."
        ),
    )
    parser.add_argument(
        "--suite",
        action="append",
        choices=SUITES,
        default=[],
        help=("Run only selected suite(s): core, control, admin, all. Repeatable. Default: all."),
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help=(
            "Run only specific case id(s). Repeatable. Use --list-cases to inspect available ids."
        ),
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List available black-box case ids and exit.",
    )
    parser.add_argument(
        "--output-json",
        default=os.environ.get(
            "OMNI_COMMAND_EVENTS_OUTPUT_JSON",
            ".run/reports/agent-channel-command-events.json",
        ),
        help="Structured output JSON report path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=os.environ.get(
            "OMNI_COMMAND_EVENTS_OUTPUT_MARKDOWN",
            ".run/reports/agent-channel-command-events.md",
        ),
        help="Structured output Markdown report path.",
    )
    return parser.parse_args()


def parse_optional_int_env(var_name: str) -> int | None:
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{var_name} must be an integer, got '{raw}'.") from error


def dedup_ints(values: list[int]) -> tuple[int, ...]:
    ordered: list[int] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return tuple(ordered)


def runtime_log_file() -> Path:
    return Path(os.environ.get("OMNI_CHANNEL_LOG_FILE", ".run/logs/omni-agent-webhook.log"))


def resolve_runtime_partition_mode() -> str | None:
    override = os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "").strip()
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(runtime_log_file())
    if mode_from_log:
        return mode_from_log

    return telegram_session_partition_mode()


def infer_group_thread_id_from_runtime_log(chat_id: int | None) -> int | None:
    if chat_id is None:
        return None
    log_path = runtime_log_file()
    if not log_path.exists():
        return None

    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for raw_line in reversed(lines):
        line = ANSI_ESCAPE_RE.sub("", raw_line)
        if "Parsed message, forwarding to agent" not in line:
            continue
        chat_match = PARSED_MESSAGE_CHAT_ID_RE.search(line)
        if chat_match and int(chat_match.group(1)) != int(chat_id):
            continue
        session_key_match = SESSION_KEY_RE.search(line)
        if session_key_match:
            parts = session_key_match.group(1).split(":")
            if len(parts) == 3:
                try:
                    thread_id = int(parts[1])
                except ValueError:
                    thread_id = 0
                if thread_id > 0:
                    return thread_id
        message_thread_match = MESSAGE_THREAD_ID_RE.search(line)
        if message_thread_match:
            thread_id = int(message_thread_match.group(1))
            if thread_id > 0:
                return thread_id
    return None


def apply_runtime_partition_defaults(case: ProbeCase, partition_mode: str | None) -> ProbeCase:
    if partition_mode != "chat_thread_user":
        return case
    if case.thread_id is not None:
        return case
    return replace(case, thread_id=0)


def first_group_chat_id(values: tuple[str, ...]) -> int | None:
    for value in values:
        try:
            parsed = int(value)
        except ValueError:
            continue
        if parsed < 0:
            return parsed
    return None


def profile_chat_ids_as_strings() -> tuple[str, ...]:
    return tuple(str(chat_id) for chat_id in group_profile_chat_ids())


def resolve_allow_chat_ids(cli_allow: tuple[str, ...]) -> tuple[str, ...]:
    if cli_allow:
        return cli_allow

    env_allow = [
        token.strip()
        for token in os.environ.get("OMNI_BLACKBOX_ALLOWED_CHAT_IDS", "").split(",")
        if token.strip()
    ]
    if env_allow:
        return tuple(env_allow)

    env_chat_id = os.environ.get("OMNI_TEST_CHAT_ID", "").strip()
    if env_chat_id:
        return (env_chat_id,)

    profile_chats = profile_chat_ids_as_strings()
    if profile_chats:
        return profile_chats

    return ()


def resolve_group_chat_id(
    *,
    explicit_group_chat_id: int | None,
    allow_chat_ids: tuple[str, ...],
) -> int | None:
    if explicit_group_chat_id is not None:
        return explicit_group_chat_id

    env_group_chat_id = parse_optional_int_env("OMNI_TEST_GROUP_CHAT_ID")
    if env_group_chat_id is not None:
        return env_group_chat_id

    profile_group_chat_id = group_profile_int("OMNI_TEST_CHAT_ID")
    if profile_group_chat_id is not None and profile_group_chat_id < 0:
        return profile_group_chat_id

    return first_group_chat_id(allow_chat_ids)


def resolve_admin_matrix_chat_ids(
    *,
    explicit_matrix_chat_ids: tuple[int, ...],
    group_chat_id: int | None,
    allow_chat_ids: tuple[str, ...],
) -> tuple[int, ...]:
    ordered: list[int] = []
    ordered.extend(explicit_matrix_chat_ids)
    if group_chat_id is not None:
        ordered.append(group_chat_id)

    for profile_chat_id in group_profile_chat_ids():
        if profile_chat_id < 0:
            ordered.append(profile_chat_id)

    for allow_chat_id in allow_chat_ids:
        try:
            parsed = int(allow_chat_id)
        except ValueError:
            continue
        if parsed < 0:
            ordered.append(parsed)
    return dedup_ints(ordered)


def resolve_topic_thread_pair(
    *,
    primary_thread_id: int | None,
    secondary_thread_id: int | None,
) -> tuple[int, int] | None:
    if primary_thread_id is None and secondary_thread_id is None:
        return None
    if primary_thread_id is None:
        raise ValueError(
            "--group-thread-id-b requires --group-thread-id "
            "(or OMNI_TEST_GROUP_THREAD_ID) to be set."
        )

    resolved_secondary = secondary_thread_id
    if resolved_secondary is None:
        resolved_secondary = primary_thread_id + 1
    if int(resolved_secondary) == int(primary_thread_id):
        raise ValueError(
            f"group topic isolation requires distinct thread ids; got both={primary_thread_id}."
        )
    return int(primary_thread_id), int(resolved_secondary)


def build_cases(
    admin_user_id: int | None,
    group_chat_id: int | None,
    group_thread_id: int | None,
) -> tuple[ProbeCase, ...]:
    delegated_admin_target = 1001
    return (
        ProbeCase(
            case_id="session_status_json",
            prompt="/session json",
            event_name="telegram.command.session_status_json.replied",
            suites=("core",),
            extra_args=("--expect-reply-json-field", "json_kind=session_context"),
        ),
        ProbeCase(
            case_id="session_budget_json",
            prompt="/session budget json",
            event_name="telegram.command.session_budget_json.replied",
            suites=("core",),
            extra_args=("--expect-reply-json-field", "json_kind=session_budget"),
        ),
        ProbeCase(
            case_id="session_memory_json",
            prompt="/session memory json",
            event_name="telegram.command.session_memory_json.replied",
            suites=("core",),
            extra_args=("--expect-reply-json-field", "json_kind=session_memory"),
        ),
        ProbeCase(
            case_id="session_feedback_up_json",
            prompt="/session feedback up json",
            event_name="telegram.command.session_feedback_json.replied",
            suites=("core",),
        ),
        ProbeCase(
            case_id="session_reset",
            prompt="/reset",
            event_name="telegram.command.session_reset.replied",
            suites=("control",),
            user_id=admin_user_id,
        ),
        ProbeCase(
            case_id="session_resume_status",
            prompt="/resume status",
            event_name="telegram.command.session_resume_status.replied",
            suites=("control",),
        ),
        ProbeCase(
            case_id="session_resume_drop",
            prompt="/resume drop",
            event_name="telegram.command.session_resume_drop.replied",
            suites=("control",),
            user_id=admin_user_id,
        ),
        ProbeCase(
            case_id="session_reset_snapshot_state",
            prompt="/reset",
            event_name="telegram.command.session_reset.replied",
            suites=("control",),
            user_id=admin_user_id,
            extra_args=(
                "--expect-event",
                "telegram.command.session_reset.snapshot_state",
                "--expect-log-regex",
                'snapshot_state="?none"?',
            ),
        ),
        ProbeCase(
            case_id="session_admin_add",
            prompt=f"/session admin add {delegated_admin_target}",
            event_name="telegram.command.session_admin.replied",
            suites=("admin",),
            user_id=admin_user_id,
            chat_id=group_chat_id,
            thread_id=group_thread_id,
        ),
        ProbeCase(
            case_id="session_admin_list_json",
            prompt="/session admin list json",
            event_name="telegram.command.session_admin_json.replied",
            suites=("admin",),
            user_id=admin_user_id,
            chat_id=group_chat_id,
            thread_id=group_thread_id,
            extra_args=("--expect-reply-json-field", "json_kind=session_admin"),
        ),
        ProbeCase(
            case_id="session_admin_clear",
            prompt="/session admin clear",
            event_name="telegram.command.session_admin.replied",
            suites=("admin",),
            user_id=admin_user_id,
            chat_id=group_chat_id,
            thread_id=group_thread_id,
        ),
    )


def run_case(
    blackbox_script: Path,
    case: ProbeCase,
    username: str,
    allow_chat_ids: tuple[str, ...],
    max_wait: int,
    max_idle_secs: int,
    secret_token: str,
    runtime_partition_mode: str | None,
) -> int:
    print()
    print(f">>> Probe[{case.case_id}]: prompt='{case.prompt}' expect-event='{case.event_name}'")
    cmd = [
        sys.executable,
        str(blackbox_script),
        "--prompt",
        case.prompt,
        "--expect-event",
        case.event_name,
        "--forbid-log-regex",
        FORBIDDEN_LOG_PATTERN,
        "--max-wait",
        str(max_wait),
        "--max-idle-secs",
        str(max_idle_secs),
    ]
    for allowed_chat_id in allow_chat_ids:
        cmd.extend(["--allow-chat-id", allowed_chat_id])
    if case.chat_id is not None:
        cmd.extend(["--chat-id", str(case.chat_id), "--allow-chat-id", str(case.chat_id)])
    if case.thread_id is not None:
        cmd.extend(["--thread-id", str(case.thread_id)])
    if username:
        cmd.extend(["--username", username])
    if case.user_id is not None:
        cmd.extend(["--user-id", str(case.user_id)])
    if runtime_partition_mode:
        cmd.extend(["--session-partition", runtime_partition_mode])
    if secret_token:
        cmd.extend(["--secret-token", secret_token])
    cmd.extend(case.extra_args)

    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def is_transient_matrix_failure(returncode: int) -> bool:
    return returncode in MATRIX_TRANSIENT_EXIT_CODES


def run_case_with_retry(
    *,
    blackbox_script: Path,
    case: ProbeCase,
    username: str,
    allow_chat_ids: tuple[str, ...],
    max_wait: int,
    max_idle_secs: int,
    secret_token: str,
    retries: int,
    backoff_secs: float,
    attempt_records: list[ProbeAttemptRecord] | None = None,
    mode_label: str = "default",
    runtime_partition_mode: str | None = None,
) -> int:
    effective_partition_mode = runtime_partition_mode or resolve_runtime_partition_mode()
    attempts = retries + 1
    for attempt in range(attempts):
        effective_case = apply_runtime_partition_defaults(case, effective_partition_mode)
        started = time.monotonic()
        status = run_case(
            blackbox_script=blackbox_script,
            case=effective_case,
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            runtime_partition_mode=effective_partition_mode,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        retry_scheduled = status != 0 and attempt < retries and is_transient_matrix_failure(status)
        if attempt_records is not None:
            attempt_records.append(
                ProbeAttemptRecord(
                    mode=mode_label,
                    case_id=effective_case.case_id,
                    prompt=effective_case.prompt,
                    event_name=effective_case.event_name,
                    suites=effective_case.suites,
                    chat_id=effective_case.chat_id,
                    user_id=effective_case.user_id,
                    thread_id=effective_case.thread_id,
                    attempt=attempt + 1,
                    max_attempts=attempts,
                    returncode=status,
                    passed=status == 0,
                    duration_ms=duration_ms,
                    retry_scheduled=retry_scheduled,
                )
            )
        if status == 0:
            return 0
        if attempt >= retries or not is_transient_matrix_failure(status):
            return status
        wait_secs = max(0.0, backoff_secs) * (2**attempt)
        print(
            "Transient admin-matrix probe failure: "
            f"case={case.case_id} exit={status} "
            f"retry={attempt + 2}/{attempts} backoff={wait_secs:.1f}s"
        )
        if wait_secs > 0:
            time.sleep(wait_secs)
    return 1


def select_cases(
    cases: tuple[ProbeCase, ...],
    suites: tuple[str, ...],
    case_ids: tuple[str, ...],
) -> list[ProbeCase]:
    if case_ids:
        requested = set(case_ids)
        selected = [case for case in cases if case.case_id in requested]
        missing = sorted(requested - {case.case_id for case in selected})
        if missing:
            raise ValueError(
                "Unknown case id(s): "
                + ", ".join(missing)
                + ". Use --list-cases to inspect available ids."
            )
        return selected

    suite_set = set(suites)
    if "all" in suite_set:
        return list(cases)
    return [case for case in cases if any(suite in suite_set for suite in case.suites)]


def build_admin_list_isolation_case(
    *,
    chat_id: int,
    admin_user_id: int | None,
    thread_id: int | None,
    expected_override_count: int,
) -> ProbeCase:
    return ProbeCase(
        case_id=f"session_admin_list_json_isolation_{chat_id}_{expected_override_count}",
        prompt="/session admin list json",
        event_name="telegram.command.session_admin_json.replied",
        suites=("admin",),
        user_id=admin_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        extra_args=(
            "--expect-reply-json-field",
            "json_kind=session_admin",
            "--expect-reply-json-field",
            f"json_override_admin_count={expected_override_count}",
        ),
    )


def build_admin_list_topic_isolation_case(
    *,
    chat_id: int,
    admin_user_id: int | None,
    thread_id: int,
    expected_override_count: int,
) -> ProbeCase:
    return ProbeCase(
        case_id=(
            "session_admin_list_json_topic_isolation_"
            f"{chat_id}_{thread_id}_{expected_override_count}"
        ),
        prompt="/session admin list json",
        event_name="telegram.command.session_admin_json.replied",
        suites=("admin",),
        user_id=admin_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        extra_args=(
            "--expect-reply-json-field",
            "json_kind=session_admin",
            "--expect-reply-json-field",
            f"json_override_admin_count={expected_override_count}",
        ),
    )


def run_admin_isolation_assertions(
    *,
    blackbox_script: Path,
    matrix_chat_ids: tuple[int, ...],
    admin_user_id: int | None,
    group_thread_id: int | None,
    username: str,
    allow_chat_ids: tuple[str, ...],
    max_wait: int,
    max_idle_secs: int,
    secret_token: str,
    retries: int,
    backoff_secs: float,
    attempt_records: list[ProbeAttemptRecord],
    runtime_partition_mode: str | None,
) -> int:
    print()
    print("=== Running admin recipient-isolation assertions ===")
    if len(matrix_chat_ids) < 2:
        print("Isolation assertions skipped: matrix has fewer than two chat ids.")
        return 0

    # Establish a deterministic zero baseline across all matrix targets.
    for chat_id in matrix_chat_ids:
        clear_case = build_cases(admin_user_id, chat_id, group_thread_id)
        clear_by_id = {case.case_id: case for case in clear_case}
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=clear_by_id["session_admin_clear"],
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_baseline",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
        list_zero_case = build_admin_list_isolation_case(
            chat_id=chat_id,
            admin_user_id=admin_user_id,
            thread_id=group_thread_id,
            expected_override_count=0,
        )
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=list_zero_case,
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_baseline",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status

    for target_chat in matrix_chat_ids:
        scoped_cases = {
            case.case_id: case for case in build_cases(admin_user_id, target_chat, group_thread_id)
        }
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=scoped_cases["session_admin_add"],
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_target",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=build_admin_list_isolation_case(
                chat_id=target_chat,
                admin_user_id=admin_user_id,
                thread_id=group_thread_id,
                expected_override_count=1,
            ),
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_target",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
        for other_chat in matrix_chat_ids:
            if other_chat == target_chat:
                continue
            status = run_case_with_retry(
                blackbox_script=blackbox_script,
                case=build_admin_list_isolation_case(
                    chat_id=other_chat,
                    admin_user_id=admin_user_id,
                    thread_id=group_thread_id,
                    expected_override_count=0,
                ),
                username=username,
                allow_chat_ids=allow_chat_ids,
                max_wait=max_wait,
                max_idle_secs=max_idle_secs,
                secret_token=secret_token,
                retries=retries,
                backoff_secs=backoff_secs,
                attempt_records=attempt_records,
                mode_label="admin_matrix_isolation_cross_check",
                runtime_partition_mode=runtime_partition_mode,
            )
            if status != 0:
                return status
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=scoped_cases["session_admin_clear"],
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_target",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=build_admin_list_isolation_case(
                chat_id=target_chat,
                admin_user_id=admin_user_id,
                thread_id=group_thread_id,
                expected_override_count=0,
            ),
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_matrix_isolation_target",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
    return 0


def run_admin_topic_isolation_assertions(
    *,
    blackbox_script: Path,
    group_chat_id: int,
    admin_user_id: int | None,
    thread_a: int,
    thread_b: int,
    username: str,
    allow_chat_ids: tuple[str, ...],
    max_wait: int,
    max_idle_secs: int,
    secret_token: str,
    retries: int,
    backoff_secs: float,
    attempt_records: list[ProbeAttemptRecord],
    runtime_partition_mode: str | None,
) -> int:
    print()
    print(
        "=== Running admin topic-isolation assertions === "
        f"chat_id={group_chat_id} threads={thread_a},{thread_b}"
    )

    cases_a = {case.case_id: case for case in build_cases(admin_user_id, group_chat_id, thread_a)}
    cases_b = {case.case_id: case for case in build_cases(admin_user_id, group_chat_id, thread_b)}

    for thread_id, clear_case in (
        (thread_a, cases_a["session_admin_clear"]),
        (thread_b, cases_b["session_admin_clear"]),
    ):
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=clear_case,
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_topic_isolation_baseline",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=build_admin_list_topic_isolation_case(
                chat_id=group_chat_id,
                admin_user_id=admin_user_id,
                thread_id=thread_id,
                expected_override_count=0,
            ),
            username=username,
            allow_chat_ids=allow_chat_ids,
            max_wait=max_wait,
            max_idle_secs=max_idle_secs,
            secret_token=secret_token,
            retries=retries,
            backoff_secs=backoff_secs,
            attempt_records=attempt_records,
            mode_label="admin_topic_isolation_baseline",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            return status

    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=cases_a["session_admin_add"],
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_a,
            expected_override_count=1,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_b,
            expected_override_count=0,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_cross_check",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=cases_a["session_admin_clear"],
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_a,
            expected_override_count=0,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status

    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=cases_b["session_admin_add"],
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_b,
            expected_override_count=1,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_a,
            expected_override_count=0,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_cross_check",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=cases_b["session_admin_clear"],
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status
    status = run_case_with_retry(
        blackbox_script=blackbox_script,
        case=build_admin_list_topic_isolation_case(
            chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_id=thread_b,
            expected_override_count=0,
        ),
        username=username,
        allow_chat_ids=allow_chat_ids,
        max_wait=max_wait,
        max_idle_secs=max_idle_secs,
        secret_token=secret_token,
        retries=retries,
        backoff_secs=backoff_secs,
        attempt_records=attempt_records,
        mode_label="admin_topic_isolation_target",
        runtime_partition_mode=runtime_partition_mode,
    )
    if status != 0:
        return status

    return 0


def render_markdown(report: dict[str, object]) -> str:
    summary = report["summary"]
    config = report["config"]
    rows: list[str] = [
        "| Mode | Case | Chat | Attempt | Result | Return | Duration (ms) | Retry Scheduled |",
        "|---|---|---:|---:|---|---:|---:|---|",
    ]
    for attempt in report["attempts"]:
        rows.append(
            "| {mode} | `{case_id}` | {chat} | {attempt}/{max_attempts} | {result} | {rc} | {dur} | {retry} |".format(
                mode=attempt["mode"],
                case_id=attempt["case_id"],
                chat=attempt["chat_id"] if attempt["chat_id"] is not None else "-",
                attempt=attempt["attempt"],
                max_attempts=attempt["max_attempts"],
                result="PASS" if attempt["passed"] else "FAIL",
                rc=attempt["returncode"],
                dur=attempt["duration_ms"],
                retry="yes" if attempt["retry_scheduled"] else "no",
            )
        )
    return "\n".join(
        [
            "# Agent Channel Command Events Report",
            "",
            "## Overview",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- Duration: `{report['duration_ms']} ms`",
            f"- Overall: `{'PASS' if report['overall_passed'] else 'FAIL'}`",
            f"- Attempts: `{summary['passed']}/{summary['total']}` passed",
            f"- Retried attempts: `{summary['retry_scheduled']}`",
            "",
            "## Config",
            f"- suite: `{config['suites']}`",
            f"- runtime_partition_mode: `{config['runtime_partition_mode']}`",
            f"- admin_matrix: `{config['admin_matrix']}`",
            f"- assert_admin_isolation: `{config['assert_admin_isolation']}`",
            f"- assert_admin_topic_isolation: `{config['assert_admin_topic_isolation']}`",
            f"- group_thread_id: `{config['group_thread_id']}`",
            f"- group_thread_id_b: `{config['group_thread_id_b']}`",
            f"- matrix_chat_ids: `{config['matrix_chat_ids']}`",
            f"- max_wait: `{config['max_wait']}`",
            f"- max_idle_secs: `{config['max_idle_secs']}`",
            "",
            "## Attempts",
            *rows,
            "",
        ]
    )


def build_report(
    *,
    args: argparse.Namespace,
    suites: tuple[str, ...],
    allow_chat_ids: tuple[str, ...],
    matrix_chat_ids: tuple[int, ...],
    attempts: list[ProbeAttemptRecord],
    started_dt: datetime,
    started_mono: float,
    exit_code: int,
) -> dict[str, object]:
    finished_dt = datetime.now(UTC)
    duration_ms = int((time.monotonic() - started_mono) * 1000)
    passed = sum(1 for attempt in attempts if attempt.passed)
    failed = len(attempts) - passed
    retry_scheduled = sum(1 for attempt in attempts if attempt.retry_scheduled)
    return {
        "started_at": started_dt.isoformat(),
        "finished_at": finished_dt.isoformat(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "overall_passed": exit_code == 0 and failed == 0 and len(attempts) > 0,
        "summary": {
            "total": len(attempts),
            "passed": passed,
            "failed": failed,
            "retry_scheduled": retry_scheduled,
        },
        "config": {
            "suites": list(suites),
            "cases": list(args.case),
            "runtime_partition_mode": resolve_runtime_partition_mode(),
            "admin_matrix": bool(args.admin_matrix),
            "assert_admin_isolation": bool(args.assert_admin_isolation),
            "assert_admin_topic_isolation": bool(args.assert_admin_topic_isolation),
            "group_thread_id": args.group_thread_id,
            "group_thread_id_b": args.group_thread_id_b,
            "matrix_chat_ids": list(matrix_chat_ids),
            "allow_chat_ids": list(allow_chat_ids),
            "max_wait": int(args.max_wait),
            "max_idle_secs": int(args.max_idle_secs),
            "matrix_retries": int(args.matrix_retries),
            "matrix_backoff_secs": float(args.matrix_backoff_secs),
        },
        "attempts": [asdict(attempt) for attempt in attempts],
    }


def write_outputs(report: dict[str, object], output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.max_wait <= 0:
        print("Error: --max-wait must be a positive integer.", file=sys.stderr)
        return 2
    if args.max_idle_secs <= 0:
        print("Error: --max-idle-secs must be a positive integer.", file=sys.stderr)
        return 2
    if args.matrix_retries < 0:
        print("Error: --matrix-retries must be a non-negative integer.", file=sys.stderr)
        return 2
    if args.matrix_backoff_secs < 0:
        print("Error: --matrix-backoff-secs must be >= 0.", file=sys.stderr)
        return 2
    output_json = Path(args.output_json).expanduser().resolve()
    output_markdown = Path(args.output_markdown).expanduser().resolve()
    started_dt = datetime.now(UTC)
    started_mono = time.monotonic()
    attempts: list[ProbeAttemptRecord] = []
    matrix_chat_ids: tuple[int, ...] = ()
    suites = tuple(args.suite) if args.suite else ("all",)
    exit_code = 0
    secret_token = (args.secret_token or "").strip()
    if not secret_token:
        secret_token = telegram_webhook_secret_token() or ""

    admin_user_id = args.admin_user_id
    if admin_user_id is None:
        try:
            admin_user_id = parse_optional_int_env("OMNI_TEST_ADMIN_USER_ID")
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    if admin_user_id is None:
        try:
            admin_user_id = group_profile_int("OMNI_TEST_USER_ID")
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2

    cli_allow_chat_ids = tuple(
        token.strip() for token in args.allow_chat_id if token and token.strip()
    )
    allow_chat_ids = resolve_allow_chat_ids(cli_allow_chat_ids)

    try:
        group_chat_id = resolve_group_chat_id(
            explicit_group_chat_id=args.group_chat_id,
            allow_chat_ids=allow_chat_ids,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    group_thread_id = args.group_thread_id
    if group_thread_id is None:
        try:
            group_thread_id = parse_optional_int_env("OMNI_TEST_GROUP_THREAD_ID")
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    group_thread_id_b = args.group_thread_id_b
    if group_thread_id_b is None:
        try:
            group_thread_id_b = parse_optional_int_env("OMNI_TEST_GROUP_THREAD_B")
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    try:
        topic_thread_pair = resolve_topic_thread_pair(
            primary_thread_id=group_thread_id,
            secondary_thread_id=group_thread_id_b,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if topic_thread_pair is not None:
        group_thread_id, group_thread_id_b = topic_thread_pair
    args.group_thread_id = group_thread_id
    args.group_thread_id_b = group_thread_id_b

    script_dir = Path(__file__).resolve().parent
    blackbox_script = script_dir / "agent_channel_blackbox.py"
    if not blackbox_script.exists():
        print(f"Error: black-box script not found: {blackbox_script}", file=sys.stderr)
        return 2
    runtime_partition_mode = resolve_runtime_partition_mode()
    if group_thread_id is None and runtime_partition_mode == "chat_thread_user":
        inferred_thread_id = infer_group_thread_id_from_runtime_log(group_chat_id)
        if inferred_thread_id is not None:
            group_thread_id = inferred_thread_id
            args.group_thread_id = inferred_thread_id

    all_cases = build_cases(admin_user_id, group_chat_id, group_thread_id)
    if args.list_cases:
        for case in all_cases:
            print(f"{case.case_id}\t[{','.join(case.suites)}]\t{case.prompt}")
        return 0

    try:
        selected_cases = select_cases(all_cases, suites, tuple(args.case))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if not selected_cases:
        print("No cases selected.", file=sys.stderr)
        return 2
    selected_admin_cases = [case for case in selected_cases if "admin" in case.suites]

    if args.admin_matrix:
        matrix_chat_ids = resolve_admin_matrix_chat_ids(
            explicit_matrix_chat_ids=tuple(args.admin_group_chat_id),
            group_chat_id=group_chat_id,
            allow_chat_ids=allow_chat_ids,
        )
        if not matrix_chat_ids:
            print(
                "Error: --admin-matrix requested but no group chats resolved. "
                "Provide --admin-group-chat-id or set group profile/env chat ids.",
                file=sys.stderr,
            )
            return 2
        matrix_chat_ids = tuple(matrix_chat_ids)

        non_admin_cases = [case for case in selected_cases if "admin" not in case.suites]
        admin_case_ids = [case.case_id for case in selected_cases if "admin" in case.suites]

        if non_admin_cases:
            print(
                "Selected non-admin cases: "
                + ", ".join(f"{case.case_id}[{','.join(case.suites)}]" for case in non_admin_cases)
            )
            for case in non_admin_cases:
                status = run_case_with_retry(
                    blackbox_script=blackbox_script,
                    case=case,
                    username=args.username.strip(),
                    allow_chat_ids=allow_chat_ids,
                    max_wait=args.max_wait,
                    max_idle_secs=args.max_idle_secs,
                    secret_token=secret_token,
                    retries=0,
                    backoff_secs=0,
                    attempt_records=attempts,
                    mode_label="matrix_non_admin",
                    runtime_partition_mode=runtime_partition_mode,
                )
                if status != 0:
                    exit_code = status
                    break

        if exit_code == 0 and admin_case_ids:
            print(
                "Selected admin matrix cases: "
                + ", ".join(admin_case_ids)
                + " | chats="
                + ",".join(str(chat_id) for chat_id in matrix_chat_ids)
            )
            print(
                "Admin matrix retry policy: "
                f"retries={args.matrix_retries} "
                f"transient_exit_codes={sorted(MATRIX_TRANSIENT_EXIT_CODES)} "
                f"base_backoff_secs={max(0.0, args.matrix_backoff_secs):.1f}"
            )
            for matrix_chat_id in matrix_chat_ids:
                print()
                print(f"=== Admin matrix target chat_id={matrix_chat_id} ===")
                scoped_cases_map = {
                    case.case_id: case
                    for case in build_cases(
                        admin_user_id,
                        matrix_chat_id,
                        group_thread_id,
                    )
                }
                scoped_cases = [
                    scoped_cases_map[case_id]
                    for case_id in admin_case_ids
                    if case_id in scoped_cases_map
                ]
                for case in scoped_cases:
                    status = run_case_with_retry(
                        blackbox_script=blackbox_script,
                        case=case,
                        username=args.username.strip(),
                        allow_chat_ids=allow_chat_ids,
                        max_wait=args.max_wait,
                        max_idle_secs=args.max_idle_secs,
                        secret_token=secret_token,
                        retries=args.matrix_retries,
                        backoff_secs=args.matrix_backoff_secs,
                        attempt_records=attempts,
                        mode_label="admin_matrix",
                        runtime_partition_mode=runtime_partition_mode,
                    )
                    if status != 0:
                        exit_code = status
                        break
                if exit_code != 0:
                    break

        if exit_code == 0 and args.assert_admin_isolation and admin_case_ids:
            isolation_status = run_admin_isolation_assertions(
                blackbox_script=blackbox_script,
                matrix_chat_ids=matrix_chat_ids,
                admin_user_id=admin_user_id,
                group_thread_id=group_thread_id,
                username=args.username.strip(),
                allow_chat_ids=allow_chat_ids,
                max_wait=args.max_wait,
                max_idle_secs=args.max_idle_secs,
                secret_token=secret_token,
                retries=args.matrix_retries,
                backoff_secs=args.matrix_backoff_secs,
                attempt_records=attempts,
                runtime_partition_mode=runtime_partition_mode,
            )
            if isolation_status != 0:
                exit_code = isolation_status

        if exit_code == 0 and args.assert_admin_topic_isolation and admin_case_ids:
            if group_chat_id is None:
                print(
                    "Error: --assert-admin-topic-isolation requires a resolved group chat id "
                    "(--group-chat-id or OMNI_TEST_GROUP_CHAT_ID).",
                    file=sys.stderr,
                )
                return 2
            if topic_thread_pair is None:
                print(
                    "Error: --assert-admin-topic-isolation requires --group-thread-id "
                    "(or OMNI_TEST_GROUP_THREAD_ID).",
                    file=sys.stderr,
                )
                return 2
            thread_a, thread_b = topic_thread_pair
            topic_status = run_admin_topic_isolation_assertions(
                blackbox_script=blackbox_script,
                group_chat_id=group_chat_id,
                admin_user_id=admin_user_id,
                thread_a=thread_a,
                thread_b=thread_b,
                username=args.username.strip(),
                allow_chat_ids=allow_chat_ids,
                max_wait=args.max_wait,
                max_idle_secs=args.max_idle_secs,
                secret_token=secret_token,
                retries=args.matrix_retries,
                backoff_secs=args.matrix_backoff_secs,
                attempt_records=attempts,
                runtime_partition_mode=runtime_partition_mode,
            )
            if topic_status != 0:
                exit_code = topic_status

        report = build_report(
            args=args,
            suites=suites,
            allow_chat_ids=allow_chat_ids,
            matrix_chat_ids=matrix_chat_ids,
            attempts=attempts,
            started_dt=started_dt,
            started_mono=started_mono,
            exit_code=exit_code,
        )
        write_outputs(report, output_json, output_markdown)
        if exit_code == 0:
            print()
            print("All command event probes passed.")
        else:
            print()
            print(f"Command event probes failed with exit code {exit_code}.")
        print(f"JSON report: {output_json}")
        print(f"Markdown report: {output_markdown}")
        return exit_code

    runnable_cases: list[ProbeCase] = []
    skipped_admin_cases: list[str] = []
    for case in selected_cases:
        if "admin" in case.suites and case.chat_id is None:
            skipped_admin_cases.append(case.case_id)
            continue
        runnable_cases.append(case)

    if skipped_admin_cases:
        print(
            "Skipping admin suite cases because no group chat id was provided "
            "(`--group-chat-id`, `OMNI_TEST_GROUP_CHAT_ID`, allowlist/group profile): "
            + ", ".join(skipped_admin_cases)
        )
    if not runnable_cases:
        print("No runnable cases left after filtering.", file=sys.stderr)
        return 2

    print(
        "Selected cases: "
        + ", ".join(f"{case.case_id}[{','.join(case.suites)}]" for case in runnable_cases)
    )

    for case in runnable_cases:
        status = run_case_with_retry(
            blackbox_script=blackbox_script,
            case=case,
            username=args.username.strip(),
            allow_chat_ids=allow_chat_ids,
            max_wait=args.max_wait,
            max_idle_secs=args.max_idle_secs,
            secret_token=secret_token,
            retries=0,
            backoff_secs=0,
            attempt_records=attempts,
            mode_label="default",
            runtime_partition_mode=runtime_partition_mode,
        )
        if status != 0:
            exit_code = status
            break

    if exit_code == 0 and args.assert_admin_topic_isolation and selected_admin_cases:
        if group_chat_id is None:
            print(
                "Error: --assert-admin-topic-isolation requires a resolved group chat id "
                "(--group-chat-id or OMNI_TEST_GROUP_CHAT_ID).",
                file=sys.stderr,
            )
            return 2
        if topic_thread_pair is None:
            print(
                "Error: --assert-admin-topic-isolation requires --group-thread-id "
                "(or OMNI_TEST_GROUP_THREAD_ID).",
                file=sys.stderr,
            )
            return 2
        thread_a, thread_b = topic_thread_pair
        topic_status = run_admin_topic_isolation_assertions(
            blackbox_script=blackbox_script,
            group_chat_id=group_chat_id,
            admin_user_id=admin_user_id,
            thread_a=thread_a,
            thread_b=thread_b,
            username=args.username.strip(),
            allow_chat_ids=allow_chat_ids,
            max_wait=args.max_wait,
            max_idle_secs=args.max_idle_secs,
            secret_token=secret_token,
            retries=args.matrix_retries,
            backoff_secs=args.matrix_backoff_secs,
            attempt_records=attempts,
            runtime_partition_mode=runtime_partition_mode,
        )
        if topic_status != 0:
            exit_code = topic_status

    report = build_report(
        args=args,
        suites=suites,
        allow_chat_ids=allow_chat_ids,
        matrix_chat_ids=matrix_chat_ids,
        attempts=attempts,
        started_dt=started_dt,
        started_mono=started_mono,
        exit_code=exit_code,
    )
    write_outputs(report, output_json, output_markdown)
    if exit_code == 0:
        print()
        print("All command event probes passed.")
    else:
        print()
        print(f"Command event probes failed with exit code {exit_code}.")
    print(f"JSON report: {output_json}")
    print(f"Markdown report: {output_markdown}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
