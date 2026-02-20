#!/usr/bin/env python3
"""Structured runtime monitor for long-running channel processes."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ERROR_MARKERS = (
    "panic",
    "thread '",
    "Error:",
    "ERROR",
    "error:",
    "Address already in use",
    "tools/call: Mcp error",
)

EVENT_TOKEN_RE = re.compile(r"\bevent\s*=\s*(?:\"|')?([A-Za-z0-9_.:-]+)")


@dataclass(slots=True)
class MonitorStats:
    total_lines: int = 0
    error_lines: int = 0
    first_error_line: str | None = None
    saw_webhook: bool = False
    saw_user_dispatch: bool = False
    saw_bot_reply: bool = False
    last_event: str | None = None


@dataclass(slots=True)
class MonitorTerminationState:
    requested_signal: int | None = None


def now_utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_exit_code(returncode: int) -> int:
    if returncode < 0:
        return 128 + abs(returncode)
    return returncode


def classify_exit(returncode: int) -> dict[str, str | int | None]:
    if returncode == 0:
        return {"kind": "ok", "exit_code": 0, "signal": None, "signal_name": None}
    if returncode < 0:
        signal_num = abs(returncode)
        signal_name = signal.Signals(signal_num).name
        return {
            "kind": "signal",
            "exit_code": 128 + signal_num,
            "signal": signal_num,
            "signal_name": signal_name,
        }
    signal_num = returncode - 128 if returncode >= 128 else None
    signal_name = None
    if signal_num:
        try:
            signal_name = signal.Signals(signal_num).name
        except ValueError:
            signal_name = f"SIG{signal_num}"
    return {
        "kind": "nonzero",
        "exit_code": returncode,
        "signal": signal_num,
        "signal_name": signal_name,
    }


def extract_event_token(line: str) -> str | None:
    match = EVENT_TOKEN_RE.search(line)
    if match:
        return match.group(1)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a command with structured exit/observability reporting."
    )
    parser.add_argument("--log-file", required=True, help="Plain-text streaming log output file.")
    parser.add_argument(
        "--report-file",
        required=True,
        help="Structured JSON exit report file (overwritten per run).",
    )
    parser.add_argument(
        "--report-jsonl",
        default="",
        help="Optional JSONL file to append one report entry per run.",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=40,
        help="Number of trailing process output lines to include in report.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute (prefix with --).",
    )
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("No command provided. Use `-- <command> [args...]`.")
    return args


def write_report(report_file: Path, report_jsonl: Path | None, report: dict) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if report_jsonl is not None:
        report_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with report_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, ensure_ascii=False) + "\n")


def run_monitored_process(
    command: list[str],
    log_file: Path,
    report_file: Path,
    report_jsonl: Path | None,
    tail_lines: int,
) -> int:
    start_wall = now_utc_iso()
    start_monotonic = time.monotonic()
    stats = MonitorStats()
    termination = MonitorTerminationState()
    event_counts: Counter[str] = Counter()
    recent_lines: deque[str] = deque(maxlen=max(tail_lines, 1))
    pid: int | None = None

    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        pid = proc.pid
    except OSError as error:
        end_wall = now_utc_iso()
        report = {
            "schema_version": 1,
            "start_time_utc": start_wall,
            "end_time_utc": end_wall,
            "duration_ms": 0,
            "command": command,
            "pid": None,
            "exit": {"kind": "spawn_error", "exit_code": 127, "signal": None, "signal_name": None},
            "spawn_error": str(error),
            "stats": {},
            "events": {"last_event": None, "counts": {}},
            "tail": [],
        }
        write_report(report_file, report_jsonl, report)
        print(
            f"[monitor] spawn failed: {error}. report={report_file}",
            file=sys.stderr,
            flush=True,
        )
        return 127

    interrupted = False
    previous_signal_handlers: dict[int, signal.Handlers] = {}

    def _terminate_handler(signum: int, _frame: object) -> None:
        if termination.requested_signal is None:
            termination.requested_signal = signum
        try:
            if proc.poll() is None:
                proc.send_signal(signum)
        except ProcessLookupError:
            pass

    for signum in (signal.SIGTERM, signal.SIGHUP):
        previous_signal_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, _terminate_handler)

    with log_file.open("a", encoding="utf-8") as output:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                print(line, flush=True)
                output.write(line + "\n")
                output.flush()

                stats.total_lines += 1
                recent_lines.append(line)
                if any(marker in line for marker in ERROR_MARKERS):
                    stats.error_lines += 1
                    if stats.first_error_line is None:
                        stats.first_error_line = line
                if "Webhook received Telegram update" in line:
                    stats.saw_webhook = True
                if "← User:" in line:
                    stats.saw_user_dispatch = True
                if "→ Bot:" in line:
                    stats.saw_bot_reply = True
                event_token = extract_event_token(line)
                if event_token:
                    stats.last_event = event_token
                    event_counts[event_token] += 1
        except KeyboardInterrupt:
            interrupted = True
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass

    for signum, handler in previous_signal_handlers.items():
        signal.signal(signum, handler)

    if interrupted:
        try:
            returncode = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait()
    else:
        returncode = proc.wait()

    duration_ms = int((time.monotonic() - start_monotonic) * 1000)
    end_wall = now_utc_iso()
    exit_info = classify_exit(returncode)
    report = {
        "schema_version": 1,
        "start_time_utc": start_wall,
        "end_time_utc": end_wall,
        "duration_ms": duration_ms,
        "command": command,
        "pid": pid,
        "returncode_raw": returncode,
        "exit": exit_info,
        "stats": {
            "total_lines": stats.total_lines,
            "error_lines": stats.error_lines,
            "first_error_line": stats.first_error_line,
            "saw_webhook": stats.saw_webhook,
            "saw_user_dispatch": stats.saw_user_dispatch,
            "saw_bot_reply": stats.saw_bot_reply,
        },
        "events": {
            "last_event": stats.last_event,
            "counts": dict(event_counts.most_common(20)),
        },
        "tail": list(recent_lines),
        "environment": {
            "cwd": os.getcwd(),
            "log_file": str(log_file),
        },
    }
    if termination.requested_signal is not None:
        report["termination"] = {
            "requested_signal": termination.requested_signal,
            "requested_signal_name": signal.Signals(termination.requested_signal).name,
        }
    write_report(report_file, report_jsonl, report)

    print(
        "[monitor] "
        f"exit_kind={exit_info['kind']} "
        f"exit_code={exit_info['exit_code']} "
        f"signal={exit_info['signal_name'] or ''} "
        f"duration_ms={duration_ms} "
        f"report={report_file}",
        file=sys.stderr,
        flush=True,
    )
    if stats.first_error_line:
        print(f"[monitor] first_error_line={stats.first_error_line}", file=sys.stderr, flush=True)

    return normalize_exit_code(returncode)


def main() -> int:
    args = parse_args()
    report_jsonl = Path(args.report_jsonl) if args.report_jsonl else None
    return run_monitored_process(
        command=args.command,
        log_file=Path(args.log_file),
        report_file=Path(args.report_file),
        report_jsonl=report_jsonl,
        tail_lines=args.tail_lines,
    )


if __name__ == "__main__":
    raise SystemExit(main())
