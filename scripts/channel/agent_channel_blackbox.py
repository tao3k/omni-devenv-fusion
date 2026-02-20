#!/usr/bin/env python3
"""
Black-box Telegram webhook probe for local omni-agent channel runtime.

This probe posts one synthetic Telegram update to local webhook endpoint, then waits for:
  - inbound log marker:  ← User: "[bbx-...] ..."
  - outbound log marker: → Bot: "..."
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

try:
    from test_config_resolver import (
        session_ids_from_runtime_log,
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
    session_ids_from_runtime_log = _resolver_module.session_ids_from_runtime_log
    telegram_webhook_secret_token = _resolver_module.telegram_webhook_secret_token
    username_from_runtime_log = _resolver_module.username_from_runtime_log
    username_from_settings = _resolver_module.username_from_settings

ERROR_PATTERNS = (
    "Telegram sendMessage failed",
    "Failed to send",
    "Foreground message handling failed",
    "tools/call: Mcp error",
)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
EVENT_TOKEN_RE = re.compile(r"\bevent\s*=\s*(?:\"|')?([A-Za-z0-9_.:-]+)")
SESSION_KEY_TOKEN_RE = re.compile(r"\bsession_key\s*=\s*(?:\"|')?([-\d]+(?::[-\d]+){1,2})(?:\"|')?")
RECIPIENT_TOKEN_RE = re.compile(r"\brecipient\s*=\s*(?:\"|')?([-\d]+)(?:\"|')?")
REPLY_CHARS_TOKEN_RE = re.compile(r"\breply_chars\s*=\s*(\d+)")
REPLY_BYTES_TOKEN_RE = re.compile(r"\breply_bytes\s*=\s*(\d+)")
LOG_TOKEN_RE = re.compile(r"\b([A-Za-z0-9_.:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s]+))")
MCP_OBSERVABILITY_EVENTS = (
    "mcp.pool.connect.attempt",
    "mcp.pool.connect.waiting",
    "mcp.pool.connect.failed",
    "mcp.pool.connect.succeeded",
    "mcp.pool.health.wait.start",
    "mcp.pool.health.wait.ready",
    "mcp.pool.health.wait.timeout",
    "mcp.pool.call.waiting",
    "mcp.pool.call.slow",
)
MCP_WAITING_EVENTS = frozenset({"mcp.pool.connect.waiting", "mcp.pool.call.waiting"})
TELEGRAM_SEND_RETRY_DELAY_MS_RE = re.compile(r"\bdelay_ms\s*=\s*(\d+)")
TELEGRAM_SEND_RETRY_AFTER_SECS_RE = re.compile(r"\bretry_after\s*=\s*(\d+)(?:s)?\b")


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def extract_event_token(value: str) -> str | None:
    match = EVENT_TOKEN_RE.search(value)
    if match:
        return match.group(1)
    return None


def extract_session_key_token(value: str) -> str | None:
    match = SESSION_KEY_TOKEN_RE.search(value)
    if match:
        return match.group(1)
    return None


def parse_log_tokens(value: str) -> dict[str, str]:
    normalized = strip_ansi(value)
    tokens: dict[str, str] = {}
    for match in LOG_TOKEN_RE.finditer(normalized):
        key = match.group(1)
        token = match.group(2) or match.group(3) or match.group(4) or ""
        tokens[key] = token
    return tokens


def parse_expected_field(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(
            f"Invalid --expect-reply-json-field value '{value}'. Expected format: key=value"
        )
    key, expected = value.split("=", 1)
    key = key.strip()
    expected = expected.strip()
    if not key or expected == "":
        raise ValueError(
            f"Invalid --expect-reply-json-field value '{value}'. Expected format: key=value"
        )
    return key, expected


def parse_allow_chat_ids(values: list[str]) -> tuple[int, ...]:
    ordered: list[int] = []
    for raw in values:
        token = raw.strip()
        if not token:
            continue
        try:
            chat_id = int(token)
        except ValueError as error:
            raise ValueError(
                f"Invalid chat id '{raw}' in allowlist. Expected integer Telegram chat id."
            ) from error
        if chat_id not in ordered:
            ordered.append(chat_id)
    return tuple(ordered)


def parse_command_reply_event_line(value: str) -> dict[str, object] | None:
    normalized = strip_ansi(value)
    if "telegram command reply sent" not in normalized:
        return None
    tokens = parse_log_tokens(normalized)
    event = tokens.get("event")
    if not event:
        return None
    return {
        "event": event,
        "session_key": tokens.get("session_key"),
        "recipient": tokens.get("recipient"),
        "reply_chars": int(tokens["reply_chars"]) if "reply_chars" in tokens else None,
        "reply_bytes": int(tokens["reply_bytes"]) if "reply_bytes" in tokens else None,
    }


def parse_command_reply_json_summary_line(value: str) -> dict[str, str] | None:
    normalized = strip_ansi(value)
    if "telegram command reply json summary" not in normalized:
        return None
    tokens = parse_log_tokens(normalized)
    if "event" not in tokens:
        return None
    return tokens


def telegram_send_retry_grace_seconds(value: str) -> float | None:
    normalized = strip_ansi(value)
    if "Telegram API transient failure; retrying" not in normalized:
        return None

    delay_match = TELEGRAM_SEND_RETRY_DELAY_MS_RE.search(normalized)
    if delay_match:
        return max(0.0, int(delay_match.group(1)) / 1000.0)

    retry_after_match = TELEGRAM_SEND_RETRY_AFTER_SECS_RE.search(normalized)
    if retry_after_match:
        return max(0.0, float(retry_after_match.group(1)))
    return None


@dataclass(frozen=True)
class ProbeConfig:
    prompt: str
    max_wait_secs: int | None
    max_idle_secs: int | None
    webhook_url: str
    log_file: Path
    chat_id: int
    user_id: int
    username: str | None
    chat_title: str | None
    thread_id: int | None
    secret_token: str | None
    follow_logs: bool
    expect_events: tuple[str, ...]
    expect_reply_json_fields: tuple[tuple[str, str], ...]
    expect_log_regexes: tuple[str, ...]
    expect_bot_regexes: tuple[str, ...]
    forbid_log_regexes: tuple[str, ...]
    fail_fast_error_logs: bool
    allow_no_bot: bool
    allow_chat_ids: tuple[int, ...]
    strong_update_id: bool = False
    session_partition: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject one synthetic Telegram webhook update and wait for bot reply logs."
    )
    parser.add_argument("--prompt", required=True, help="Prompt to inject.")
    parser.add_argument(
        "--max-wait",
        type=int,
        default=None,
        help="Optional overall wait upper-bound in seconds. Default: no hard limit (event-driven).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Deprecated alias for --max-wait.",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=None,
        help="Optional max idle (no new logs) before fail-fast.",
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
        default=None,
        help="Synthetic Telegram chat id (auto-infer from logs when omitted).",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Synthetic Telegram user id (auto-infer from logs when omitted).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OMNI_TEST_USERNAME"),
        help="Synthetic Telegram username for allowlist checks (e.g. `tao3k`).",
    )
    parser.add_argument(
        "--chat-title",
        default=os.environ.get("OMNI_TEST_CHAT_TITLE"),
        help=(
            "Optional synthetic Telegram chat title to include in payload "
            "(useful for chat_id/chat_title log mapping checks)."
        ),
    )
    parser.add_argument(
        "--thread-id",
        type=int,
        default=None,
        help="Synthetic Telegram thread/topic id.",
    )
    parser.add_argument(
        "--session-partition",
        default=os.environ.get("OMNI_TEST_SESSION_PARTITION"),
        help=(
            "Optional session partition mode hint "
            "(`chat`, `chat_user`, `user`, `chat_thread_user`) "
            "used for strict session-key validation."
        ),
    )
    parser.add_argument(
        "--secret-token",
        default=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
        help="Webhook secret token header value.",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Disable live log streaming while waiting.",
    )
    parser.add_argument(
        "--expect-log-regex",
        action="append",
        default=[],
        help="Regex expected somewhere in new logs (repeatable).",
    )
    parser.add_argument(
        "--expect-event",
        action="append",
        default=[],
        help="Structured `event=` token expected in new logs (repeatable, exact match).",
    )
    parser.add_argument(
        "--expect-reply-json-field",
        action="append",
        default=[],
        help=(
            "Expected key=value from `telegram command reply json summary` logs "
            "(repeatable). Example: --expect-reply-json-field json_kind=session_budget"
        ),
    )
    parser.add_argument(
        "--expect-bot-regex",
        action="append",
        default=[],
        help="Regex expected in `→ Bot:` log line (repeatable).",
    )
    parser.add_argument(
        "--forbid-log-regex",
        action="append",
        default=[],
        help="Regex that must not appear in new logs (repeatable).",
    )
    parser.add_argument(
        "--no-fail-fast-error-log",
        action="store_true",
        help="Do not fail immediately when known error patterns appear.",
    )
    parser.add_argument(
        "--allow-no-bot",
        action="store_true",
        help="Allow success without `→ Bot:` if all expect-log checks are satisfied.",
    )
    parser.add_argument(
        "--allow-chat-id",
        action="append",
        default=[],
        help=(
            "Allowlisted chat id for this probe (repeatable). "
            "When set, probe refuses to post outside this allowlist."
        ),
    )
    return parser.parse_args()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def read_new_lines(path: Path, cursor: int) -> tuple[int, list[str]]:
    if not path.exists():
        return cursor, []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.read().splitlines()
    total = len(lines)
    if total <= cursor:
        return total, []
    return total, lines[cursor:]


def tail_lines(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    buf: deque[str] = deque(maxlen=n)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            buf.append(line.rstrip("\n"))
    return list(buf)


# Backward-compatible aliases for existing test-kit imports.
def infer_ids_from_log(path: Path) -> tuple[int | None, int | None, int | None]:
    return session_ids_from_runtime_log(path)


def infer_username_from_log(path: Path) -> str | None:
    return username_from_runtime_log(path)


def build_update_payload(
    update_id: int,
    chat_id: int,
    user_id: int,
    username: str | None,
    chat_title: str | None,
    text: str,
    thread_id: int | None,
) -> str:
    from_user: dict[str, object] = {"id": user_id, "is_bot": False, "first_name": "BlackboxProbe"}
    if username:
        from_user["username"] = username
    chat: dict[str, object] = {"id": chat_id, "type": "private" if chat_id > 0 else "group"}
    if chat_title:
        chat["title"] = chat_title
    message: dict[str, object] = {
        "message_id": update_id % 2_000_000_000,
        "date": int(time.time()),
        "text": text,
        "chat": chat,
        "from": from_user,
    }
    if thread_id is not None:
        message["message_thread_id"] = thread_id
    payload = {"update_id": update_id, "message": message}
    return json.dumps(payload, ensure_ascii=False)


def build_probe_message(prompt: str, trace_id: str) -> str:
    if prompt.lstrip().startswith("/"):
        # Keep slash-command payload unchanged so command routers receive exact input.
        return prompt
    return f"[{trace_id}] {prompt}"


def normalize_session_partition(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"chat", "chat_only", "chatonly"}:
        return "chat"
    if normalized in {"chat_user", "chatuser"}:
        return "chat_user"
    if normalized in {"user", "user_only", "useronly"}:
        return "user"
    if normalized in {"chat_thread_user", "chatthreaduser", "topic_user", "topicuser"}:
        return "chat_thread_user"
    return None


def expected_session_keys(
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    session_partition: str | None = None,
) -> tuple[str, ...]:
    """Return accepted session-key forms for the current probe target."""
    partition = normalize_session_partition(session_partition)
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

    # Unknown mode fallback preserves historical expectations used by existing tests/callers.
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


def expected_recipient_key(chat_id: int, thread_id: int | None) -> str:
    if thread_id is None:
        return str(chat_id)
    return f"{chat_id}:{thread_id}"


def post_webhook_update(url: str, payload: str, secret_token: str | None) -> tuple[int, str]:
    data = payload.encode("utf-8")
    request = urllib.request.Request(url=url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if secret_token:
        request.add_header("X-Telegram-Bot-Api-Secret-Token", secret_token)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return int(error.code), body
    except urllib.error.URLError as error:
        return 0, f"connection_error: {error.reason}"


def build_config(args: argparse.Namespace) -> ProbeConfig:
    log_file = Path(args.log_file)
    chat_id = args.chat_id if args.chat_id is not None else None
    user_id = args.user_id if args.user_id is not None else None
    thread_id = args.thread_id if args.thread_id is not None else None

    if chat_id is None:
        env_chat = os.environ.get("OMNI_TEST_CHAT_ID")
        if env_chat:
            chat_id = int(env_chat)
    if user_id is None:
        env_user = os.environ.get("OMNI_TEST_USER_ID")
        if env_user:
            user_id = int(env_user)
    if thread_id is None:
        env_thread = os.environ.get("OMNI_TEST_THREAD_ID")
        if env_thread:
            thread_id = int(env_thread)

    if chat_id is None or user_id is None:
        inferred_chat, inferred_user, inferred_thread = session_ids_from_runtime_log(log_file)
        if chat_id is None:
            chat_id = inferred_chat
        if user_id is None:
            user_id = inferred_user
        if thread_id is None:
            thread_id = inferred_thread

    username: str | None = args.username
    if not username:
        username = username_from_settings()
    if not username:
        username = username_from_runtime_log(log_file)

    if chat_id is None or user_id is None:
        raise ValueError(
            "chat/user id are required. Set --chat-id/--user-id (or OMNI_TEST_CHAT_ID/OMNI_TEST_USER_ID). "
            f"Tip: run one real Telegram message first to auto-infer from {log_file}."
        )
    max_wait_secs: int | None = args.max_wait
    if max_wait_secs is None and args.timeout is not None:
        max_wait_secs = args.timeout
    if max_wait_secs is None:
        env_wait = os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "").strip()
        if env_wait:
            max_wait_secs = int(env_wait)
    if max_wait_secs is not None and max_wait_secs <= 0:
        max_wait_secs = None
    max_idle_secs: int | None = args.max_idle_secs
    if max_idle_secs is None:
        env_idle = os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "").strip()
        if env_idle:
            max_idle_secs = int(env_idle)
    if max_idle_secs is not None and max_idle_secs <= 0:
        max_idle_secs = None
    expect_reply_json_fields = tuple(
        parse_expected_field(value) for value in args.expect_reply_json_field
    )
    cli_allow_chat_ids = parse_allow_chat_ids(args.allow_chat_id)
    env_allow_chat_ids = parse_allow_chat_ids(
        [token for token in os.environ.get("OMNI_BLACKBOX_ALLOWED_CHAT_IDS", "").split(",")]
    )
    allow_chat_ids = tuple(dict.fromkeys([*cli_allow_chat_ids, *env_allow_chat_ids]))
    if allow_chat_ids and int(chat_id) not in allow_chat_ids:
        raise ValueError(
            "Probe chat_id is not in allowlist. "
            f"chat_id={chat_id} allow_chat_ids={list(allow_chat_ids)}"
        )
    session_partition = normalize_session_partition(getattr(args, "session_partition", None))

    return ProbeConfig(
        prompt=args.prompt,
        max_wait_secs=max_wait_secs,
        max_idle_secs=max_idle_secs,
        webhook_url=args.webhook_url,
        log_file=log_file,
        chat_id=int(chat_id),
        user_id=int(user_id),
        username=username,
        chat_title=(args.chat_title.strip() if args.chat_title else None),
        thread_id=thread_id,
        session_partition=session_partition,
        secret_token=(args.secret_token or telegram_webhook_secret_token()),
        follow_logs=not args.no_follow,
        expect_events=tuple(args.expect_event),
        expect_reply_json_fields=expect_reply_json_fields,
        expect_log_regexes=tuple(args.expect_log_regex),
        expect_bot_regexes=tuple(args.expect_bot_regex),
        forbid_log_regexes=tuple(args.forbid_log_regex),
        fail_fast_error_logs=not args.no_fail_fast_error_log,
        allow_no_bot=bool(args.allow_no_bot),
        allow_chat_ids=allow_chat_ids,
        strong_update_id=True,
    )


_LAST_STRONG_UPDATE_ID = 0


def next_update_id(strong_update_id: bool) -> int:
    base_ms = int(time.time() * 1000)
    if not strong_update_id:
        return base_ms

    # Use composed time + pid + random components so concurrent probe subprocesses
    # do not collide on update_id and get dropped by webhook dedup.
    pid_component = os.getpid() % 10_000
    rand_component = secrets.randbelow(100)
    candidate = (base_ms * 1_000_000) + (pid_component * 100) + rand_component
    global _LAST_STRONG_UPDATE_ID
    if candidate <= _LAST_STRONG_UPDATE_ID:
        candidate = _LAST_STRONG_UPDATE_ID + 1
    _LAST_STRONG_UPDATE_ID = candidate
    return candidate


def run_probe(cfg: ProbeConfig) -> int:
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    start_line = count_lines(cfg.log_file)

    update_id = next_update_id(cfg.strong_update_id)
    trace_id = f"bbx-{update_id}-{os.getpid()}"
    message_text = build_probe_message(cfg.prompt, trace_id)
    payload = build_update_payload(
        update_id=update_id,
        chat_id=cfg.chat_id,
        user_id=cfg.user_id,
        username=cfg.username,
        chat_title=cfg.chat_title,
        text=message_text,
        thread_id=cfg.thread_id,
    )

    status, body = post_webhook_update(cfg.webhook_url, payload, cfg.secret_token)
    if status != 200:
        print(f"Error: webhook POST failed (HTTP {status}).", file=sys.stderr)
        print(f"Webhook URL: {cfg.webhook_url}", file=sys.stderr)
        print("Response body:", file=sys.stderr)
        for line in body.splitlines():
            print(f"  {line}", file=sys.stderr)
        print("MCP diagnostics:")
        print("  mcp_last_event=")
        print("  mcp_waiting_seen=false")
        print("  mcp_event_counts={}")
        return 1

    print("Blackbox probe posted.")
    print(f"  update_id={update_id}")
    print(f"  trace_id={trace_id}")
    print(f"  webhook_url={cfg.webhook_url}")
    print(
        f"  chat_id={cfg.chat_id} user_id={cfg.user_id} "
        f"username={cfg.username if cfg.username else '(none)'} "
        f"chat_title={cfg.chat_title if cfg.chat_title else '(none)'} "
        f"thread_id={cfg.thread_id if cfg.thread_id is not None else 'none'}"
    )
    print(f"  session_partition={cfg.session_partition or 'auto'}")
    print(f"  log_file={cfg.log_file}")
    print(f"  trace_mode={'on' if trace_id in message_text else 'off'}")
    if cfg.allow_chat_ids:
        print(f"  allow_chat_ids={list(cfg.allow_chat_ids)}")
    else:
        print("  allow_chat_ids=none (no probe-level restriction)")
    if cfg.max_wait_secs is None:
        print("  max_wait_secs=none (event-driven)")
    else:
        print(f"  max_wait_secs={cfg.max_wait_secs}")
    if cfg.max_idle_secs is None:
        print("  max_idle_secs=none")
    else:
        print(f"  max_idle_secs={cfg.max_idle_secs}")
    if cfg.expect_events:
        print(f"  expect_events={list(cfg.expect_events)}")
    if cfg.expect_reply_json_fields:
        print(
            "  expect_reply_json_fields="
            f"{[f'{key}={value}' for key, value in cfg.expect_reply_json_fields]}"
        )
    if cfg.expect_log_regexes:
        print(f"  expect_log_regexes={list(cfg.expect_log_regexes)}")
    if cfg.expect_bot_regexes:
        print(f"  expect_bot_regexes={list(cfg.expect_bot_regexes)}")
    if cfg.forbid_log_regexes:
        print(f"  forbid_log_regexes={list(cfg.forbid_log_regexes)}")
    print("")

    expect_log_compiled = [re.compile(p) for p in cfg.expect_log_regexes]
    expect_bot_compiled = [re.compile(p) for p in cfg.expect_bot_regexes]
    forbid_log_compiled = [re.compile(p) for p in cfg.forbid_log_regexes]
    expected_sessions = expected_session_keys(
        cfg.chat_id,
        cfg.user_id,
        cfg.thread_id,
        cfg.session_partition,
    )
    expected_session = expected_session_key(
        cfg.chat_id,
        cfg.user_id,
        cfg.thread_id,
        cfg.session_partition,
    )
    expected_recipient = expected_recipient_key(cfg.chat_id, cfg.thread_id)
    matched_expect_events = [False] * len(cfg.expect_events)
    matched_expect_reply_json_fields = [False] * len(cfg.expect_reply_json_fields)
    matched_expect_log = [False] * len(expect_log_compiled)
    matched_expect_bot = [False] * len(expect_bot_compiled)
    bot_observations: list[str] = []
    mcp_event_counts: Counter[str] = Counter()
    mcp_last_event: str | None = None
    mcp_waiting_seen = False

    def all_expectations_satisfied() -> bool:
        return (
            all(matched_expect_events)
            and all(matched_expect_reply_json_fields)
            and all(matched_expect_log)
            and all(matched_expect_bot)
        )

    def non_bot_expectations_satisfied() -> bool:
        return (
            all(matched_expect_events)
            and all(matched_expect_reply_json_fields)
            and all(matched_expect_log)
        )

    def missing_expectations() -> tuple[list[str], list[str], list[str], list[str]]:
        missing_events = [
            cfg.expect_events[i] for i, ok in enumerate(matched_expect_events) if not ok
        ]
        missing_reply_json_fields = [
            f"{key}={value}"
            for i, (key, value) in enumerate(cfg.expect_reply_json_fields)
            if not matched_expect_reply_json_fields[i]
        ]
        missing_log = [
            cfg.expect_log_regexes[i] for i, ok in enumerate(matched_expect_log) if not ok
        ]
        missing_bot = [
            cfg.expect_bot_regexes[i] for i, ok in enumerate(matched_expect_bot) if not ok
        ]
        return missing_events, missing_reply_json_fields, missing_log, missing_bot

    def latest_json_summary_for_event(event: str | None) -> dict[str, str] | None:
        if not json_reply_summary_observations:
            return None
        if event:
            for obs in reversed(json_reply_summary_observations):
                if obs.get("event") == event:
                    return obs
        return json_reply_summary_observations[-1]

    def event_matches_expectations(event: str) -> bool:
        return not cfg.expect_events or event in cfg.expect_events

    def recipient_matches_target(recipient: str) -> bool:
        if not recipient:
            return True
        return recipient == expected_recipient

    def observation_matches_target_recipient(observation: dict[str, object]) -> bool:
        recipient = str(observation.get("recipient") or "")
        return recipient_matches_target(recipient)

    def observation_matches_target_scope(observation: dict[str, object]) -> bool:
        if not observation_matches_target_recipient(observation):
            return False
        session_key = str(observation.get("session_key") or "")
        return not session_key or session_key in expected_sessions

    def event_line_matches_target_recipient(value: str) -> bool:
        tokens = parse_log_tokens(value)
        recipient = tokens.get("recipient", "")
        return recipient_matches_target(recipient)

    def pick_target_command_reply_observation() -> dict[str, object] | None:
        fallback_recipient_only: dict[str, object] | None = None
        for obs in command_reply_observations:
            event = str(obs.get("event") or "")
            if not event_matches_expectations(event):
                continue
            if observation_matches_target_scope(obs):
                return obs
            if fallback_recipient_only is None and observation_matches_target_recipient(obs):
                fallback_recipient_only = obs
        return fallback_recipient_only

    def pick_target_json_summary_observation() -> dict[str, str] | None:
        fallback_recipient_only: dict[str, str] | None = None
        for obs in json_reply_summary_observations:
            event = str(obs.get("event") or "")
            if not event_matches_expectations(event):
                continue
            if observation_matches_target_scope(obs):
                return obs
            if fallback_recipient_only is None and observation_matches_target_recipient(obs):
                fallback_recipient_only = obs
        return fallback_recipient_only

    def validate_target_session_scope() -> tuple[bool, str]:
        # When the probe has no command-scoped expectations, skip command-reply
        # session matching to avoid false positives under concurrent traffic.
        if not cfg.expect_events and not cfg.expect_reply_json_fields:
            return True, ""
        target_reply = pick_target_command_reply_observation()
        if target_reply:
            observed_session = str(target_reply.get("session_key") or "")
            if observed_session and observed_session not in expected_sessions:
                return (
                    False,
                    "command_reply "
                    f"event={target_reply.get('event')} recipient={target_reply.get('recipient')} "
                    f"observed_session_key={observed_session}",
                )
            return True, ""
        target_summary = pick_target_json_summary_observation()
        if target_summary:
            observed_session = str(target_summary.get("session_key") or "")
            if observed_session and observed_session not in expected_sessions:
                return (
                    False,
                    "command_reply_json_summary "
                    f"event={target_summary.get('event')} recipient={target_summary.get('recipient')} "
                    f"observed_session_key={observed_session}",
                )
            return True, ""
        requires_target_observation = bool(cfg.expect_reply_json_fields) or any(
            event.startswith("telegram.command.") for event in cfg.expect_events
        )
        if requires_target_observation:
            return (
                False,
                "missing target-scoped command reply/json observation "
                f"for chat_id={cfg.chat_id} session_key={expected_session}",
            )
        return True, ""

    def emit_mcp_diagnostics() -> None:
        counts_payload = {
            event: mcp_event_counts[event]
            for event in MCP_OBSERVABILITY_EVENTS
            if mcp_event_counts[event] > 0
        }
        print("MCP diagnostics:")
        print(f"  mcp_last_event={mcp_last_event or ''}")
        print(f"  mcp_waiting_seen={'true' if mcp_waiting_seen else 'false'}")
        print(
            "  mcp_event_counts="
            + json.dumps(counts_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        )

    def finish(code: int) -> int:
        emit_mcp_diagnostics()
        return code

    cursor = start_line
    trace_mode = trace_id in message_text
    seen_trace = False
    seen_user_dispatch = False
    seen_bot = False
    bot_line = ""
    error_line = ""
    dedup_duplicate_line = ""
    dispatch_session_mismatch_line = ""
    webhook_seen = False
    command_reply_observations: list[dict[str, object]] = []
    json_reply_summary_observations: list[dict[str, str]] = []
    deadline = time.monotonic() + cfg.max_wait_secs if cfg.max_wait_secs is not None else None
    last_log_activity = time.monotonic()
    retry_grace_until = 0.0

    while True:
        if deadline is not None and time.monotonic() > deadline:
            break
        cursor, chunk = read_new_lines(cfg.log_file, cursor)
        if chunk:
            normalized_chunk = [strip_ansi(line) for line in chunk]
            last_log_activity = time.monotonic()
            if cfg.follow_logs:
                for line in chunk:
                    print(f"[log] {line}")
            for line in normalized_chunk:
                event_token = extract_event_token(line)
                if event_token:
                    for idx, expected in enumerate(cfg.expect_events):
                        if (
                            not matched_expect_events[idx]
                            and event_token == expected
                            and event_line_matches_target_recipient(line)
                        ):
                            matched_expect_events[idx] = True
                    if event_token in MCP_OBSERVABILITY_EVENTS:
                        mcp_event_counts[event_token] += 1
                        mcp_last_event = event_token
                        if event_token in MCP_WAITING_EVENTS:
                            mcp_waiting_seen = True
                reply_obs = parse_command_reply_event_line(line)
                if reply_obs:
                    command_reply_observations.append(reply_obs)
                json_summary_obs = parse_command_reply_json_summary_line(line)
                if json_summary_obs:
                    json_reply_summary_observations.append(json_summary_obs)
                    json_summary_event = json_summary_obs.get("event")
                    event_scoped_match = not cfg.expect_events or (
                        json_summary_event in cfg.expect_events
                    )
                    if event_scoped_match and observation_matches_target_recipient(
                        json_summary_obs
                    ):
                        for idx, (key, expected) in enumerate(cfg.expect_reply_json_fields):
                            if matched_expect_reply_json_fields[idx]:
                                continue
                            if json_summary_obs.get(key) == expected:
                                matched_expect_reply_json_fields[idx] = True
                retry_grace_secs = telegram_send_retry_grace_seconds(line)
                if retry_grace_secs is not None:
                    grace_until = time.monotonic() + retry_grace_secs + 2.0
                    if grace_until > retry_grace_until:
                        retry_grace_until = grace_until
                for idx, pattern in enumerate(expect_log_compiled):
                    if not matched_expect_log[idx] and pattern.search(line):
                        matched_expect_log[idx] = True
                for pattern in forbid_log_compiled:
                    if pattern.search(line):
                        print("", file=sys.stderr)
                        print("Probe failed: forbidden log regex matched.", file=sys.stderr)
                        print(f"  regex={pattern.pattern}", file=sys.stderr)
                        print(f"  line={line}", file=sys.stderr)
                        return finish(5)
            for line in normalized_chunk:
                if f"update_id=Some({update_id})" in line:
                    webhook_seen = True
                if str(update_id) in line and "duplicate update" in line.lower():
                    dedup_duplicate_line = line
                if trace_mode and trace_id in line:
                    observed_session_key = extract_session_key_token(line)
                    if observed_session_key and observed_session_key not in expected_sessions:
                        dispatch_session_mismatch_line = line
                        break
            if dispatch_session_mismatch_line:
                break
            if trace_mode and not seen_trace and any(trace_id in line for line in normalized_chunk):
                seen_trace = True
            if not seen_user_dispatch:
                if trace_mode:
                    seen_user_dispatch = any(
                        "← User:" in line and trace_id in line for line in normalized_chunk
                    )
                else:
                    seen_user_dispatch = any(
                        ("← User:" in line or "Parsed message, forwarding to agent" in line)
                        and cfg.prompt in line
                        for line in normalized_chunk
                    )
            if seen_user_dispatch:
                for line in normalized_chunk:
                    if any(pattern in line for pattern in ERROR_PATTERNS):
                        error_line = line
                        if cfg.fail_fast_error_logs:
                            print("", file=sys.stderr)
                            print("Probe failed: fail-fast error log detected.", file=sys.stderr)
                            print(f"  line={line}", file=sys.stderr)
                            return finish(6)
                for line in normalized_chunk:
                    if "→ Bot:" in line:
                        bot_observations.append(line)
                        seen_bot = True
                        bot_line = line
                        for idx, pattern in enumerate(expect_bot_compiled):
                            if not matched_expect_bot[idx] and pattern.search(line):
                                matched_expect_bot[idx] = True
                if seen_bot and all_expectations_satisfied():
                    break
            if cfg.allow_no_bot and seen_user_dispatch and all_expectations_satisfied():
                session_ok, mismatch_context = validate_target_session_scope()
                if not session_ok:
                    print("Probe failed: command reply session_key mismatch.", file=sys.stderr)
                    print(
                        f"  expected_session_keys={list(expected_sessions)}",
                        file=sys.stderr,
                    )
                    print(f"  {mismatch_context}", file=sys.stderr)
                    return finish(10)
                print("")
                print("Blackbox probe succeeded (allow-no-bot mode).")
                print(
                    "All expect-event / expect-reply-json-field / expect-log / expect-bot checks are satisfied."
                )
                return finish(0)
        if seen_bot and all_expectations_satisfied():
            break
        if (
            cfg.max_idle_secs is not None
            and (time.monotonic() - last_log_activity) > cfg.max_idle_secs
        ):
            if retry_grace_until and time.monotonic() <= retry_grace_until:
                time.sleep(0.2)
                continue
            print("", file=sys.stderr)
            print(
                "Probe failed: max-idle exceeded with no new logs.",
                file=sys.stderr,
            )
            print(f"  max_idle_secs={cfg.max_idle_secs}", file=sys.stderr)
            return finish(7)
        time.sleep(1)

    print("")
    if dedup_duplicate_line and not seen_user_dispatch:
        print("Probe failed: webhook update was dropped as duplicate.", file=sys.stderr)
        print("Related log line:", file=sys.stderr)
        print(f"  {dedup_duplicate_line}", file=sys.stderr)
        return finish(4)
    if dispatch_session_mismatch_line:
        print("Probe failed: observed session_key does not match target session.", file=sys.stderr)
        print(f"  expected_session_keys={list(expected_sessions)}", file=sys.stderr)
        print(f"  line={dispatch_session_mismatch_line}", file=sys.stderr)
        return finish(10)

    if seen_bot:
        missing_events, missing_reply_json_fields, missing_log, missing_bot = missing_expectations()
        if missing_events or missing_reply_json_fields or missing_log or missing_bot:
            if (
                not missing_events
                and not missing_reply_json_fields
                and not missing_log
                and missing_bot
            ):
                print(
                    "Probe failed: outbound bot reply observed, but expect-bot regex did not match.",
                    file=sys.stderr,
                )
                print(f"Missing expect-bot regex: {missing_bot}", file=sys.stderr)
                print("Observed outbound bot logs (latest first):", file=sys.stderr)
                for observed in reversed(bot_observations[-3:]):
                    print(f"  {observed}", file=sys.stderr)
                return finish(11)
            print("Probe failed: bot replied but expectations are incomplete.", file=sys.stderr)
            if missing_events:
                print(f"Missing expect-event values: {missing_events}", file=sys.stderr)
            if missing_reply_json_fields:
                print(
                    f"Missing expect-reply-json-field values: {missing_reply_json_fields}",
                    file=sys.stderr,
                )
            if missing_log:
                print(f"Missing expect-log regex: {missing_log}", file=sys.stderr)
            if missing_bot:
                print(f"Missing expect-bot regex: {missing_bot}", file=sys.stderr)
            return finish(8)
        session_ok, mismatch_context = validate_target_session_scope()
        if not session_ok:
            print("Probe failed: command reply session_key mismatch.", file=sys.stderr)
            print(f"  expected_session_keys={list(expected_sessions)}", file=sys.stderr)
            print(f"  {mismatch_context}", file=sys.stderr)
            return finish(10)
        target_obs = pick_target_command_reply_observation()
        print("Blackbox probe succeeded.")
        print("Observed outbound bot log:")
        print(f"  {bot_line}")
        if command_reply_observations:
            latest_obs = target_obs or command_reply_observations[-1]
            print("Reply observability:")
            print(f"  event={latest_obs.get('event')}")
            print(f"  session_key={latest_obs.get('session_key')}")
            print(f"  recipient={latest_obs.get('recipient')}")
            print(f"  reply_chars={latest_obs.get('reply_chars')}")
            print(f"  reply_bytes={latest_obs.get('reply_bytes')}")
            latest_summary = latest_json_summary_for_event(str(latest_obs.get("event")))
        else:
            latest_summary = latest_json_summary_for_event(
                cfg.expect_events[0] if cfg.expect_events else None
            )
        if latest_summary:
            print("Reply json summary:")
            for key in (
                "json_kind",
                "json_available",
                "json_status",
                "json_found",
                "json_decision",
                "json_keys",
            ):
                value = latest_summary.get(key)
                if value:
                    print(f"  {key}={value}")
        return finish(0)

    if trace_mode and not seen_trace:
        if webhook_seen:
            print(
                "Probe timed out: webhook update arrived, but trace marker was not observed in downstream logs.",
                file=sys.stderr,
            )
        else:
            print("Probe timed out: did not observe inbound marker in logs.", file=sys.stderr)
        print(f"Expected marker: {trace_id}", file=sys.stderr)
        print(
            "Tip: ensure runtime log file is correct and webhook process is running.",
            file=sys.stderr,
        )
        last = tail_lines(cfg.log_file, 40)
        if last:
            print("Last 40 log lines:", file=sys.stderr)
            for line in last:
                print(f"  {line}", file=sys.stderr)
        return finish(2)

    if not seen_user_dispatch:
        print(
            "Probe timed out: trace marker observed, but dispatch marker `← User:` was not observed.",
            file=sys.stderr,
        )
        print(f"Expected dispatch trace: [{trace_id}]", file=sys.stderr)
        last = tail_lines(cfg.log_file, 60)
        if last:
            print("Last 60 log lines:", file=sys.stderr)
            for line in last:
                print(f"  {line}", file=sys.stderr)
        return finish(9)

    print(
        "Probe timed out: inbound marker observed, but no outbound bot log found before max-wait.",
        file=sys.stderr,
    )
    missing_events, missing_reply_json_fields, missing_log, missing_bot = missing_expectations()
    if missing_events:
        print(f"Missing expect-event values: {missing_events}", file=sys.stderr)
    if missing_reply_json_fields:
        print(
            f"Missing expect-reply-json-field values: {missing_reply_json_fields}",
            file=sys.stderr,
        )
    if missing_log:
        print(f"Missing expect-log regex: {missing_log}", file=sys.stderr)
    if missing_bot:
        print(f"Missing expect-bot regex: {missing_bot}", file=sys.stderr)
    if error_line:
        print("Last related error:", file=sys.stderr)
        print(f"  {error_line}", file=sys.stderr)
    if command_reply_observations:
        print("Observed command reply events (latest first):", file=sys.stderr)
        for obs in reversed(command_reply_observations[-3:]):
            print(
                "  "
                f"event={obs.get('event')} "
                f"session_key={obs.get('session_key')} "
                f"recipient={obs.get('recipient')} "
                f"reply_chars={obs.get('reply_chars')} "
                f"reply_bytes={obs.get('reply_bytes')}",
                file=sys.stderr,
            )
    if json_reply_summary_observations:
        print("Observed reply json summary events (latest first):", file=sys.stderr)
        for obs in reversed(json_reply_summary_observations[-3:]):
            print(
                "  "
                f"event={obs.get('event')} "
                f"json_kind={obs.get('json_kind')} "
                f"json_available={obs.get('json_available')} "
                f"json_status={obs.get('json_status')} "
                f"json_found={obs.get('json_found')} "
                f"json_decision={obs.get('json_decision')} "
                f"json_keys={obs.get('json_keys')}",
                file=sys.stderr,
            )
    last = tail_lines(cfg.log_file, 60)
    if last:
        print("Last 60 log lines:", file=sys.stderr)
        for line in last:
            print(f"  {line}", file=sys.stderr)
    return finish(3)


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    try:
        return run_probe(config)
    except KeyboardInterrupt:
        print("\nProbe interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
