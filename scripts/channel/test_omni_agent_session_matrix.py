#!/usr/bin/env python3
"""
Session matrix black-box probe for Telegram webhook runtime.

Step 3 validation target:
1) Baseline concurrent dual-session handling.
2) Cross-session reset/resume sequence.
3) Structured JSON/Markdown report for acceptance and debugging.
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
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from test_config_resolver import (
        group_profile_int,
        normalize_telegram_session_partition_mode,
        session_ids_from_runtime_log,
        session_partition_mode_from_runtime_log,
        telegram_session_partition_mode,
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
    group_profile_int = _resolver_module.group_profile_int
    normalize_telegram_session_partition_mode = (
        _resolver_module.normalize_telegram_session_partition_mode
    )
    session_ids_from_runtime_log = _resolver_module.session_ids_from_runtime_log
    session_partition_mode_from_runtime_log = (
        _resolver_module.session_partition_mode_from_runtime_log
    )
    telegram_session_partition_mode = _resolver_module.telegram_session_partition_mode
    username_from_runtime_log = _resolver_module.username_from_runtime_log
    username_from_settings = _resolver_module.username_from_settings


@dataclass(frozen=True)
class ProbeConfig:
    max_wait: int
    max_idle_secs: int
    webhook_url: str
    log_file: Path
    chat_id: int
    chat_b: int
    chat_c: int
    user_a: int
    user_b: int
    user_c: int
    username: str | None
    thread_a: int | None
    thread_b: int | None
    thread_c: int | None
    mixed_plain_prompt: str
    secret_token: str | None
    output_json: Path
    output_markdown: Path
    forbid_log_regexes: tuple[str, ...]
    session_partition: str | None = None


@dataclass(frozen=True)
class MatrixStep:
    name: str
    prompt: str
    chat_id: int
    event: str | None
    user_id: int
    thread_id: int | None
    expect_reply_json_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepResult:
    name: str
    kind: str
    session_key: str | None
    prompt: str | None
    event: str | None
    command: tuple[str, ...]
    returncode: int
    duration_ms: int
    passed: bool
    stdout_tail: str
    stderr_tail: str


RESTART_NOISE_MARKERS = (
    "Telegram webhook listening on 0.0.0.0:8081/telegram/webhook",
    "Webhook dedup backend:",
    "Session commands: /session [json]",
    "mcp pool client connect attempt started",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run session isolation matrix against local Telegram webhook runtime "
            "and emit structured JSON/Markdown reports."
        )
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "35")),
        help="Max wait per probe in seconds (default: 35).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "25")),
        help="Max idle seconds per probe (default: 25).",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get(
            "OMNI_WEBHOOK_URL",
            f"http://127.0.0.1:{os.environ.get('WEBHOOK_PORT', '8081')}/telegram/webhook",
        ),
        help="Webhook URL.",
    )
    parser.add_argument(
        "--log-file",
        default=os.environ.get("OMNI_CHANNEL_LOG_FILE", ".run/logs/omni-agent-webhook.log"),
        help="Runtime log file path.",
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        default=int(os.environ["OMNI_TEST_CHAT_ID"]) if "OMNI_TEST_CHAT_ID" in os.environ else None,
        help="Telegram chat id (default: inferred from env/log).",
    )
    parser.add_argument(
        "--chat-b",
        type=int,
        default=int(os.environ["OMNI_TEST_CHAT_B"]) if "OMNI_TEST_CHAT_B" in os.environ else None,
        help="Session B chat id (default: --chat-id or $OMNI_TEST_CHAT_B).",
    )
    parser.add_argument(
        "--chat-c",
        type=int,
        default=int(os.environ["OMNI_TEST_CHAT_C"]) if "OMNI_TEST_CHAT_C" in os.environ else None,
        help="Session C chat id for mixed concurrency probe (default: --chat-id or $OMNI_TEST_CHAT_C).",
    )
    parser.add_argument(
        "--user-a",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_ID"]) if "OMNI_TEST_USER_ID" in os.environ else None,
        help="Session A user id (default: inferred from env/log).",
    )
    parser.add_argument(
        "--user-b",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_B"]) if "OMNI_TEST_USER_B" in os.environ else None,
        help="Session B user id (default: user-a + 1 or $OMNI_TEST_USER_B).",
    )
    parser.add_argument(
        "--user-c",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_C"]) if "OMNI_TEST_USER_C" in os.environ else None,
        help="Session C user id for mixed concurrency probe (default: user-a + 2 or $OMNI_TEST_USER_C).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME"),
        help="Telegram username for allowlist checks.",
    )
    parser.add_argument(
        "--thread-a",
        type=int,
        default=int(os.environ["OMNI_TEST_THREAD_ID"])
        if "OMNI_TEST_THREAD_ID" in os.environ
        else None,
        help="Optional thread id for session A.",
    )
    parser.add_argument(
        "--thread-b",
        type=int,
        default=int(os.environ["OMNI_TEST_THREAD_B"])
        if "OMNI_TEST_THREAD_B" in os.environ
        else None,
        help=(
            "Optional thread id for session B "
            "(default: thread-a + 1 when thread-a is provided, or $OMNI_TEST_THREAD_B)."
        ),
    )
    parser.add_argument(
        "--thread-c",
        type=int,
        default=int(os.environ["OMNI_TEST_THREAD_C"])
        if "OMNI_TEST_THREAD_C" in os.environ
        else None,
        help="Optional thread id for session C mixed probe (default: $OMNI_TEST_THREAD_C).",
    )
    parser.add_argument(
        "--mixed-plain-prompt",
        default="Please reply with one short sentence for mixed concurrency probe.",
        help="Plain prompt used in mixed concurrency batch.",
    )
    parser.add_argument(
        "--secret-token",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
        help="Webhook secret header value.",
    )
    parser.add_argument(
        "--output-json",
        default=".run/reports/agent-channel-session-matrix.json",
        help="Structured output JSON path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=".run/reports/agent-channel-session-matrix.md",
        help="Structured output Markdown path.",
    )
    parser.add_argument(
        "--forbid-log-regex",
        action="append",
        default=["tools/call: Mcp error", "Telegram sendMessage failed"],
        help="Regex that must not appear in probe logs (repeatable).",
    )
    return parser.parse_args()


def expected_session_keys(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    session_partition: str | None = None,
) -> tuple[str, ...]:
    partition = normalize_telegram_session_partition_mode(session_partition)
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
    session_partition: str | None = None,
) -> str:
    return expected_session_keys(chat_id, user_id, thread_id, session_partition)[0]


def resolve_runtime_partition_mode(log_file: Path) -> str | None:
    override = os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", "").strip()
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(log_file)
    if mode_from_log:
        return mode_from_log
    return telegram_session_partition_mode()


def session_context_result_fields(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    session_partition: str | None = None,
) -> tuple[str, ...]:
    session_key = expected_session_key(chat_id, user_id, thread_id, session_partition)
    return (
        "json_kind=session_context",
        f"json_logical_session_id=telegram:{session_key}",
        f"json_partition_key={session_key}",
    )


def session_memory_result_fields() -> tuple[str, ...]:
    return ("json_kind=session_memory",)


def _tail_text(value: str, limit_lines: int = 30) -> str:
    lines = value.splitlines()
    if len(lines) <= limit_lines:
        return value
    return "\n".join(lines[-limit_lines:])


def build_config(args: argparse.Namespace) -> ProbeConfig:
    if args.max_wait <= 0:
        raise ValueError("--max-wait must be a positive integer.")
    if args.max_idle_secs <= 0:
        raise ValueError("--max-idle-secs must be a positive integer.")

    log_file = Path(args.log_file)
    chat_id = args.chat_id
    if chat_id is None:
        chat_id = group_profile_int("OMNI_TEST_CHAT_ID")

    user_a = args.user_a
    if user_a is None:
        user_a = group_profile_int("OMNI_TEST_USER_ID")

    thread_a = args.thread_a

    if chat_id is None or user_a is None:
        inferred_chat, inferred_user, inferred_thread = session_ids_from_runtime_log(log_file)
        if chat_id is None:
            chat_id = inferred_chat
        if user_a is None:
            user_a = inferred_user
        if thread_a is None:
            thread_a = inferred_thread

    if chat_id is None or user_a is None:
        raise ValueError(
            "chat/user are required. Use --chat-id/--user-a "
            "(or OMNI_TEST_CHAT_ID/OMNI_TEST_USER_ID). "
            "Tip: send one Telegram message first so session_key can be inferred from logs."
        )

    chat_b = args.chat_b
    if chat_b is None:
        chat_b = group_profile_int("OMNI_TEST_CHAT_B")
    if chat_b is None:
        chat_b = int(chat_id)

    chat_c = args.chat_c
    if chat_c is None:
        chat_c = group_profile_int("OMNI_TEST_CHAT_C")
    if chat_c is None:
        chat_c = int(chat_id)

    thread_b = args.thread_b
    if thread_a is not None and thread_b is None:
        thread_b = int(thread_a) + 1
    thread_c = args.thread_c
    runtime_partition_mode = resolve_runtime_partition_mode(log_file)
    if runtime_partition_mode == "chat_thread_user":
        if thread_a is None:
            thread_a = 0
        if thread_b is None:
            thread_b = 0
        if thread_c is None:
            thread_c = 0

    user_b = args.user_b
    if user_b is None:
        user_b = group_profile_int("OMNI_TEST_USER_B")
    if user_b is None:
        if (
            int(chat_b) == int(chat_id)
            and thread_a is not None
            and thread_b is not None
            and int(thread_a) != int(thread_b)
        ):
            user_b = int(user_a)
        else:
            user_b = int(user_a) + 1
    user_c = args.user_c
    if user_c is None:
        user_c = group_profile_int("OMNI_TEST_USER_C")
    if user_c is None:
        user_c = int(user_a) + 2

    key_a = expected_session_key(int(chat_id), int(user_a), thread_a, runtime_partition_mode)
    key_b = expected_session_key(int(chat_b), int(user_b), thread_b, runtime_partition_mode)
    key_c = expected_session_key(int(chat_c), int(user_c), thread_c, runtime_partition_mode)
    unique_keys = {key_a, key_b, key_c}
    if len(unique_keys) != 3:
        raise ValueError(
            "session matrix requires three distinct session identities "
            f"(got keys: {key_a}, {key_b}, {key_c}). Adjust chat/user/thread parameters."
        )

    username = args.username.strip() if args.username else None
    if not username:
        username = username_from_settings()
    if not username:
        username = username_from_runtime_log(log_file)

    return ProbeConfig(
        max_wait=int(args.max_wait),
        max_idle_secs=int(args.max_idle_secs),
        webhook_url=args.webhook_url,
        log_file=log_file,
        chat_id=int(chat_id),
        chat_b=int(chat_b),
        chat_c=int(chat_c),
        user_a=int(user_a),
        user_b=int(user_b),
        user_c=int(user_c),
        username=username,
        thread_a=thread_a,
        thread_b=thread_b,
        thread_c=thread_c,
        mixed_plain_prompt=args.mixed_plain_prompt.strip(),
        secret_token=(args.secret_token.strip() if args.secret_token else None),
        output_json=Path(args.output_json),
        output_markdown=Path(args.output_markdown),
        forbid_log_regexes=tuple(args.forbid_log_regex),
        session_partition=runtime_partition_mode,
    )


def build_matrix_steps(cfg: ProbeConfig) -> tuple[MatrixStep, ...]:
    return (
        MatrixStep(
            name="reset_session_a",
            prompt="/reset",
            chat_id=cfg.chat_id,
            event="telegram.command.session_reset.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
        ),
        MatrixStep(
            name="session_status_session_a_after_reset",
            prompt="/session json",
            chat_id=cfg.chat_id,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_id, cfg.user_a, cfg.thread_a, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="session_memory_session_a_after_reset",
            prompt="/session memory json",
            chat_id=cfg.chat_id,
            event="telegram.command.session_memory_json.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
            expect_reply_json_fields=session_memory_result_fields(),
        ),
        MatrixStep(
            name="resume_status_session_a",
            prompt="/resume status",
            chat_id=cfg.chat_id,
            event="telegram.command.session_resume_status.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
        ),
        MatrixStep(
            name="session_status_session_b_after_a_reset",
            prompt="/session json",
            chat_id=cfg.chat_b,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_b, cfg.user_b, cfg.thread_b, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="session_memory_session_b_after_a_reset",
            prompt="/session memory json",
            chat_id=cfg.chat_b,
            event="telegram.command.session_memory_json.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
            expect_reply_json_fields=session_memory_result_fields(),
        ),
        MatrixStep(
            name="session_status_session_c_after_a_reset",
            prompt="/session json",
            chat_id=cfg.chat_c,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_c,
            thread_id=cfg.thread_c,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_c, cfg.user_c, cfg.thread_c, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="session_memory_session_c_after_a_reset",
            prompt="/session memory json",
            chat_id=cfg.chat_c,
            event="telegram.command.session_memory_json.replied",
            user_id=cfg.user_c,
            thread_id=cfg.thread_c,
            expect_reply_json_fields=session_memory_result_fields(),
        ),
        MatrixStep(
            name="reset_session_b",
            prompt="/reset",
            chat_id=cfg.chat_b,
            event="telegram.command.session_reset.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
        ),
        MatrixStep(
            name="session_status_session_b_after_reset",
            prompt="/session json",
            chat_id=cfg.chat_b,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_b, cfg.user_b, cfg.thread_b, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="resume_status_session_b",
            prompt="/resume status",
            chat_id=cfg.chat_b,
            event="telegram.command.session_resume_status.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
        ),
        MatrixStep(
            name="session_status_session_a_after_b_reset",
            prompt="/session json",
            chat_id=cfg.chat_id,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_id, cfg.user_a, cfg.thread_a, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="session_status_session_c_after_b_reset",
            prompt="/session json",
            chat_id=cfg.chat_c,
            event="telegram.command.session_status_json.replied",
            user_id=cfg.user_c,
            thread_id=cfg.thread_c,
            expect_reply_json_fields=session_context_result_fields(
                cfg.chat_c, cfg.user_c, cfg.thread_c, cfg.session_partition
            ),
        ),
        MatrixStep(
            name="resume_drop_session_a",
            prompt="/resume drop",
            chat_id=cfg.chat_id,
            event="telegram.command.session_resume_drop.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
        ),
        MatrixStep(
            name="resume_drop_session_b",
            prompt="/resume drop",
            chat_id=cfg.chat_b,
            event="telegram.command.session_resume_drop.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
        ),
    )


def _run_command(cmd: list[str]) -> tuple[int, int, str, str]:
    started = time.monotonic()
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration_ms = int((time.monotonic() - started) * 1000)
    return completed.returncode, duration_ms, completed.stdout, completed.stderr


def should_retry_on_restart_noise(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        return False
    payload = f"{stdout}\n{stderr}"
    return any(marker in payload for marker in RESTART_NOISE_MARKERS)


def run_command_with_restart_retry(
    cmd: list[str],
    *,
    max_restart_retries: int = 1,
) -> tuple[int, int, str, str]:
    attempts = 0
    total_duration_ms = 0
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    while True:
        attempts += 1
        returncode, duration_ms, stdout, stderr = _run_command(cmd)
        total_duration_ms += duration_ms
        stdout_parts.append(stdout)
        stderr_parts.append(stderr)
        can_retry = attempts <= max_restart_retries and should_retry_on_restart_noise(
            returncode, stdout, stderr
        )
        if not can_retry:
            break
        stdout_parts.append(
            "[matrix-retry] detected webhook restart noise, retrying the same step once.\n"
        )
        time.sleep(0.2)
    return returncode, total_duration_ms, "".join(stdout_parts), "".join(stderr_parts)


def run_concurrent_step(
    script_dir: Path,
    cfg: ProbeConfig,
    *,
    name: str,
    chat_a: int,
    user_a: int,
    thread_a: int | None,
    chat_b: int,
    user_b: int,
    thread_b: int | None,
    prompt: str = "/session json",
    allow_send_failure: bool = False,
) -> StepResult:
    session_a = expected_session_key(chat_a, user_a, thread_a, cfg.session_partition)
    session_b = expected_session_key(chat_b, user_b, thread_b, cfg.session_partition)
    cmd = [
        sys.executable,
        str(script_dir / "test_omni_agent_concurrent_sessions.py"),
        "--max-wait",
        str(cfg.max_wait),
        "--webhook-url",
        cfg.webhook_url,
        "--log-file",
        str(cfg.log_file),
        "--chat-id",
        str(chat_a),
        "--chat-b",
        str(chat_b),
        "--user-a",
        str(user_a),
        "--user-b",
        str(user_b),
        "--prompt",
        prompt,
    ]
    if thread_a is not None:
        cmd.extend(["--thread-a", str(thread_a)])
    if thread_b is not None:
        cmd.extend(["--thread-b", str(thread_b)])
    if cfg.username:
        cmd.extend(["--username", cfg.username])
    if cfg.secret_token:
        cmd.extend(["--secret-token", cfg.secret_token])
    if cfg.session_partition:
        cmd.extend(["--session-partition", cfg.session_partition])
    if allow_send_failure:
        cmd.append("--allow-send-failure")
    for pattern in cfg.forbid_log_regexes:
        cmd.extend(["--forbid-log-regex", pattern])

    returncode, duration_ms, stdout, stderr = run_command_with_restart_retry(cmd)
    passed = returncode == 0
    return StepResult(
        name=name,
        kind="concurrent",
        session_key=f"{session_a} | {session_b}",
        prompt=f"{prompt} (concurrent)",
        event="telegram.command.session_status_json.replied",
        command=tuple(cmd),
        returncode=returncode,
        duration_ms=duration_ms,
        passed=passed,
        stdout_tail=_tail_text(stdout),
        stderr_tail=_tail_text(stderr),
    )


def run_blackbox_step(script_dir: Path, cfg: ProbeConfig, step: MatrixStep) -> StepResult:
    session_key = expected_session_key(
        step.chat_id,
        step.user_id,
        step.thread_id,
        cfg.session_partition,
    )
    escaped_key = re.escape(session_key)
    allowed_chat_ids = tuple(dict.fromkeys((cfg.chat_id, cfg.chat_b, cfg.chat_c)))
    cmd = [
        sys.executable,
        str(script_dir / "agent_channel_blackbox.py"),
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
        str(step.chat_id),
        "--user-id",
        str(step.user_id),
        "--expect-log-regex",
        rf'session_key="?{escaped_key}"?',
    ]
    for allowed_chat_id in allowed_chat_ids:
        cmd.extend(["--allow-chat-id", str(allowed_chat_id)])
    if step.event is not None:
        cmd.extend(["--expect-event", step.event])
    if step.thread_id is not None:
        cmd.extend(["--thread-id", str(step.thread_id)])
    if cfg.username:
        cmd.extend(["--username", cfg.username])
    if cfg.secret_token:
        cmd.extend(["--secret-token", cfg.secret_token])
    if cfg.session_partition:
        cmd.extend(["--session-partition", cfg.session_partition])
    for field in step.expect_reply_json_fields:
        cmd.extend(["--expect-reply-json-field", field])
    for pattern in cfg.forbid_log_regexes:
        cmd.extend(["--forbid-log-regex", pattern])

    returncode, duration_ms, stdout, stderr = run_command_with_restart_retry(cmd)
    passed = returncode == 0
    return StepResult(
        name=step.name,
        kind="blackbox",
        session_key=session_key,
        prompt=step.prompt,
        event=step.event,
        command=tuple(cmd),
        returncode=returncode,
        duration_ms=duration_ms,
        passed=passed,
        stdout_tail=_tail_text(stdout),
        stderr_tail=_tail_text(stderr),
    )


def build_mixed_concurrency_steps(cfg: ProbeConfig) -> tuple[MatrixStep, ...]:
    return (
        MatrixStep(
            name="mixed_reset_session_a",
            prompt="/reset",
            chat_id=cfg.chat_id,
            event="telegram.command.session_reset.replied",
            user_id=cfg.user_a,
            thread_id=cfg.thread_a,
        ),
        MatrixStep(
            name="mixed_resume_status_session_b",
            prompt="/resume status",
            chat_id=cfg.chat_b,
            event="telegram.command.session_resume_status.replied",
            user_id=cfg.user_b,
            thread_id=cfg.thread_b,
        ),
        MatrixStep(
            name="mixed_plain_session_c",
            prompt=cfg.mixed_plain_prompt,
            chat_id=cfg.chat_c,
            event=None,
            user_id=cfg.user_c,
            thread_id=cfg.thread_c,
        ),
    )


def run_mixed_concurrency_batch(script_dir: Path, cfg: ProbeConfig) -> list[StepResult]:
    from concurrent.futures import ThreadPoolExecutor

    def _run_with_stagger(step: MatrixStep, delay_secs: float) -> StepResult:
        if delay_secs > 0:
            time.sleep(delay_secs)
        return run_blackbox_step(script_dir, cfg, step)

    steps = build_mixed_concurrency_steps(cfg)
    with ThreadPoolExecutor(max_workers=len(steps)) as pool:
        futures = [
            pool.submit(_run_with_stagger, step, index * 0.02) for index, step in enumerate(steps)
        ]
        return [future.result() for future in futures]


def render_markdown(report: dict[str, object]) -> str:
    summary = report["summary"]
    config = report["config"]
    rows: list[str] = [
        "| Step | Kind | Session | Prompt | Event | Result | Duration (ms) |",
        "|---|---|---|---|---|---|---:|",
    ]
    for step in report["steps"]:
        status = "PASS" if step["passed"] else "FAIL"
        rows.append(
            "| {name} | {kind} | `{session}` | `{prompt}` | `{event}` | {status} | {duration} |".format(
                name=step["name"],
                kind=step["kind"],
                session=step["session_key"] or "-",
                prompt=step["prompt"] or "-",
                event=step["event"] or "-",
                status=status,
                duration=step["duration_ms"],
            )
        )
    failure_blocks = [
        "\n".join(
            [
                f"### {step['name']}",
                "",
                "```text",
                (step["stderr_tail"] or step["stdout_tail"] or "(no output)"),
                "```",
            ]
        )
        for step in report["steps"]
        if not step["passed"]
    ]
    if not failure_blocks:
        failure_blocks = ["- None"]

    return "\n".join(
        [
            "# Agent Channel Session Matrix Report",
            "",
            "## Overview",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- Duration: `{report['duration_ms']} ms`",
            f"- Overall: `{'PASS' if report['overall_passed'] else 'FAIL'}`",
            f"- Steps: `{summary['passed']}/{summary['total']}` passed",
            "",
            "## Session Inputs",
            f"- chat_id: `{config['chat_id']}`",
            f"- chat_b: `{config['chat_b']}`",
            f"- chat_c: `{config['chat_c']}`",
            f"- user_a: `{config['user_a']}`",
            f"- user_b: `{config['user_b']}`",
            f"- user_c: `{config['user_c']}`",
            f"- thread_a: `{config['thread_a']}`",
            f"- thread_b: `{config['thread_b']}`",
            f"- thread_c: `{config['thread_c']}`",
            f"- log_file: `{config['log_file']}`",
            "",
            "## Step Results",
            *rows,
            "",
            "## Failure Tails",
            *failure_blocks,
            "",
        ]
    )


def run_matrix(cfg: ProbeConfig) -> tuple[bool, dict[str, object]]:
    script_dir = Path(__file__).resolve().parent
    started_dt = datetime.now(UTC)
    started_mono = time.monotonic()
    results: list[StepResult] = []

    baseline_name = "concurrent_baseline_same_chat"
    baseline_chat_b = cfg.chat_id
    baseline_user_b = cfg.user_b
    baseline_thread_b = cfg.thread_b
    baseline_allow_send_failure = False
    baseline_is_cross_group = False

    if cfg.session_partition == "chat":
        baseline_name = "concurrent_baseline_cross_chat"
        if cfg.chat_b != cfg.chat_id:
            baseline_chat_b = cfg.chat_b
            baseline_user_b = cfg.user_b
            baseline_thread_b = cfg.thread_b
        else:
            baseline_chat_b = cfg.chat_c
            baseline_user_b = cfg.user_c
            baseline_thread_b = cfg.thread_c
        baseline_is_cross_group = True

    results.append(
        run_concurrent_step(
            script_dir,
            cfg,
            name=baseline_name,
            chat_a=cfg.chat_id,
            user_a=cfg.user_a,
            thread_a=cfg.thread_a,
            chat_b=baseline_chat_b,
            user_b=baseline_user_b,
            thread_b=baseline_thread_b,
            prompt="/session json",
            allow_send_failure=baseline_allow_send_failure,
        )
    )
    if not results[-1].passed:
        return False, build_report(cfg, results, started_dt, started_mono)

    if cfg.chat_b != cfg.chat_id and not baseline_is_cross_group:
        results.append(
            run_concurrent_step(
                script_dir,
                cfg,
                name="concurrent_cross_group",
                chat_a=cfg.chat_id,
                user_a=cfg.user_a,
                thread_a=cfg.thread_a,
                chat_b=cfg.chat_b,
                user_b=cfg.user_b,
                thread_b=cfg.thread_b,
                prompt="/session json",
                allow_send_failure=True,
            )
        )
        if not results[-1].passed:
            return False, build_report(cfg, results, started_dt, started_mono)

    if (
        cfg.session_partition == "chat_thread_user"
        and cfg.thread_a is not None
        and cfg.thread_b is not None
        and cfg.thread_a != cfg.thread_b
    ):
        results.append(
            run_concurrent_step(
                script_dir,
                cfg,
                name="concurrent_cross_thread_same_user",
                chat_a=cfg.chat_id,
                user_a=cfg.user_a,
                thread_a=cfg.thread_a,
                chat_b=cfg.chat_id,
                user_b=cfg.user_a,
                thread_b=cfg.thread_b,
                prompt="/session json",
                allow_send_failure=False,
            )
        )
        if not results[-1].passed:
            return False, build_report(cfg, results, started_dt, started_mono)

    for step in build_matrix_steps(cfg):
        result = run_blackbox_step(script_dir, cfg, step)
        results.append(result)
        if not result.passed:
            break

    if all(step.passed for step in results):
        for mixed_result in run_mixed_concurrency_batch(script_dir, cfg):
            results.append(mixed_result)
            if not mixed_result.passed:
                break

    overall_passed = all(step.passed for step in results)
    return overall_passed, build_report(cfg, results, started_dt, started_mono)


def build_report(
    cfg: ProbeConfig,
    results: list[StepResult],
    started_dt: datetime,
    started_mono: float,
) -> dict[str, object]:
    finished_dt = datetime.now(UTC)
    duration_ms = int((time.monotonic() - started_mono) * 1000)
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    report: dict[str, object] = {
        "started_at": started_dt.isoformat(),
        "finished_at": finished_dt.isoformat(),
        "duration_ms": duration_ms,
        "overall_passed": failed == 0 and len(results) > 0,
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "config": {
            "webhook_url": cfg.webhook_url,
            "log_file": str(cfg.log_file),
            "chat_id": cfg.chat_id,
            "chat_b": cfg.chat_b,
            "chat_c": cfg.chat_c,
            "user_a": cfg.user_a,
            "user_b": cfg.user_b,
            "user_c": cfg.user_c,
            "thread_a": cfg.thread_a,
            "thread_b": cfg.thread_b,
            "thread_c": cfg.thread_c,
            "mixed_plain_prompt": cfg.mixed_plain_prompt,
            "forbid_log_regexes": list(cfg.forbid_log_regexes),
        },
        "steps": [asdict(result) for result in results],
    }
    return report


def write_outputs(report: dict[str, object], output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    try:
        cfg = build_config(parse_args())
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    passed, report = run_matrix(cfg)
    write_outputs(report, cfg.output_json, cfg.output_markdown)

    print("Session matrix completed.")
    print(f"  overall={'PASS' if passed else 'FAIL'}")
    print(
        "  steps={passed}/{total}".format(
            passed=report["summary"]["passed"], total=report["summary"]["total"]
        )
    )
    print(f"  json_report={cfg.output_json}")
    print(f"  markdown_report={cfg.output_markdown}")

    if not passed:
        failed_steps = [step["name"] for step in report["steps"] if not step["passed"]]
        print(f"  failed_steps={failed_steps}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
