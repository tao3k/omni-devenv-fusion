#!/usr/bin/env python3
"""
One-click session trace reconstruction for omni-agent runtime logs.

Focus:
- route decision/fallback
- injection snapshot
- reflection lifecycle/hints
- memory recall/gate lifecycle
- optional suggested_link evidence
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
EVENT_RE = re.compile(r'\bevent=(?:"([^"]+)"|([^\s]+))')
KEY_VALUE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)=(?:"([^"]*)"|([^\s]+))')
TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ][^\s]+)")
LEVEL_RE = re.compile(r"\b(INFO|WARN|ERROR|DEBUG|TRACE)\b")

DEFAULT_EVENT_PREFIXES = (
    "telegram.dedup.",
    "session.route.",
    "session.injection.",
    "agent.reflection.",
    "agent.memory.",
)
DEFAULT_REQUIRED_STAGES = ("route", "injection", "reflection", "memory")
STAGE_TO_FLAG = {
    "dedup": "has_dedup",
    "route": "has_route",
    "injection": "has_injection",
    "reflection": "has_reflection",
    "memory": "has_memory",
}
STAGE_ERROR_MESSAGE = {
    "dedup": "missing dedup events",
    "route": "missing route events",
    "injection": "missing injection snapshot events",
    "reflection": "missing reflection events",
    "memory": "missing memory lifecycle events",
}


def strip_ansi(line: str) -> str:
    return ANSI_RE.sub("", line)


def _extract_timestamp(line: str) -> str | None:
    match = TIMESTAMP_RE.search(line)
    if match is None:
        return None
    return match.group(1)


def _extract_level(line: str) -> str | None:
    match = LEVEL_RE.search(line)
    if match is None:
        return None
    return match.group(1)


def _extract_event(line: str) -> str | None:
    match = EVENT_RE.search(line)
    if match is not None:
        return match.group(1) or match.group(2)
    if "suggested_link" in line:
        return "suggested_link"
    return None


def _extract_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in KEY_VALUE_RE.finditer(line):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        fields[key] = value
    return fields


def _line_matches_session(line: str, fields: dict[str, str], session_id: str | None) -> bool:
    if session_id is None:
        return True
    session_value = fields.get("session_id", "") or fields.get("session_key", "")
    if session_value == session_id:
        return True
    return session_id in line


def _line_matches_chat(line: str, fields: dict[str, str], chat_id: int | None) -> bool:
    if chat_id is None:
        return True
    normalized = str(chat_id)
    value = fields.get("chat_id", "")
    if value:
        if normalized in value:
            return True
    return f"chat_id={normalized}" in line or f"chat_id=Some({normalized})" in line


def _event_is_tracked(event: str, event_prefixes: tuple[str, ...]) -> bool:
    if event == "suggested_link":
        return True
    return any(event.startswith(prefix) for prefix in event_prefixes)


def load_trace_entries(
    log_file: Path,
    *,
    session_id: str | None = None,
    chat_id: int | None = None,
    event_prefixes: tuple[str, ...] = DEFAULT_EVENT_PREFIXES,
    max_events: int = 500,
) -> list[dict[str, Any]]:
    if not log_file.exists():
        raise FileNotFoundError(f"log file not found: {log_file}")
    entries: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        log_file.read_text(encoding="utf-8", errors="ignore").splitlines(),
        start=1,
    ):
        line = strip_ansi(raw_line)
        event = _extract_event(line)
        if event is None:
            continue
        if not _event_is_tracked(event, event_prefixes):
            continue
        fields = _extract_fields(line)
        if not _line_matches_session(line, fields, session_id):
            continue
        if not _line_matches_chat(line, fields, chat_id):
            continue

        entries.append(
            {
                "line": line_number,
                "timestamp": _extract_timestamp(line),
                "level": _extract_level(line),
                "event": event,
                "fields": fields,
                "raw": line.strip(),
            }
        )
        if len(entries) >= max_events:
            break
    return entries


def _first_index(entries: list[dict[str, Any]], event_name: str) -> int | None:
    for index, entry in enumerate(entries):
        if entry["event"] == event_name:
            return index
    return None


def build_trace_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    event_counts: dict[str, int] = {}
    for entry in entries:
        event = str(entry["event"])
        event_counts[event] = event_counts.get(event, 0) + 1

    stage_flags = {
        "has_dedup": "telegram.dedup.update_accepted" in event_counts,
        "has_route": (
            "session.route.decision_selected" in event_counts
            or "session.route.fallback_applied" in event_counts
        ),
        "has_injection": "session.injection.snapshot_created" in event_counts,
        "has_reflection": any(name.startswith("agent.reflection.") for name in event_counts),
        "has_memory": any(name.startswith("agent.memory.") for name in event_counts),
        "has_suggested_link": "suggested_link" in event_counts,
    }

    warnings: list[str] = []
    route_idx = _first_index(entries, "session.route.decision_selected")
    injection_idx = _first_index(entries, "session.injection.snapshot_created")
    if route_idx is not None and injection_idx is not None and route_idx > injection_idx:
        warnings.append("route decision appeared after injection snapshot")

    reflection_store_idx = _first_index(entries, "agent.reflection.policy_hint.stored")
    reflection_apply_idx = _first_index(entries, "agent.reflection.policy_hint.applied")
    if (
        reflection_store_idx is not None
        and reflection_apply_idx is not None
        and reflection_store_idx > reflection_apply_idx
    ):
        warnings.append("reflection hint applied before it was stored")

    recall_plan_idx = _first_index(entries, "agent.memory.recall.planned")
    recall_decision_idx = None
    for candidate in ("agent.memory.recall.injected", "agent.memory.recall.skipped"):
        idx = _first_index(entries, candidate)
        if idx is None:
            continue
        recall_decision_idx = idx if recall_decision_idx is None else min(recall_decision_idx, idx)
    if (
        recall_plan_idx is not None
        and recall_decision_idx is not None
        and recall_plan_idx > recall_decision_idx
    ):
        warnings.append("memory recall decision appeared before recall planning")

    quality_components = [
        int(stage_flags["has_route"]),
        int(stage_flags["has_injection"]),
        int(stage_flags["has_reflection"]),
        int(stage_flags["has_memory"]),
    ]
    quality_score = round((sum(quality_components) / len(quality_components)) * 100.0, 2)

    return {
        "events_total": len(entries),
        "event_counts": event_counts,
        "stage_flags": stage_flags,
        "warnings": warnings,
        "quality_score": quality_score,
    }


def evaluate_trace_health(
    summary: dict[str, Any],
    *,
    require_suggested_link: bool = False,
    required_stages: tuple[str, ...] = DEFAULT_REQUIRED_STAGES,
) -> list[str]:
    stage_flags = summary.get("stage_flags", {})
    errors: list[str] = []
    for stage in required_stages:
        flag_name = STAGE_TO_FLAG.get(stage)
        if flag_name is None:
            continue
        if not bool(stage_flags.get(flag_name, False)):
            errors.append(STAGE_ERROR_MESSAGE[stage])
    if require_suggested_link and not bool(stage_flags.get("has_suggested_link", False)):
        errors.append("missing suggested_link evidence")
    return errors


def render_markdown_report(
    entries: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    title: str = "Omni Agent Trace Reconstruction",
) -> str:
    lines: list[str] = [f"# {title}", ""]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Events: {summary['events_total']}")
    lines.append(f"- Quality score: {summary['quality_score']}")
    lines.append("")
    lines.append("### Stage Flags")
    for key, value in summary["stage_flags"].items():
        lines.append(f"- {key}: {value}")

    warnings = summary.get("warnings", [])
    lines.append("")
    lines.append("### Warnings")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    lines.append("| Line | Time | Level | Event | Notes |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in entries:
        notes = []
        for key in ("session_id", "session_key", "chat_id", "route", "confidence", "verdict"):
            value = entry["fields"].get(key)
            if value:
                notes.append(f"{key}={value}")
        lines.append(
            f"| {entry['line']} | {entry.get('timestamp') or ''} | {entry.get('level') or ''} "
            f"| `{entry['event']}` | {'; '.join(notes)} |"
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct omni-agent runtime trace from log file"
    )
    parser.add_argument("log_file", type=Path, help="Runtime log file path")
    parser.add_argument("--session-id", default="", help="Optional session_id/session_key filter")
    parser.add_argument("--chat-id", type=int, default=None, help="Optional chat_id filter")
    parser.add_argument("--max-events", type=int, default=500, help="Maximum events to include")
    parser.add_argument(
        "--required-stage",
        action="append",
        choices=tuple(STAGE_TO_FLAG.keys()),
        default=[],
        help=(
            "Required lifecycle stage for health evaluation (repeatable). "
            f"Default: {','.join(DEFAULT_REQUIRED_STAGES)}"
        ),
    )
    parser.add_argument(
        "--require-suggested-link",
        action="store_true",
        help="Fail if no suggested_link record appears in filtered trace",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail when chain warnings/errors exist"
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path")
    parser.add_argument(
        "--markdown-out", type=Path, default=None, help="Optional markdown output path"
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        entries = load_trace_entries(
            args.log_file,
            session_id=args.session_id.strip() or None,
            chat_id=args.chat_id,
            max_events=int(args.max_events),
        )
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    summary = build_trace_summary(entries)
    required_stages = tuple(args.required_stage) if args.required_stage else DEFAULT_REQUIRED_STAGES
    errors = evaluate_trace_health(
        summary,
        require_suggested_link=bool(args.require_suggested_link),
        required_stages=required_stages,
    )
    warnings = list(summary.get("warnings", []))

    payload = {
        "log_file": str(args.log_file),
        "filters": {
            "session_id": args.session_id.strip() or None,
            "chat_id": args.chat_id,
            "max_events": int(args.max_events),
            "required_stages": list(required_stages),
        },
        "summary": summary,
        "errors": errors,
        "entries": entries,
    }

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.markdown_out is not None:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown_report(entries, summary), encoding="utf-8")

    print(f"trace events: {summary['events_total']}")
    print(f"quality score: {summary['quality_score']}")
    print(f"errors: {len(errors)}")
    print(f"warnings: {len(warnings)}")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
    if warnings:
        for warning in warnings:
            print(f"[WARN] {warning}")

    if args.strict and (errors or warnings):
        return 1
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
