#!/usr/bin/env python3
"""
Unified acceptance runner for Telegram channel black-box validation.

Pipeline:
1) Capture group profile (Test1/Test2/Test3)
2) Command event probes
3) Dedup probe
4) Concurrent session probe
5) Session matrix
6) Complex control-plane scenario
7) Memory evolution DAG scenario
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_WEBHOOK_LOG = ".run/logs/omni-agent-webhook.log"
DEFAULT_REPORT_JSON = ".run/reports/agent-channel-acceptance.json"
DEFAULT_REPORT_MARKDOWN = ".run/reports/agent-channel-acceptance.md"
DEFAULT_GROUP_PROFILE_JSON = ".run/config/agent-channel-groups.json"
DEFAULT_GROUP_PROFILE_ENV = ".run/config/agent-channel-groups.env"

DEFAULT_MATRIX_JSON = ".run/reports/agent-channel-session-matrix.json"
DEFAULT_MATRIX_MARKDOWN = ".run/reports/agent-channel-session-matrix.md"
DEFAULT_COMPLEX_JSON = ".run/reports/agent-channel-complex-scenarios.json"
DEFAULT_COMPLEX_MARKDOWN = ".run/reports/agent-channel-complex-scenarios.md"
DEFAULT_MEMORY_JSON = ".run/reports/agent-channel-memory-evolution.json"
DEFAULT_MEMORY_MARKDOWN = ".run/reports/agent-channel-memory-evolution.md"

DEFAULT_COMPLEX_DATASET = "scripts/channel/fixtures/complex_blackbox_scenarios.json"
DEFAULT_MEMORY_DATASET = "scripts/channel/fixtures/memory_evolution_complex_scenarios.json"
DEFAULT_MEMORY_SCENARIO = "memory_self_correction_high_complexity_dag"


@dataclass(frozen=True)
class StepResult:
    step: str
    title: str
    command: tuple[str, ...]
    returncode: int
    duration_ms: int
    attempts: int
    passed: bool
    expected_outputs: tuple[str, ...]
    missing_outputs: tuple[str, ...]
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True)
class AcceptanceConfig:
    titles: str
    log_file: Path
    output_json: Path
    output_markdown: Path
    group_profile_json: Path
    group_profile_env: Path
    max_wait: int
    max_idle_secs: int
    group_thread_id: int | None
    group_thread_id_b: int | None
    evolution_max_wait: int
    evolution_max_idle_secs: int
    evolution_max_parallel: int
    retries: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end Telegram channel black-box acceptance pipeline."
    )
    parser.add_argument(
        "--titles",
        default="Test1,Test2,Test3",
        help="Group titles for capture step (default: Test1,Test2,Test3).",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_WEBHOOK_LOG,
        help=f"Webhook runtime log file path (default: {DEFAULT_WEBHOOK_LOG}).",
    )
    parser.add_argument(
        "--output-json",
        default=DEFAULT_REPORT_JSON,
        help=f"Acceptance summary JSON path (default: {DEFAULT_REPORT_JSON}).",
    )
    parser.add_argument(
        "--output-markdown",
        default=DEFAULT_REPORT_MARKDOWN,
        help=f"Acceptance summary markdown path (default: {DEFAULT_REPORT_MARKDOWN}).",
    )
    parser.add_argument(
        "--group-profile-json",
        default=DEFAULT_GROUP_PROFILE_JSON,
        help=f"Captured group profile JSON path (default: {DEFAULT_GROUP_PROFILE_JSON}).",
    )
    parser.add_argument(
        "--group-profile-env",
        default=DEFAULT_GROUP_PROFILE_ENV,
        help=f"Captured group profile env path (default: {DEFAULT_GROUP_PROFILE_ENV}).",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_WAIT_SECS", "40")),
        help="Max wait seconds for standard black-box steps (default: 40).",
    )
    parser.add_argument(
        "--max-idle-secs",
        type=int,
        default=int(os.environ.get("OMNI_BLACKBOX_MAX_IDLE_SECS", "25")),
        help="Max idle seconds for standard black-box steps (default: 25).",
    )
    parser.add_argument(
        "--group-thread-id",
        type=int,
        default=None,
        help=(
            "Optional Telegram topic thread id for thread-aware acceptance checks. "
            "Falls back to $OMNI_TEST_GROUP_THREAD_ID."
        ),
    )
    parser.add_argument(
        "--group-thread-id-b",
        type=int,
        default=None,
        help=(
            "Optional secondary topic thread id for cross-topic checks. "
            "Falls back to $OMNI_TEST_GROUP_THREAD_B; defaults to thread A + 1."
        ),
    )
    parser.add_argument(
        "--evolution-max-wait",
        type=int,
        default=90,
        help="Max wait seconds for memory evolution scenario (default: 90).",
    )
    parser.add_argument(
        "--evolution-max-idle-secs",
        type=int,
        default=60,
        help="Max idle seconds for memory evolution scenario (default: 60).",
    )
    parser.add_argument(
        "--evolution-max-parallel",
        type=int,
        default=4,
        help="Max parallel wave probes for memory evolution scenario (default: 4).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry attempts per step on failure (default: 2).",
    )
    return parser.parse_args()


def _tail_text(value: str, max_lines: int = 40) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    return "\n".join(lines[-max_lines:])


def run_step(
    *,
    step: str,
    title: str,
    cmd: list[str],
    expected_outputs: list[Path],
    attempts: int,
) -> StepResult:
    started = time.perf_counter()
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration_ms = int((time.perf_counter() - started) * 1000)

    missing_outputs = tuple(str(path) for path in expected_outputs if not path.exists())
    passed = completed.returncode == 0 and len(missing_outputs) == 0

    return StepResult(
        step=step,
        title=title,
        command=tuple(cmd),
        returncode=completed.returncode,
        duration_ms=duration_ms,
        attempts=attempts,
        passed=passed,
        expected_outputs=tuple(str(path) for path in expected_outputs),
        missing_outputs=missing_outputs,
        stdout_tail=_tail_text(completed.stdout),
        stderr_tail=_tail_text(completed.stderr),
    )


def build_config(args: argparse.Namespace) -> AcceptanceConfig:
    if args.max_wait <= 0:
        raise ValueError("--max-wait must be positive")
    if args.max_idle_secs <= 0:
        raise ValueError("--max-idle-secs must be positive")
    if args.evolution_max_wait <= 0:
        raise ValueError("--evolution-max-wait must be positive")
    if args.evolution_max_idle_secs <= 0:
        raise ValueError("--evolution-max-idle-secs must be positive")
    if args.evolution_max_parallel <= 0:
        raise ValueError("--evolution-max-parallel must be positive")
    if args.retries <= 0:
        raise ValueError("--retries must be positive")
    group_thread_id = args.group_thread_id
    if group_thread_id is None:
        raw = os.environ.get("OMNI_TEST_GROUP_THREAD_ID", "").strip()
        if raw:
            try:
                group_thread_id = int(raw)
            except ValueError as error:
                raise ValueError(
                    f"OMNI_TEST_GROUP_THREAD_ID must be an integer, got '{raw}'."
                ) from error

    group_thread_id_b = args.group_thread_id_b
    if group_thread_id_b is None:
        raw = os.environ.get("OMNI_TEST_GROUP_THREAD_B", "").strip()
        if raw:
            try:
                group_thread_id_b = int(raw)
            except ValueError as error:
                raise ValueError(
                    f"OMNI_TEST_GROUP_THREAD_B must be an integer, got '{raw}'."
                ) from error
    if group_thread_id_b is None and group_thread_id is not None:
        group_thread_id_b = group_thread_id + 1
    if (
        group_thread_id is not None
        and group_thread_id_b is not None
        and int(group_thread_id) == int(group_thread_id_b)
    ):
        raise ValueError(
            "group thread acceptance checks require distinct thread ids; "
            f"got both={group_thread_id}."
        )

    return AcceptanceConfig(
        titles=args.titles.strip(),
        log_file=Path(args.log_file),
        output_json=Path(args.output_json),
        output_markdown=Path(args.output_markdown),
        group_profile_json=Path(args.group_profile_json),
        group_profile_env=Path(args.group_profile_env),
        max_wait=int(args.max_wait),
        max_idle_secs=int(args.max_idle_secs),
        group_thread_id=group_thread_id,
        group_thread_id_b=group_thread_id_b,
        evolution_max_wait=int(args.evolution_max_wait),
        evolution_max_idle_secs=int(args.evolution_max_idle_secs),
        evolution_max_parallel=int(args.evolution_max_parallel),
        retries=int(args.retries),
    )


def to_markdown(report: dict[str, object]) -> str:
    lines: list[str] = [
        "# Agent Channel Acceptance Report",
        "",
        "## Overview",
        f"- started_at: `{report['started_at']}`",
        f"- finished_at: `{report['finished_at']}`",
        f"- duration_ms: `{report['duration_ms']}`",
        f"- overall: `{'PASS' if report['overall_passed'] else 'FAIL'}`",
        (
            f"- steps: `{report['summary']['passed']}/{report['summary']['total']}` passed"  # type: ignore[index]
        ),
        "",
        "## Outputs",
        f"- group_profile_json: `{report['artifacts']['group_profile_json']}`",  # type: ignore[index]
        f"- group_profile_env: `{report['artifacts']['group_profile_env']}`",  # type: ignore[index]
        f"- matrix_json: `{report['artifacts']['matrix_json']}`",  # type: ignore[index]
        f"- complex_json: `{report['artifacts']['complex_json']}`",  # type: ignore[index]
        f"- memory_evolution_json: `{report['artifacts']['memory_evolution_json']}`",  # type: ignore[index]
        "",
        "## Step Results",
        "| Step | Result | Return Code | Attempts | Duration (ms) |",
        "|---|---|---:|---:|---:|",
    ]

    for step in report["steps"]:  # type: ignore[index]
        status = "PASS" if step["passed"] else "FAIL"
        lines.append(
            f"| `{step['step']}` | {status} | {step['returncode']} | "
            f"{step['attempts']} | {step['duration_ms']} |"
        )

    failed_steps = [step for step in report["steps"] if not step["passed"]]  # type: ignore[index]
    lines.append("")
    lines.append("## Failure Tails")
    if not failed_steps:
        lines.append("- None")
        return "\n".join(lines) + "\n"

    for step in failed_steps:
        lines.append(f"### {step['step']}")
        lines.append("")
        lines.append("```text")
        if step["missing_outputs"]:
            lines.append(f"missing_outputs={step['missing_outputs']}")
        if step["stderr_tail"]:
            lines.append(step["stderr_tail"])
        elif step["stdout_tail"]:
            lines.append(step["stdout_tail"])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def write_report(report: dict[str, object], *, output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    output_markdown.write_text(to_markdown(report), encoding="utf-8")


def run_pipeline(cfg: AcceptanceConfig) -> dict[str, object]:
    started = datetime.now(UTC)
    timer_start = time.perf_counter()
    steps: list[StepResult] = []

    python_exe = sys.executable

    def execute(step: str, title: str, cmd: list[str], expected_outputs: list[Path]) -> bool:
        print(f">>> {title}", flush=True)
        print("+ " + " ".join(shlex.quote(part) for part in cmd), flush=True)
        result: StepResult | None = None
        for attempt in range(1, cfg.retries + 1):
            result = run_step(
                step=step,
                title=title,
                cmd=cmd,
                expected_outputs=expected_outputs,
                attempts=attempt,
            )
            if result.passed:
                break
            if attempt < cfg.retries:
                print(
                    f"  attempt={attempt} failed; retrying ({attempt + 1}/{cfg.retries})...",
                    flush=True,
                )
                time.sleep(1.0)

        assert result is not None
        steps.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(
            (
                f"  result={status} returncode={result.returncode} attempts={result.attempts} "
                f"duration_ms={result.duration_ms}"
            ),
            flush=True,
        )
        if result.missing_outputs:
            print(f"  missing_outputs={list(result.missing_outputs)}", flush=True)
        return result.passed

    continue_pipeline = execute(
        "capture_groups",
        "Capture Telegram group profile",
        [
            python_exe,
            "scripts/channel/capture_telegram_group_profile.py",
            "--titles",
            cfg.titles,
            "--log-file",
            str(cfg.log_file),
            "--output-json",
            str(cfg.group_profile_json),
            "--output-env",
            str(cfg.group_profile_env),
        ],
        [cfg.group_profile_json, cfg.group_profile_env],
    )
    if continue_pipeline:
        continue_pipeline = execute(
            "command_events",
            "Run command event probes",
            [
                "bash",
                "scripts/channel/test-omni-agent-command-events.sh",
                "--max-wait",
                str(cfg.max_wait),
                "--max-idle-secs",
                str(cfg.max_idle_secs),
            ],
            [],
        )
    if continue_pipeline and cfg.group_thread_id is not None and cfg.group_thread_id_b is not None:
        continue_pipeline = execute(
            "command_events_topic_isolation",
            "Run command event topic-isolation probes",
            [
                "bash",
                "scripts/channel/test-omni-agent-command-events.sh",
                "--suite",
                "admin",
                "--assert-admin-topic-isolation",
                "--group-thread-id",
                str(cfg.group_thread_id),
                "--group-thread-id-b",
                str(cfg.group_thread_id_b),
                "--max-wait",
                str(cfg.max_wait),
                "--max-idle-secs",
                str(cfg.max_idle_secs),
            ],
            [],
        )
    if continue_pipeline:
        continue_pipeline = execute(
            "dedup",
            "Run dedup probe",
            [
                "bash",
                "scripts/channel/test-omni-agent-dedup-events.sh",
                "--max-wait",
                str(cfg.max_wait),
            ],
            [],
        )
    if continue_pipeline:
        continue_pipeline = execute(
            "concurrent",
            "Run concurrent probe",
            [
                "bash",
                "scripts/channel/test-omni-agent-concurrent-sessions.sh",
                "--max-wait",
                str(cfg.max_wait),
            ],
            [],
        )
    if continue_pipeline:
        session_matrix_cmd: list[str] = [
            "bash",
            "scripts/channel/test-omni-agent-session-matrix.sh",
            "--max-wait",
            str(cfg.max_wait),
            "--max-idle-secs",
            str(cfg.max_idle_secs),
            "--output-json",
            DEFAULT_MATRIX_JSON,
            "--output-markdown",
            DEFAULT_MATRIX_MARKDOWN,
        ]
        if cfg.group_thread_id is not None:
            session_matrix_cmd.extend(["--thread-a", str(cfg.group_thread_id)])
        if cfg.group_thread_id_b is not None:
            session_matrix_cmd.extend(["--thread-b", str(cfg.group_thread_id_b)])
        continue_pipeline = execute(
            "session_matrix",
            "Run session matrix",
            session_matrix_cmd,
            [Path(DEFAULT_MATRIX_JSON), Path(DEFAULT_MATRIX_MARKDOWN)],
        )
    if continue_pipeline:
        continue_pipeline = execute(
            "complex_scenario",
            "Run complex control-plane scenario",
            [
                "bash",
                "scripts/channel/test-omni-agent-complex-scenarios.sh",
                "--dataset",
                DEFAULT_COMPLEX_DATASET,
                "--max-wait",
                str(cfg.max_wait),
                "--max-idle-secs",
                str(cfg.max_idle_secs),
                "--max-parallel",
                "4",
                "--min-steps",
                "14",
                "--min-dependency-edges",
                "14",
                "--min-critical-path",
                "6",
                "--min-parallel-waves",
                "3",
                "--min-error-signals",
                "0",
                "--min-negative-feedback-events",
                "0",
                "--min-correction-checks",
                "0",
                "--min-successful-corrections",
                "0",
                "--min-planned-hits",
                "0",
                "--min-natural-language-steps",
                "0",
                "--output-json",
                DEFAULT_COMPLEX_JSON,
                "--output-markdown",
                DEFAULT_COMPLEX_MARKDOWN,
            ],
            [Path(DEFAULT_COMPLEX_JSON), Path(DEFAULT_COMPLEX_MARKDOWN)],
        )
    if continue_pipeline:
        continue_pipeline = execute(
            "memory_evolution",
            "Run memory evolution DAG scenario",
            [
                "bash",
                "scripts/channel/test-omni-agent-complex-scenarios.sh",
                "--dataset",
                DEFAULT_MEMORY_DATASET,
                "--scenario",
                DEFAULT_MEMORY_SCENARIO,
                "--max-wait",
                str(cfg.evolution_max_wait),
                "--max-idle-secs",
                str(cfg.evolution_max_idle_secs),
                "--max-parallel",
                str(cfg.evolution_max_parallel),
                "--output-json",
                DEFAULT_MEMORY_JSON,
                "--output-markdown",
                DEFAULT_MEMORY_MARKDOWN,
            ],
            [Path(DEFAULT_MEMORY_JSON), Path(DEFAULT_MEMORY_MARKDOWN)],
        )

    finished = datetime.now(UTC)
    duration_ms = int((time.perf_counter() - timer_start) * 1000)
    passed_count = sum(1 for step in steps if step.passed)
    report = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": duration_ms,
        "overall_passed": passed_count == len(steps),
        "summary": {
            "total": len(steps),
            "passed": passed_count,
            "failed": len(steps) - passed_count,
        },
        "config": asdict(cfg),
        "artifacts": {
            "group_profile_json": str(cfg.group_profile_json),
            "group_profile_env": str(cfg.group_profile_env),
            "matrix_json": DEFAULT_MATRIX_JSON,
            "complex_json": DEFAULT_COMPLEX_JSON,
            "memory_evolution_json": DEFAULT_MEMORY_JSON,
        },
        "steps": [asdict(step) for step in steps],
    }
    return report


def main() -> int:
    cfg = build_config(parse_args())
    report = run_pipeline(cfg)
    write_report(report, output_json=cfg.output_json, output_markdown=cfg.output_markdown)
    print("Acceptance suite completed.", flush=True)
    print(f"  overall={'PASS' if report['overall_passed'] else 'FAIL'}", flush=True)
    print(
        f"  steps={report['summary']['passed']}/{report['summary']['total']}",  # type: ignore[index]
        flush=True,
    )
    print(f"  json_report={cfg.output_json}", flush=True)
    print(f"  markdown_report={cfg.output_markdown}", flush=True)
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
