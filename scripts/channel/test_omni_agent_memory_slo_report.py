#!/usr/bin/env python3
"""
Aggregate omni-agent memory/session black-box reports into a single SLO gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SloConfig:
    project_root: Path
    evolution_report_json: Path
    benchmark_report_json: Path
    session_matrix_report_json: Path
    runtime_log_file: Path | None
    output_json: Path
    output_markdown: Path
    min_planned_hits: int
    min_successful_corrections: int
    min_recall_credit_events: int
    min_quality_score: float
    required_benchmark_modes: tuple[str, ...]
    min_query_turns: int
    max_mode_mcp_error_turns: int
    max_total_mcp_error_turns: int
    min_session_steps: int
    max_session_failed_steps: int
    enable_stream_gate: bool
    min_stream_ack_ratio: float
    min_stream_published_events: int
    max_stream_read_failed: int


def default_report_path(filename: str) -> Path:
    runtime_root = Path(os.environ.get("PRJ_RUNTIME_DIR", ".run"))
    if not runtime_root.is_absolute():
        runtime_root = Path.cwd() / runtime_root
    return runtime_root / "reports" / filename


def project_root_from(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def resolve_path(path_str: str, project_root: Path) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def parse_required_modes(raw: str) -> tuple[str, ...]:
    modes = tuple(mode.strip() for mode in raw.split(",") if mode.strip())
    if not modes:
        raise ValueError("--required-benchmark-modes must contain at least one mode.")
    return modes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a unified memory/session SLO report from evolution, benchmark, "
            "and session-matrix outputs."
        )
    )
    parser.add_argument(
        "--project-root",
        default=str(project_root_from(Path.cwd())),
        help="Project root (default: auto-detect from .git).",
    )
    parser.add_argument(
        "--evolution-report-json",
        default=str(default_report_path("omni-agent-memory-evolution.json")),
    )
    parser.add_argument(
        "--benchmark-report-json",
        default=str(default_report_path("omni-agent-memory-benchmark.json")),
    )
    parser.add_argument(
        "--session-matrix-report-json",
        default=str(default_report_path("agent-channel-session-matrix.json")),
    )
    parser.add_argument(
        "--runtime-log-file",
        default="",
        help="Optional runtime log for stream ack/read-failure checks.",
    )
    parser.add_argument(
        "--output-json",
        default=str(default_report_path("omni-agent-memory-slo-report.json")),
    )
    parser.add_argument(
        "--output-markdown",
        default=str(default_report_path("omni-agent-memory-slo-report.md")),
    )
    parser.add_argument("--min-planned-hits", type=int, default=10)
    parser.add_argument("--min-successful-corrections", type=int, default=3)
    parser.add_argument("--min-recall-credit-events", type=int, default=1)
    parser.add_argument("--min-quality-score", type=float, default=90.0)
    parser.add_argument("--required-benchmark-modes", default="baseline,adaptive")
    parser.add_argument("--min-query-turns", type=int, default=1)
    parser.add_argument("--max-mode-mcp-error-turns", type=int, default=0)
    parser.add_argument("--max-total-mcp-error-turns", type=int, default=0)
    parser.add_argument("--min-session-steps", type=int, default=1)
    parser.add_argument("--max-session-failed-steps", type=int, default=0)
    parser.add_argument("--enable-stream-gate", action="store_true")
    parser.add_argument("--min-stream-ack-ratio", type=float, default=0.999)
    parser.add_argument("--min-stream-published-events", type=int, default=1)
    parser.add_argument("--max-stream-read-failed", type=int, default=0)
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> SloConfig:
    project_root = resolve_path(args.project_root, Path.cwd())
    if args.min_planned_hits < 0:
        raise ValueError("--min-planned-hits must be >= 0.")
    if args.min_successful_corrections < 0:
        raise ValueError("--min-successful-corrections must be >= 0.")
    if args.min_recall_credit_events < 0:
        raise ValueError("--min-recall-credit-events must be >= 0.")
    if args.min_quality_score < 0:
        raise ValueError("--min-quality-score must be >= 0.")
    if args.min_query_turns < 0:
        raise ValueError("--min-query-turns must be >= 0.")
    if args.max_mode_mcp_error_turns < 0:
        raise ValueError("--max-mode-mcp-error-turns must be >= 0.")
    if args.max_total_mcp_error_turns < 0:
        raise ValueError("--max-total-mcp-error-turns must be >= 0.")
    if args.min_session_steps < 0:
        raise ValueError("--min-session-steps must be >= 0.")
    if args.max_session_failed_steps < 0:
        raise ValueError("--max-session-failed-steps must be >= 0.")
    if args.min_stream_ack_ratio < 0 or args.min_stream_ack_ratio > 1:
        raise ValueError("--min-stream-ack-ratio must be in [0, 1].")
    if args.min_stream_published_events < 0:
        raise ValueError("--min-stream-published-events must be >= 0.")
    if args.max_stream_read_failed < 0:
        raise ValueError("--max-stream-read-failed must be >= 0.")

    runtime_log_file = None
    if args.runtime_log_file.strip():
        runtime_log_file = resolve_path(args.runtime_log_file, project_root)

    return SloConfig(
        project_root=project_root,
        evolution_report_json=resolve_path(args.evolution_report_json, project_root),
        benchmark_report_json=resolve_path(args.benchmark_report_json, project_root),
        session_matrix_report_json=resolve_path(args.session_matrix_report_json, project_root),
        runtime_log_file=runtime_log_file,
        output_json=resolve_path(args.output_json, project_root),
        output_markdown=resolve_path(args.output_markdown, project_root),
        min_planned_hits=int(args.min_planned_hits),
        min_successful_corrections=int(args.min_successful_corrections),
        min_recall_credit_events=int(args.min_recall_credit_events),
        min_quality_score=float(args.min_quality_score),
        required_benchmark_modes=parse_required_modes(args.required_benchmark_modes),
        min_query_turns=int(args.min_query_turns),
        max_mode_mcp_error_turns=int(args.max_mode_mcp_error_turns),
        max_total_mcp_error_turns=int(args.max_total_mcp_error_turns),
        min_session_steps=int(args.min_session_steps),
        max_session_failed_steps=int(args.max_session_failed_steps),
        enable_stream_gate=bool(args.enable_stream_gate),
        min_stream_ack_ratio=float(args.min_stream_ack_ratio),
        min_stream_published_events=int(args.min_stream_published_events),
        max_stream_read_failed=int(args.max_stream_read_failed),
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"report payload is not an object: {path}")
    return payload


def evaluate_evolution(cfg: SloConfig, report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    scenarios_obj = report.get("scenarios")
    scenarios = scenarios_obj if isinstance(scenarios_obj, list) else []
    if not bool(report.get("overall_passed", False)):
        failures.append("evolution.overall_passed=false")
    if not scenarios:
        failures.append("evolution.scenarios is empty")
        return {
            "passed": False,
            "failures": failures,
            "summary": {
                "scenario_count": 0,
                "min_planned_hits": 0,
                "min_successful_corrections": 0,
                "min_recall_credit_events": 0,
                "min_quality_score": 0.0,
            },
        }

    min_planned_hits: int | None = None
    min_successful_corrections: int | None = None
    min_recall_credit_events: int | None = None
    min_quality_score: float | None = None

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            failures.append("evolution.scenario payload is not an object")
            continue
        scenario_id = str(scenario.get("scenario_id", "unknown"))
        quality_obj = scenario.get("quality")
        quality = quality_obj if isinstance(quality_obj, dict) else {}
        planned_hits = int(quality.get("planned_hits", 0))
        successful_corrections = int(quality.get("successful_corrections", 0))
        recall_credit_events = int(quality.get("recall_credit_events", 0))
        quality_score = float(quality.get("quality_score", 0.0))
        if not bool(scenario.get("quality_passed", True)):
            failures.append(f"evolution.{scenario_id}.quality_passed=false")
        if planned_hits < cfg.min_planned_hits:
            failures.append(
                f"evolution.{scenario_id}.planned_hits={planned_hits} < {cfg.min_planned_hits}"
            )
        if successful_corrections < cfg.min_successful_corrections:
            failures.append(
                "evolution."
                f"{scenario_id}.successful_corrections={successful_corrections} "
                f"< {cfg.min_successful_corrections}"
            )
        if recall_credit_events < cfg.min_recall_credit_events:
            failures.append(
                "evolution."
                f"{scenario_id}.recall_credit_events={recall_credit_events} "
                f"< {cfg.min_recall_credit_events}"
            )
        if quality_score < cfg.min_quality_score:
            failures.append(
                f"evolution.{scenario_id}.quality_score={quality_score:.2f} < "
                f"{cfg.min_quality_score:.2f}"
            )
        min_planned_hits = (
            planned_hits if min_planned_hits is None else min(min_planned_hits, planned_hits)
        )
        min_successful_corrections = (
            successful_corrections
            if min_successful_corrections is None
            else min(min_successful_corrections, successful_corrections)
        )
        min_recall_credit_events = (
            recall_credit_events
            if min_recall_credit_events is None
            else min(min_recall_credit_events, recall_credit_events)
        )
        min_quality_score = (
            quality_score if min_quality_score is None else min(min_quality_score, quality_score)
        )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "summary": {
            "scenario_count": len(scenarios),
            "min_planned_hits": int(min_planned_hits or 0),
            "min_successful_corrections": int(min_successful_corrections or 0),
            "min_recall_credit_events": int(min_recall_credit_events or 0),
            "min_quality_score": round(float(min_quality_score or 0.0), 2),
        },
    }


def evaluate_benchmark(cfg: SloConfig, report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    mode_summaries_obj = report.get("mode_summaries")
    mode_summaries = mode_summaries_obj if isinstance(mode_summaries_obj, dict) else {}
    if not mode_summaries:
        failures.append("benchmark.mode_summaries missing or empty")
    total_mcp_error_turns = 0
    query_turns_by_mode: dict[str, int] = {}
    mcp_errors_by_mode: dict[str, int] = {}

    for mode in cfg.required_benchmark_modes:
        summary_obj = mode_summaries.get(mode)
        if not isinstance(summary_obj, dict):
            failures.append(f"benchmark.mode={mode} missing")
            continue
        query_turns = int(summary_obj.get("query_turns", 0))
        mcp_error_turns = int(summary_obj.get("mcp_error_turns", 0))
        query_turns_by_mode[mode] = query_turns
        mcp_errors_by_mode[mode] = mcp_error_turns
        total_mcp_error_turns += mcp_error_turns
        if query_turns < cfg.min_query_turns:
            failures.append(f"benchmark.{mode}.query_turns={query_turns} < {cfg.min_query_turns}")
        if mcp_error_turns > cfg.max_mode_mcp_error_turns:
            failures.append(
                "benchmark."
                f"{mode}.mcp_error_turns={mcp_error_turns} > {cfg.max_mode_mcp_error_turns}"
            )

    if total_mcp_error_turns > cfg.max_total_mcp_error_turns:
        failures.append(
            f"benchmark.total_mcp_error_turns={total_mcp_error_turns} > "
            f"{cfg.max_total_mcp_error_turns}"
        )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "summary": {
            "required_modes": list(cfg.required_benchmark_modes),
            "query_turns_by_mode": query_turns_by_mode,
            "mcp_error_turns_by_mode": mcp_errors_by_mode,
            "total_mcp_error_turns": total_mcp_error_turns,
        },
    }


def evaluate_session_matrix(cfg: SloConfig, report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary_obj = report.get("summary")
    summary = summary_obj if isinstance(summary_obj, dict) else {}
    total = int(summary.get("total", 0))
    failed = int(summary.get("failed", 0))
    overall_passed = bool(report.get("overall_passed", False))
    if not overall_passed:
        failures.append("session_matrix.overall_passed=false")
    if total < cfg.min_session_steps:
        failures.append(f"session_matrix.summary.total={total} < {cfg.min_session_steps}")
    if failed > cfg.max_session_failed_steps:
        failures.append(f"session_matrix.summary.failed={failed} > {cfg.max_session_failed_steps}")
    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "summary": {
            "total_steps": total,
            "failed_steps": failed,
            "overall_passed": overall_passed,
        },
    }


def evaluate_stream_health(cfg: SloConfig, runtime_log_file: Path | None) -> dict[str, Any]:
    if runtime_log_file is None:
        return {
            "enabled": False,
            "passed": True,
            "failures": [],
            "summary": {
                "published_events": 0,
                "processed_events": 0,
                "read_failed_events": 0,
                "ack_ratio": None,
                "runtime_log_file": None,
            },
        }

    if not runtime_log_file.exists():
        return {
            "enabled": bool(cfg.enable_stream_gate),
            "passed": not cfg.enable_stream_gate,
            "failures": (
                [f"stream.runtime_log_file_missing={runtime_log_file}"]
                if cfg.enable_stream_gate
                else []
            ),
            "summary": {
                "published_events": 0,
                "processed_events": 0,
                "read_failed_events": 0,
                "ack_ratio": None,
                "runtime_log_file": str(runtime_log_file),
            },
        }

    published_events = 0
    processed_events = 0
    read_failed_events = 0

    with runtime_log_file.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "session.stream_event.published" in line:
                published_events += 1
            if "agent.memory.stream_consumer.event_processed" in line:
                processed_events += 1
            if "agent.memory.stream_consumer.read_failed" in line:
                read_failed_events += 1

    ack_ratio: float | None = None
    if published_events > 0:
        ack_ratio = processed_events / published_events

    failures: list[str] = []
    if cfg.enable_stream_gate:
        if published_events < cfg.min_stream_published_events:
            failures.append(
                f"stream.published_events={published_events} < {cfg.min_stream_published_events}"
            )
        if ack_ratio is None:
            failures.append("stream.ack_ratio unavailable (published_events=0)")
        elif ack_ratio < cfg.min_stream_ack_ratio:
            failures.append(f"stream.ack_ratio={ack_ratio:.4f} < {cfg.min_stream_ack_ratio:.4f}")
        if read_failed_events > cfg.max_stream_read_failed:
            failures.append(
                f"stream.read_failed_events={read_failed_events} > {cfg.max_stream_read_failed}"
            )

    return {
        "enabled": bool(cfg.enable_stream_gate),
        "passed": len(failures) == 0,
        "failures": failures,
        "summary": {
            "published_events": published_events,
            "processed_events": processed_events,
            "read_failed_events": read_failed_events,
            "ack_ratio": round(ack_ratio, 4) if ack_ratio is not None else None,
            "runtime_log_file": str(runtime_log_file),
        },
    }


def run_slo_report(cfg: SloConfig) -> dict[str, Any]:
    started_ts = time.time()
    started_at = datetime.fromtimestamp(started_ts, tz=UTC).isoformat()

    evolution = evaluate_evolution(cfg, load_json(cfg.evolution_report_json))
    benchmark = evaluate_benchmark(cfg, load_json(cfg.benchmark_report_json))
    session_matrix = evaluate_session_matrix(cfg, load_json(cfg.session_matrix_report_json))
    stream = evaluate_stream_health(cfg, cfg.runtime_log_file)

    failures = [
        *evolution["failures"],
        *benchmark["failures"],
        *session_matrix["failures"],
        *stream["failures"],
    ]

    finished_ts = time.time()
    finished_at = datetime.fromtimestamp(finished_ts, tz=UTC).isoformat()
    return {
        "metadata": {
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "duration_secs": round(finished_ts - started_ts, 3),
        },
        "inputs": {
            "evolution_report_json": str(cfg.evolution_report_json),
            "benchmark_report_json": str(cfg.benchmark_report_json),
            "session_matrix_report_json": str(cfg.session_matrix_report_json),
            "runtime_log_file": str(cfg.runtime_log_file) if cfg.runtime_log_file else None,
        },
        "thresholds": {
            "min_planned_hits": cfg.min_planned_hits,
            "min_successful_corrections": cfg.min_successful_corrections,
            "min_recall_credit_events": cfg.min_recall_credit_events,
            "min_quality_score": cfg.min_quality_score,
            "required_benchmark_modes": list(cfg.required_benchmark_modes),
            "min_query_turns": cfg.min_query_turns,
            "max_mode_mcp_error_turns": cfg.max_mode_mcp_error_turns,
            "max_total_mcp_error_turns": cfg.max_total_mcp_error_turns,
            "min_session_steps": cfg.min_session_steps,
            "max_session_failed_steps": cfg.max_session_failed_steps,
            "enable_stream_gate": cfg.enable_stream_gate,
            "min_stream_ack_ratio": cfg.min_stream_ack_ratio,
            "min_stream_published_events": cfg.min_stream_published_events,
            "max_stream_read_failed": cfg.max_stream_read_failed,
        },
        "checks": {
            "evolution": evolution,
            "benchmark": benchmark,
            "session_matrix": session_matrix,
            "stream": stream,
        },
        "overall_passed": len(failures) == 0,
        "failure_count": len(failures),
        "failures": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    checks = report["checks"]
    evolution = checks["evolution"]
    benchmark = checks["benchmark"]
    session_matrix = checks["session_matrix"]
    stream = checks["stream"]
    status = "PASS" if report["overall_passed"] else "FAIL"

    lines = [
        "# Omni-Agent Memory SLO Report",
        "",
        f"- Overall: `{status}`",
        f"- Failure count: `{report['failure_count']}`",
        "",
        "## Inputs",
        "",
        f"- Evolution: `{report['inputs']['evolution_report_json']}`",
        f"- Benchmark: `{report['inputs']['benchmark_report_json']}`",
        f"- Session matrix: `{report['inputs']['session_matrix_report_json']}`",
        f"- Runtime log: `{report['inputs']['runtime_log_file']}`",
        "",
        "## Gate Results",
        "",
        f"- Evolution: `{'PASS' if evolution['passed'] else 'FAIL'}`",
        f"- Benchmark: `{'PASS' if benchmark['passed'] else 'FAIL'}`",
        f"- Session matrix: `{'PASS' if session_matrix['passed'] else 'FAIL'}`",
        f"- Stream gate: `{'PASS' if stream['passed'] else 'FAIL'}` (enabled={stream['enabled']})",
        "",
        "## Key Metrics",
        "",
        (
            "- Evolution minima: "
            "planned_hits={ph}, successful_corrections={sc}, "
            "recall_credit_events={rc}, quality_score={qs}".format(
                ph=evolution["summary"]["min_planned_hits"],
                sc=evolution["summary"]["min_successful_corrections"],
                rc=evolution["summary"]["min_recall_credit_events"],
                qs=evolution["summary"]["min_quality_score"],
            )
        ),
        (
            "- Benchmark MCP errors: "
            f"{benchmark['summary']['total_mcp_error_turns']} "
            f"(per-mode={benchmark['summary']['mcp_error_turns_by_mode']})"
        ),
        (
            "- Session matrix: "
            f"total_steps={session_matrix['summary']['total_steps']} "
            f"failed_steps={session_matrix['summary']['failed_steps']}"
        ),
        (
            "- Stream health: "
            f"published={stream['summary']['published_events']} "
            f"processed={stream['summary']['processed_events']} "
            f"read_failed={stream['summary']['read_failed_events']} "
            f"ack_ratio={stream['summary']['ack_ratio']}"
        ),
    ]

    failures = report.get("failures", [])
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend([f"- {item}" for item in failures])

    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_json: Path, output_markdown: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_markdown.write_text(render_markdown(report) + "\n", encoding="utf-8")


def main() -> int:
    try:
        cfg = build_config(parse_args())
        report = run_slo_report(cfg)
        write_outputs(report, cfg.output_json, cfg.output_markdown)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Memory SLO aggregation completed.", flush=True)
    print(f"  overall={'PASS' if report['overall_passed'] else 'FAIL'}", flush=True)
    print(f"  failure_count={report['failure_count']}", flush=True)
    print(f"  json_report={cfg.output_json}", flush=True)
    print(f"  markdown_report={cfg.output_markdown}", flush=True)
    if report["failures"]:
        print("  failures:", flush=True)
        for item in report["failures"]:
            print(f"    - {item}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
