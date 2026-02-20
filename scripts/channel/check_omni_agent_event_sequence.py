#!/usr/bin/env python3
"""
Validate key observability event sequence for Telegram webhook/session/memory flows.

Compatibility target:
  scripts/channel/check-omni-agent-event-sequence.sh
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class Reporter:
    def __init__(self) -> None:
        self.passes = 0
        self.warnings = 0
        self.failures = 0

    def emit_pass(self, message: str) -> None:
        self.passes += 1
        print(f"[PASS] {message}")

    def emit_warn(self, message: str) -> None:
        self.warnings += 1
        print(f"[WARN] {message}")

    def emit_fail(self, message: str) -> None:
        self.failures += 1
        print(f"[FAIL] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_omni_agent_event_sequence.py",
        description=(
            "Validate key observability event sequence for Telegram webhook + session gate + "
            "memory persistence flows."
        ),
    )
    parser.add_argument("log_file", help="Path to agent log file.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    parser.add_argument(
        "--require-memory",
        action="store_true",
        help="Fail if memory backend lifecycle events are missing.",
    )
    parser.add_argument(
        "--expect-memory-backend",
        choices=("local", "valkey"),
        default="",
        help="Require backend in agent.memory.backend.initialized to match.",
    )
    return parser.parse_args()


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def count_event(lines: list[str], event: str) -> int:
    return sum(1 for line in lines if event in line)


def first_line(lines: list[str], event: str) -> int:
    for idx, line in enumerate(lines, start=1):
        if event in line:
            return idx
    return 0


def first_line_any(lines: list[str], events: list[str]) -> int:
    values = [first_line(lines, event) for event in events]
    positives = [value for value in values if value > 0]
    return min(positives) if positives else 0


def check_order(
    reporter: Reporter,
    earlier_label: str,
    earlier_line: int,
    later_label: str,
    later_line: int,
    description: str,
) -> None:
    if earlier_line == 0 or later_line == 0:
        reporter.emit_warn(f"{description} (skipped: missing '{earlier_label}' or '{later_label}')")
        return

    if earlier_line < later_line:
        reporter.emit_pass(
            f"{description} (lines: {earlier_label}={earlier_line}, {later_label}={later_line})"
        )
    else:
        reporter.emit_fail(
            f"{description} (unexpected order: {earlier_label}={earlier_line}, "
            f"{later_label}={later_line})"
        )


def run_checks(
    lines: list[str],
    stripped_lines: list[str],
    strict: bool,
    require_memory: bool,
    expect_memory_backend: str,
) -> int:
    reporter = Reporter()

    count_dedup_evaluated = count_event(lines, "telegram.dedup.evaluated")
    count_dedup_accepted = count_event(lines, "telegram.dedup.update_accepted")
    count_gate_backend_initialized = count_event(lines, "session.gate.backend.initialized")
    count_gate_backend_valkey = sum(
        1
        for line in stripped_lines
        if "session.gate.backend.initialized" in line and 'backend="valkey"' in line
    )
    count_gate_backend_memory = sum(
        1
        for line in stripped_lines
        if "session.gate.backend.initialized" in line and 'backend="memory"' in line
    )
    count_gate_acquired = count_event(lines, "session.gate.lease.acquired")
    count_gate_released = count_event(lines, "session.gate.lease.released")
    count_window_loaded = count_event(lines, "session.window_slots.loaded")
    count_window_appended = count_event(lines, "session.window_slots.appended")
    count_retry_failed = count_event(lines, "session.valkey.command.retry_failed")
    count_retry_succeeded = count_event(lines, "session.valkey.command.retry_succeeded")

    count_memory_backend_initialized = count_event(lines, "agent.memory.backend.initialized")
    count_memory_load_succeeded = count_event(lines, "agent.memory.state_load_succeeded")
    count_memory_load_failed = count_event(lines, "agent.memory.state_load_failed")
    count_memory_save_succeeded = count_event(lines, "agent.memory.state_save_succeeded")
    count_memory_save_failed = count_event(lines, "agent.memory.state_save_failed")
    count_memory_recall_planned = count_event(lines, "agent.memory.recall.planned")
    count_memory_recall_injected = count_event(lines, "agent.memory.recall.injected")
    count_memory_recall_skipped = count_event(lines, "agent.memory.recall.skipped")

    if count_dedup_evaluated > 0:
        reporter.emit_pass(f"dedup evaluation events present (count={count_dedup_evaluated})")
    else:
        reporter.emit_fail("dedup evaluation events missing (expected: telegram.dedup.evaluated)")

    if count_dedup_accepted > 0:
        reporter.emit_pass(f"dedup accepted-update events present (count={count_dedup_accepted})")
        if (count_window_loaded + count_window_appended) > 0:
            reporter.emit_pass(
                "session window activity events present "
                f"(loaded={count_window_loaded}, appended={count_window_appended})"
            )
        else:
            reporter.emit_warn("no session window load/append events found after accepted updates")

        if count_gate_acquired > 0:
            reporter.emit_pass(f"session gate acquire events present (count={count_gate_acquired})")
            if count_gate_released > 0:
                reporter.emit_pass(
                    f"session gate release events present (count={count_gate_released})"
                )
            else:
                reporter.emit_warn(
                    "session gate release events missing; check in-flight shutdowns or lease cleanup"
                )

            line_dedup_accepted = first_line(lines, "telegram.dedup.update_accepted")
            line_gate_acquired = first_line(lines, "session.gate.lease.acquired")
            line_window_appended = first_line(lines, "session.window_slots.appended")

            check_order(
                reporter,
                "telegram.dedup.update_accepted",
                line_dedup_accepted,
                "session.gate.lease.acquired",
                line_gate_acquired,
                "dedup acceptance should precede session gate acquisition",
            )
            check_order(
                reporter,
                "session.gate.lease.acquired",
                line_gate_acquired,
                "session.window_slots.appended",
                line_window_appended,
                "session gate acquisition should precede window append",
            )
        else:
            if count_gate_backend_valkey > 0:
                reporter.emit_fail(
                    "session gate backend is valkey but no lease acquire events were observed"
                )
            elif count_gate_backend_memory > 0:
                reporter.emit_warn(
                    "session gate backend is memory; no lease events observed "
                    "(expected in command-only or single-process flows)"
                )
            elif count_gate_backend_initialized > 0:
                reporter.emit_warn(
                    "session gate backend initialized but backend mode could not be inferred; "
                    "skipping lease checks"
                )
            else:
                reporter.emit_warn(
                    "session gate backend initialization event missing; skipping lease checks"
                )
    else:
        reporter.emit_warn("no accepted updates found (telegram.dedup.update_accepted)")

    if count_retry_failed > 0:
        if count_retry_succeeded > 0:
            reporter.emit_pass(
                "valkey retry recovery observed "
                f"(failed={count_retry_failed}, succeeded={count_retry_succeeded})"
            )
        else:
            reporter.emit_warn(
                "valkey retries failed without observed recovery "
                f"(retry_failed={count_retry_failed})"
            )
    else:
        reporter.emit_pass("no valkey retry failures observed")

    if count_memory_backend_initialized > 0:
        reporter.emit_pass(
            f"memory backend initialization events present (count={count_memory_backend_initialized})"
        )

        if (count_memory_load_succeeded + count_memory_load_failed) > 0:
            reporter.emit_pass(
                "memory load lifecycle events present "
                f"(load_ok={count_memory_load_succeeded}, load_fail={count_memory_load_failed})"
            )
        else:
            reporter.emit_fail(
                "memory backend initialized but no memory load lifecycle event found"
            )

        if count_memory_save_failed > 0:
            reporter.emit_fail(f"memory save failures detected (count={count_memory_save_failed})")
        elif count_memory_save_succeeded > 0:
            reporter.emit_pass(
                f"memory save success events present (count={count_memory_save_succeeded})"
            )
        else:
            reporter.emit_warn("no memory save events observed")

        if count_memory_recall_planned > 0:
            reporter.emit_pass(
                f"memory recall planning events present (count={count_memory_recall_planned})"
            )
            if (count_memory_recall_injected + count_memory_recall_skipped) > 0:
                reporter.emit_pass(
                    "memory recall decision events present "
                    f"(injected={count_memory_recall_injected}, "
                    f"skipped={count_memory_recall_skipped})"
                )
            else:
                reporter.emit_fail("memory recall planned but no recall decision event found")
        else:
            if require_memory:
                reporter.emit_fail("memory recall planning events missing while memory is required")
            else:
                reporter.emit_warn("memory recall planning events missing")

        line_memory_backend = first_line(lines, "agent.memory.backend.initialized")
        line_memory_load = first_line_any(
            lines,
            ["agent.memory.state_load_succeeded", "agent.memory.state_load_failed"],
        )
        line_memory_recall_planned = first_line(lines, "agent.memory.recall.planned")
        line_memory_recall_decision = first_line_any(
            lines,
            ["agent.memory.recall.injected", "agent.memory.recall.skipped"],
        )
        check_order(
            reporter,
            "agent.memory.backend.initialized",
            line_memory_backend,
            "agent.memory.state_load_(succeeded|failed)",
            line_memory_load,
            "memory backend initialization should precede memory load lifecycle event",
        )
        check_order(
            reporter,
            "agent.memory.backend.initialized",
            line_memory_backend,
            "agent.memory.recall.planned",
            line_memory_recall_planned,
            "memory backend initialization should precede memory recall planning",
        )
        check_order(
            reporter,
            "agent.memory.recall.planned",
            line_memory_recall_planned,
            "agent.memory.recall.(injected|skipped)",
            line_memory_recall_decision,
            "memory recall planning should precede recall decision logging",
        )
    else:
        if require_memory:
            reporter.emit_fail(
                "memory lifecycle events are required but backend initialization event is missing"
            )
        else:
            reporter.emit_warn(
                "memory backend initialization event missing (memory may be disabled)"
            )

    if expect_memory_backend:
        expected_backend_re = re.compile(
            rf'backend="?{re.escape(expect_memory_backend)}"?\b|'
            rf'"backend"\s*:\s*"{re.escape(expect_memory_backend)}"'
        )
        count_expected_backend = sum(
            1
            for line in stripped_lines
            if "agent.memory.backend.initialized" in line and expected_backend_re.search(line)
        )
        if count_expected_backend > 0:
            reporter.emit_pass(
                "memory backend expectation matched "
                f"(expected={expect_memory_backend}, count={count_expected_backend})"
            )
        else:
            reporter.emit_fail(
                f"memory backend expectation not matched (expected={expect_memory_backend})"
            )

    if strict and reporter.warnings > 0:
        reporter.emit_fail(
            f"strict mode enabled: warnings are treated as failures (warnings={reporter.warnings})"
        )

    print()
    print(f"Summary: pass={reporter.passes} warn={reporter.warnings} fail={reporter.failures}")
    return 1 if reporter.failures > 0 else 0


def main() -> int:
    args = parse_args()
    log_file = Path(args.log_file)
    if not log_file.is_file():
        print(f"Error: log file not found: {log_file}", file=sys.stderr)
        return 2

    content = log_file.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    stripped_lines = [strip_ansi(line) for line in lines]
    return run_checks(
        lines=lines,
        stripped_lines=stripped_lines,
        strict=args.strict,
        require_memory=args.require_memory,
        expect_memory_backend=args.expect_memory_backend,
    )


if __name__ == "__main__":
    raise SystemExit(main())
