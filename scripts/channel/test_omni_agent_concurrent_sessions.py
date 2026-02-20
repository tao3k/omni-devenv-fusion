#!/usr/bin/env python3
"""
Concurrent multi-session black-box probe for Telegram webhook runtime.

This probe sends the same command concurrently to two distinct session identities
(same chat, different user ids by default; or different chats with same user) and verifies:
  - dedup accepted events for both update ids
  - parsed inbound session_key for both sessions
  - command reply event for both sessions
  - no duplicate_detected for these new update ids
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

try:
    from test_config_resolver import (
        group_profile_int,
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
    group_profile_int = _resolver_module.group_profile_int
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

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
SESSION_KEY_RE = re.compile(
    r"\bsession_key(?:\s*=\s*|\x1b\[2m=\x1b\[0m)(?:\"|')?([-\d:]+)(?:\"|')?"
)


@dataclass(frozen=True)
class ProbeConfig:
    max_wait: int
    webhook_url: str
    log_file: Path
    chat_id: int
    chat_b: int
    user_a: int
    user_b: int
    username: str | None
    thread_a: int | None
    thread_b: int | None
    secret_token: str | None
    prompt: str
    forbid_log_regexes: tuple[str, ...]
    allow_send_failure: bool
    session_partition: str | None = None


@dataclass(frozen=True)
class Observation:
    accepted_a: int
    accepted_b: int
    dedup_fail_open_a: int
    dedup_fail_open_b: int
    duplicate_a: int
    duplicate_b: int
    parsed_a: int
    parsed_b: int
    replied_a: int
    replied_b: int
    forbidden_hits: tuple[str, ...]


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def resolve_runtime_partition_mode(log_file: Path, override: str | None = None) -> str | None:
    normalized_override = normalize_telegram_session_partition_mode(override)
    if normalized_override:
        return normalized_override

    mode_from_log = session_partition_mode_from_runtime_log(log_file)
    if mode_from_log:
        return mode_from_log
    return telegram_session_partition_mode()


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
        if thread_id is not None:
            return (f"{chat_id}:{thread_id}:{user_id}",)
        return (f"{chat_id}:0:{user_id}", f"{chat_id}:{user_id}")

    if thread_id is not None:
        return (f"{chat_id}:{thread_id}:{user_id}",)
    return (f"{chat_id}:{user_id}", f"{chat_id}:0:{user_id}")


def expected_session_key(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    session_partition: str | None = None,
) -> str:
    return expected_session_keys(chat_id, user_id, thread_id, session_partition)[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run concurrent dual-session command probe against local webhook runtime."
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "30")),
        help="Max wait for probe completion in seconds (default: 30).",
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
        help="Session A chat id (default: $OMNI_TEST_CHAT_ID or inferred from logs).",
    )
    parser.add_argument(
        "--chat-b",
        type=int,
        default=None,
        help="Session B chat id (default: --chat-id).",
    )
    parser.add_argument(
        "--user-a",
        type=int,
        default=int(os.environ["OMNI_TEST_USER_ID"]) if "OMNI_TEST_USER_ID" in os.environ else None,
        help="First user id (default: $OMNI_TEST_USER_ID or inferred from logs).",
    )
    parser.add_argument(
        "--user-b",
        type=int,
        default=None,
        help="Second user id (default: user-a + 1; may equal user-a when --chat-b differs).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME"),
        help="Username used for allowlist checks (default: env/settings/log fallback).",
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
        default=None,
        help="Optional thread id for session B.",
    )
    parser.add_argument(
        "--secret-token",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
        help="Webhook secret header value.",
    )
    parser.add_argument(
        "--prompt",
        default="/session json",
        help="Command prompt to execute concurrently for both sessions.",
    )
    parser.add_argument(
        "--forbid-log-regex",
        action="append",
        default=["tools/call: Mcp error", "Telegram sendMessage failed"],
        help="Regex that must not appear in new logs (repeatable).",
    )
    parser.add_argument(
        "--allow-send-failure",
        action="store_true",
        help=(
            "Allow Telegram send failures for synthetic cross-chat probes where "
            "the bot cannot reply to chat-b. This relaxes reply-event requirements."
        ),
    )
    parser.add_argument(
        "--session-partition",
        default=os.environ.get("OMNI_BLACKBOX_SESSION_PARTITION_MODE", ""),
        help=(
            "Session partition mode override for key matching "
            "(chat|chat_user|user|chat_thread_user)."
        ),
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> ProbeConfig:
    if args.max_wait <= 0:
        raise ValueError("--max-wait must be a positive integer.")

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

    user_b = args.user_b
    if user_b is None:
        user_b = group_profile_int("OMNI_TEST_USER_B")
    if user_b is None:
        user_b = int(user_a) + 1

    username = args.username.strip() if args.username else None
    if not username:
        username = username_from_settings()
    if not username:
        username = username_from_runtime_log(log_file)

    runtime_partition_mode = resolve_runtime_partition_mode(
        log_file,
        getattr(args, "session_partition", None),
    )

    key_a_candidates = set(
        expected_session_keys(int(chat_id), int(user_a), thread_a, runtime_partition_mode)
    )
    key_b_candidates = set(
        expected_session_keys(int(chat_b), int(user_b), args.thread_b, runtime_partition_mode)
    )
    if key_a_candidates & key_b_candidates:
        raise ValueError(
            "session-a and session-b resolve to the same session_key; adjust "
            "--chat-b/--user-b/--thread-b to target distinct sessions "
            f"(partition={runtime_partition_mode or 'unknown'})."
        )

    secret_token: str | None = args.secret_token.strip() if args.secret_token else None
    if not secret_token:
        secret_token = telegram_webhook_secret_token()

    return ProbeConfig(
        max_wait=args.max_wait,
        webhook_url=args.webhook_url,
        log_file=log_file,
        chat_id=int(chat_id),
        chat_b=int(chat_b),
        user_a=int(user_a),
        user_b=int(user_b),
        username=username,
        thread_a=thread_a,
        thread_b=args.thread_b,
        secret_token=secret_token,
        prompt=args.prompt,
        forbid_log_regexes=tuple(
            pattern
            for pattern in args.forbid_log_regex
            if not (args.allow_send_failure and pattern == "Telegram sendMessage failed")
        ),
        allow_send_failure=bool(args.allow_send_failure),
        session_partition=runtime_partition_mode,
    )


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def read_new_lines(path: Path, start_line: int) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return handle.read().splitlines()[start_line:]


def build_payload(
    *,
    update_id: int,
    chat_id: int,
    user_id: int,
    username: str | None,
    prompt: str,
    thread_id: int | None,
) -> bytes:
    from_user: dict[str, object] = {"id": user_id, "is_bot": False, "first_name": "ConcurrentProbe"}
    if username:
        from_user["username"] = username
    message: dict[str, object] = {
        "message_id": update_id % 2_000_000_000,
        "date": update_id // 1_000_000,
        "text": prompt,
        "chat": {"id": chat_id, "type": "private" if chat_id > 0 else "group"},
        "from": from_user,
    }
    if thread_id is not None:
        message["message_thread_id"] = thread_id
    body = {"update_id": update_id, "message": message}
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def post_webhook(url: str, payload: bytes, secret_token: str | None) -> tuple[int, str]:
    request = urllib.request.Request(url=url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    if secret_token:
        request.add_header("X-Telegram-Bot-Api-Secret-Token", secret_token)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return int(error.code), error.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        return 0, f"connection_error: {error.reason}"


def collect_observation(
    lines: list[str],
    *,
    update_a: int,
    update_b: int,
    key_a_candidates: tuple[str, ...],
    key_b_candidates: tuple[str, ...],
    forbid_log_regexes: tuple[str, ...],
) -> Observation:
    normalized = [strip_ansi(line) for line in lines]
    key_a_set = set(key_a_candidates)
    key_b_set = set(key_b_candidates)
    forbidden_hits: list[str] = []
    for pattern in forbid_log_regexes:
        regex = re.compile(pattern)
        for line in normalized:
            if regex.search(line):
                forbidden_hits.append(line)

    def _count(predicate) -> int:
        return sum(1 for line in normalized if predicate(line))

    def _session_key_in(line: str, candidates: set[str]) -> bool:
        match = SESSION_KEY_RE.search(line)
        return bool(match and match.group(1) in candidates)

    return Observation(
        accepted_a=_count(
            lambda line: f"update_id={update_a}" in line
            and 'event="telegram.dedup.update_accepted"' in line
        ),
        accepted_b=_count(
            lambda line: f"update_id={update_b}" in line
            and 'event="telegram.dedup.update_accepted"' in line
        ),
        dedup_fail_open_a=_count(
            lambda line: f"update_id={update_a}" in line and "Webhook dedup check failed" in line
        ),
        dedup_fail_open_b=_count(
            lambda line: f"update_id={update_b}" in line and "Webhook dedup check failed" in line
        ),
        duplicate_a=_count(
            lambda line: f"update_id={update_a}" in line
            and 'event="telegram.dedup.duplicate_detected"' in line
        ),
        duplicate_b=_count(
            lambda line: f"update_id={update_b}" in line
            and 'event="telegram.dedup.duplicate_detected"' in line
        ),
        parsed_a=_count(
            lambda line: "Parsed message, forwarding to agent" in line
            and _session_key_in(line, key_a_set)
        ),
        parsed_b=_count(
            lambda line: "Parsed message, forwarding to agent" in line
            and _session_key_in(line, key_b_set)
        ),
        replied_a=_count(
            lambda line: "telegram command reply sent" in line
            and 'event="telegram.command.session_status_json.replied"' in line
            and _session_key_in(line, key_a_set)
        ),
        replied_b=_count(
            lambda line: "telegram command reply sent" in line
            and 'event="telegram.command.session_status_json.replied"' in line
            and _session_key_in(line, key_b_set)
        ),
        forbidden_hits=tuple(forbidden_hits),
    )


def run_probe(cfg: ProbeConfig) -> int:
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.log_file.exists():
        cfg.log_file.touch()

    start_line = count_lines(cfg.log_file)
    update_a = (time.time_ns() // 1_000) + random.randint(0, 999)
    update_b = update_a + random.randint(1_000, 9_999)
    key_a_candidates = expected_session_keys(
        cfg.chat_id,
        cfg.user_a,
        cfg.thread_a,
        cfg.session_partition,
    )
    key_b_candidates = expected_session_keys(
        cfg.chat_b,
        cfg.user_b,
        cfg.thread_b,
        cfg.session_partition,
    )
    key_a = key_a_candidates[0]
    key_b = key_b_candidates[0]

    payload_a = build_payload(
        update_id=update_a,
        chat_id=cfg.chat_id,
        user_id=cfg.user_a,
        username=cfg.username,
        prompt=cfg.prompt,
        thread_id=cfg.thread_a,
    )
    payload_b = build_payload(
        update_id=update_b,
        chat_id=cfg.chat_b,
        user_id=cfg.user_b,
        username=cfg.username,
        prompt=cfg.prompt,
        thread_id=cfg.thread_b,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(post_webhook, cfg.webhook_url, payload_a, cfg.secret_token)
        fut_b = pool.submit(post_webhook, cfg.webhook_url, payload_b, cfg.secret_token)
        status_a, body_a = fut_a.result()
        status_b, body_b = fut_b.result()

    print("Concurrent probe posted.")
    print(f"  webhook_url={cfg.webhook_url}")
    print(f"  log_file={cfg.log_file}")
    print(f"  session_partition={cfg.session_partition or 'unknown'}")
    print(f"  session_a={key_a} chat={cfg.chat_id} update_id={update_a} status={status_a}")
    print(f"  session_b={key_b} chat={cfg.chat_b} update_id={update_b} status={status_b}")
    if cfg.allow_send_failure:
        print("  allow_send_failure=true")

    if status_a != 200 or status_b != 200:
        print("Error: webhook POST failed.", file=sys.stderr)
        print(f"  session_a status={status_a} body={body_a}", file=sys.stderr)
        print(f"  session_b status={status_b} body={body_b}", file=sys.stderr)
        return 1

    deadline = time.monotonic() + cfg.max_wait
    obs = Observation(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ())
    while time.monotonic() < deadline:
        lines = read_new_lines(cfg.log_file, start_line)
        obs = collect_observation(
            lines,
            update_a=update_a,
            update_b=update_b,
            key_a_candidates=key_a_candidates,
            key_b_candidates=key_b_candidates,
            forbid_log_regexes=cfg.forbid_log_regexes,
        )
        dedup_a_ready = obs.accepted_a >= 1 or obs.dedup_fail_open_a >= 1
        dedup_b_ready = obs.accepted_b >= 1 or obs.dedup_fail_open_b >= 1
        done = (
            dedup_a_ready
            and dedup_b_ready
            and obs.parsed_a >= 1
            and obs.parsed_b >= 1
            and (cfg.allow_send_failure or (obs.replied_a >= 1 and obs.replied_b >= 1))
        )
        if done or obs.forbidden_hits:
            break
        time.sleep(0.5)

    if obs.forbidden_hits:
        print("Error: forbidden log pattern detected during concurrent probe.", file=sys.stderr)
        for line in obs.forbidden_hits[:10]:
            print(f"  {line}", file=sys.stderr)
        return 1

    if (
        (obs.accepted_a < 1 and obs.dedup_fail_open_a < 1)
        or (obs.accepted_b < 1 and obs.dedup_fail_open_b < 1)
        or obs.parsed_a < 1
        or obs.parsed_b < 1
        or (not cfg.allow_send_failure and (obs.replied_a < 1 or obs.replied_b < 1))
    ):
        print(f"Error: concurrent probe timed out after {cfg.max_wait}s.", file=sys.stderr)
        print(
            "  observed:"
            f" accepted_a={obs.accepted_a} accepted_b={obs.accepted_b}"
            f" dedup_fail_open_a={obs.dedup_fail_open_a} dedup_fail_open_b={obs.dedup_fail_open_b}"
            f" parsed_a={obs.parsed_a} parsed_b={obs.parsed_b}"
            f" replied_a={obs.replied_a} replied_b={obs.replied_b}",
            file=sys.stderr,
        )
        return 1

    if obs.duplicate_a > 0 or obs.duplicate_b > 0:
        print("Error: duplicate_detected appeared for fresh concurrent updates.", file=sys.stderr)
        print(f"  duplicate_a={obs.duplicate_a} duplicate_b={obs.duplicate_b}", file=sys.stderr)
        return 1

    print("Concurrent probe passed.")
    print(f"  accepted_a={obs.accepted_a} accepted_b={obs.accepted_b}")
    print(f"  dedup_fail_open_a={obs.dedup_fail_open_a} dedup_fail_open_b={obs.dedup_fail_open_b}")
    print(f"  parsed_a={obs.parsed_a} parsed_b={obs.parsed_b}")
    print(f"  replied_a={obs.replied_a} replied_b={obs.replied_b}")
    print(f"  isolated_session_keys=true ({key_a} != {key_b})")
    return 0


def main() -> int:
    try:
        cfg = build_config(parse_args())
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return run_probe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
