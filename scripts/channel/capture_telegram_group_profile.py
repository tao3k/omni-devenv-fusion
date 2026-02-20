#!/usr/bin/env python3
"""
Capture Telegram test-group chat IDs from webhook runtime logs and persist
them as reusable profile files for black-box test suites.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
PARSED_MESSAGE_RE = re.compile(
    r"Parsed message, forwarding to agent"
    r".*?session_key=(?P<session_key>[-\d:]+)"
    r".*?chat_id=Some\((?P<chat_id>-?\d+)\)"
    r'.*?chat_title=(?:None|Some\("(?P<chat_title>[^"]*)"\))'
    r'.*?chat_type=Some\("(?P<chat_type>[^"]+)"\)'
)


@dataclass(frozen=True)
class GroupObservation:
    title: str
    chat_id: int
    chat_type: str
    user_id: int | None
    line_index: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Persist Telegram group mappings for black-box tests. "
            "Reads webhook logs and writes JSON/env profile files."
        )
    )
    parser.add_argument(
        "--titles",
        default="Test1,Test2,Test3",
        help="Comma-separated group titles in desired A/B/C order (default: Test1,Test2,Test3).",
    )
    parser.add_argument(
        "--log-file",
        default=".run/logs/omni-agent-webhook.log",
        help="Webhook runtime log file path.",
    )
    parser.add_argument(
        "--output-json",
        default=".run/config/agent-channel-groups.json",
        help="Output profile JSON path.",
    )
    parser.add_argument(
        "--output-env",
        default=".run/config/agent-channel-groups.env",
        help="Output profile env file path.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help=(
            "Optional fixed Telegram user id for all sessions "
            "(default: inferred from matched session_key values)."
        ),
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow missing titles and write only discovered mappings.",
    )
    return parser.parse_args()


def normalize_title(value: str) -> str:
    return value.strip().casefold()


def parse_user_id(session_key: str) -> int | None:
    parts = session_key.split(":")
    if len(parts) == 2:
        return int(parts[1])
    if len(parts) == 3:
        return int(parts[2])
    return None


def discover_groups(log_file: Path, targets: list[str]) -> dict[str, GroupObservation]:
    normalized_targets = {normalize_title(title): title for title in targets}
    found: dict[str, GroupObservation] = {}

    for idx, raw_line in enumerate(
        log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    ):
        line = ANSI_ESCAPE_RE.sub("", raw_line)
        match = PARSED_MESSAGE_RE.search(line)
        if not match:
            continue

        chat_type = match.group("chat_type")
        if chat_type not in {"group", "supergroup"}:
            continue

        raw_title = (match.group("chat_title") or "").strip()
        if not raw_title:
            continue

        normalized = normalize_title(raw_title)
        if normalized not in normalized_targets:
            continue

        canonical_title = normalized_targets[normalized]
        found[canonical_title] = GroupObservation(
            title=raw_title,
            chat_id=int(match.group("chat_id")),
            chat_type=chat_type,
            user_id=parse_user_id(match.group("session_key")),
            line_index=idx,
        )

    return found


def quote_env(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def write_profile(
    *,
    output_json: Path,
    output_env: Path,
    ordered_titles: list[str],
    discovered: dict[str, GroupObservation],
    user_id_override: int | None,
) -> None:
    present_titles = [title for title in ordered_titles if title in discovered]

    chosen_user_id: int | None = user_id_override
    if chosen_user_id is None:
        user_samples = [
            discovered[title].user_id for title in present_titles if discovered[title].user_id
        ]
        if user_samples:
            chosen_user_id = Counter(user_samples).most_common(1)[0][0]

    user_a = chosen_user_id
    user_b = chosen_user_id + 1 if chosen_user_id is not None else None
    user_c = chosen_user_id + 2 if chosen_user_id is not None else None

    session_aliases = ("a", "b", "c")
    sessions: dict[str, dict[str, object]] = {}
    for index, (alias, title) in enumerate(zip(session_aliases, present_titles, strict=False)):
        obs = discovered[title]
        alias_user = user_a if index == 0 else (user_b if index == 1 else user_c)
        sessions[alias] = {
            "title": title,
            "observed_title": obs.title,
            "chat_id": obs.chat_id,
            "chat_type": obs.chat_type,
            "user_id": alias_user,
            "line_index": obs.line_index,
        }

    profile = {
        "generated_at": datetime.now(UTC).isoformat(),
        "titles_order": ordered_titles,
        "present_titles": present_titles,
        "sessions": sessions,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(profile, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    env_lines: list[str] = [
        "# Generated by scripts/channel/capture_telegram_group_profile.py",
        f"OMNI_TEST_GROUP_PROFILE_JSON={quote_env(str(output_json))}",
    ]

    def set_pair(key: str, value: str | int) -> None:
        if isinstance(value, int):
            env_lines.append(f"{key}={value}")
        else:
            env_lines.append(f"{key}={quote_env(value)}")

    if "a" in sessions:
        set_pair("OMNI_TEST_CHAT_ID", int(sessions["a"]["chat_id"]))
        set_pair("OMNI_TEST_CHAT_TITLE_A", str(sessions["a"]["title"]))
    if "b" in sessions:
        set_pair("OMNI_TEST_CHAT_B", int(sessions["b"]["chat_id"]))
        set_pair("OMNI_TEST_CHAT_TITLE_B", str(sessions["b"]["title"]))
    if "c" in sessions:
        set_pair("OMNI_TEST_CHAT_C", int(sessions["c"]["chat_id"]))
        set_pair("OMNI_TEST_CHAT_TITLE_C", str(sessions["c"]["title"]))
    if user_a is not None:
        set_pair("OMNI_TEST_USER_ID", user_a)
    if user_b is not None:
        set_pair("OMNI_TEST_USER_B", user_b)
    if user_c is not None:
        set_pair("OMNI_TEST_USER_C", user_c)

    output_env.parent.mkdir(parents=True, exist_ok=True)
    output_env.write_text("\n".join(env_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    titles = [item.strip() for item in args.titles.split(",") if item.strip()]
    if len(titles) < 1:
        raise ValueError("--titles must include at least one title.")

    log_file = Path(args.log_file)
    if not log_file.exists():
        raise FileNotFoundError(f"log file not found: {log_file}")

    discovered = discover_groups(log_file=log_file, targets=titles)
    missing = [title for title in titles if title not in discovered]
    if missing and not args.allow_missing:
        missing_joined = ", ".join(missing)
        raise RuntimeError(
            f"missing group titles in log: {missing_joined}. "
            "Send '/help' (or any message) in each target group and retry."
        )

    output_json = Path(args.output_json)
    output_env = Path(args.output_env)
    write_profile(
        output_json=output_json,
        output_env=output_env,
        ordered_titles=titles,
        discovered=discovered,
        user_id_override=args.user_id,
    )

    present = [title for title in titles if title in discovered]
    print("Captured Telegram test-group profile.")
    print(f"  present_titles={present}")
    if missing:
        print(f"  missing_titles={missing}")
    for title in present:
        obs = discovered[title]
        print(
            "  title={title} chat_id={chat_id} chat_type={chat_type}".format(
                title=title,
                chat_id=obs.chat_id,
                chat_type=obs.chat_type,
            )
        )
    print(f"  output_json={output_json}")
    print(f"  output_env={output_env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
