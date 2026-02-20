#!/usr/bin/env python3
"""
knowledge.recall performance gate with P95 latency and RSS peak delta thresholds.

This gate runs the same path as `omni skill run knowledge.recall ... -v` but collects
machine-readable monitor metrics for CI pass/fail decisions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from omni.foundation.runtime.skills_monitor.perf_gate import (
    RecallPerfRun,
    evaluate_gate,
    extract_status_and_error,
    summarize_runs,
)


def _default_report_path() -> Path:
    from omni.foundation import PRJ_RUNTIME

    raw = PRJ_RUNTIME("reports", "knowledge_recall_perf_gate.json")
    return raw if isinstance(raw, Path) else Path(raw)


def _is_embedding_unavailable(error_text: str) -> bool:
    if not error_text:
        return False
    text = error_text.lower()
    patterns = (
        "embedding",
        "mcp embedding",
        "timed out",
        "timeout",
        "unavailable",
    )
    return any(p in text for p in patterns)


def _extract_row_budget_memory(report_payload: dict[str, Any]) -> tuple[float | None, bool]:
    retrieval = report_payload.get("retrieval_signals")
    if not isinstance(retrieval, dict):
        return None, False
    row_budget = retrieval.get("row_budget")
    if not isinstance(row_budget, dict):
        return None, False
    memory = row_budget.get("memory")
    if not isinstance(memory, dict):
        return None, False
    observed_raw = memory.get("observed_count")
    observed_count = int(observed_raw) if isinstance(observed_raw, int | float) else 0
    peak_raw = memory.get("rss_peak_delta_max")
    peak = float(peak_raw) if isinstance(peak_raw, int | float) else None
    return peak, observed_count > 0


async def _run_once(
    *,
    query: str,
    limit: int,
    retrieval_mode: str,
    verbose: bool,
) -> tuple[RecallPerfRun, dict[str, Any]]:
    from omni.core.skills import run_skill
    from omni.foundation.runtime.skills_monitor import skills_monitor_scope

    monitor_report: dict[str, Any] = {}
    error_text = ""
    status = "unknown"
    try:
        async with skills_monitor_scope(
            "knowledge.recall",
            verbose=verbose,
            auto_report=False,
        ) as monitor:
            result = await run_skill(
                "knowledge",
                "recall",
                {
                    "query": query,
                    "limit": int(limit),
                    "chunked": False,
                    "retrieval_mode": retrieval_mode,
                },
            )
        report = monitor.build_report()
        monitor_report = report.to_dict()
        status, error_text = extract_status_and_error(result)
        ok = status == "success" and not error_text
        row_budget_peak_max_mb, row_budget_observed = _extract_row_budget_memory(monitor_report)
        run = RecallPerfRun(
            elapsed_ms=float(report.elapsed_sec) * 1000.0,
            rss_peak_delta_mb=float(report.rss_peak_delta_mb),
            ok=ok,
            row_budget_rss_peak_delta_max_mb=row_budget_peak_max_mb,
            row_budget_memory_observed=row_budget_observed,
            error=error_text,
        )
        return run, monitor_report
    except Exception as exc:
        error_text = str(exc)
        run = RecallPerfRun(
            elapsed_ms=0.0,
            rss_peak_delta_mb=0.0,
            ok=False,
            error=error_text,
        )
        return run, monitor_report


async def _run_batch(
    *,
    query: str,
    limit: int,
    retrieval_mode: str,
    warm_runs: int,
    runs: int,
    verbose: bool,
) -> tuple[list[RecallPerfRun], list[dict[str, Any]]]:
    for _ in range(max(0, warm_runs)):
        await _run_once(
            query=query,
            limit=limit,
            retrieval_mode=retrieval_mode,
            verbose=verbose,
        )
    measured: list[RecallPerfRun] = []
    reports: list[dict[str, Any]] = []
    for _ in range(max(0, runs)):
        run, report = await _run_once(
            query=query,
            limit=limit,
            retrieval_mode=retrieval_mode,
            verbose=verbose,
        )
        measured.append(run)
        reports.append(report)
    return measured, reports


async def _run_auto_mode(
    *,
    query: str,
    limit: int,
    warm_runs: int,
    runs: int,
    verbose: bool,
) -> tuple[str, list[RecallPerfRun], list[dict[str, Any]], str]:
    measured, reports = await _run_batch(
        query=query,
        limit=limit,
        retrieval_mode="hybrid",
        warm_runs=warm_runs,
        runs=runs,
        verbose=verbose,
    )
    if any(item.ok for item in measured):
        return "hybrid", measured, reports, ""

    errors = [item.error for item in measured if item.error]
    if errors and all(_is_embedding_unavailable(err) for err in errors):
        fallback_measured, fallback_reports = await _run_batch(
            query=query,
            limit=limit,
            retrieval_mode="graph_only",
            warm_runs=warm_runs,
            runs=runs,
            verbose=verbose,
        )
        return (
            "graph_only",
            fallback_measured,
            fallback_reports,
            "fallback_from_hybrid_due_embedding_unavailable",
        )
    return "hybrid", measured, reports, ""


def _to_json_payload(
    *,
    requested_mode: str,
    effective_mode: str,
    fallback_reason: str,
    query: str,
    limit: int,
    warm_runs: int,
    runs: list[RecallPerfRun],
    max_p95_ms: float,
    max_rss_peak_delta_mb: float,
    max_failures: int,
    max_row_budget_rss_peak_delta_mb: float,
    min_row_budget_memory_observed_runs: int,
    passed: bool,
    failures: list[str],
) -> dict[str, Any]:
    summary = summarize_runs(runs)
    return {
        "schema": "omni.skills_monitor.recall_perf_gate.v1",
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "fallback_reason": fallback_reason or None,
        "query": query,
        "limit": int(limit),
        "warm_runs": int(warm_runs),
        "runs": [
            {
                "elapsed_ms": round(item.elapsed_ms, 2),
                "rss_peak_delta_mb": round(item.rss_peak_delta_mb, 2),
                "row_budget_rss_peak_delta_max_mb": (
                    round(float(item.row_budget_rss_peak_delta_max_mb), 2)
                    if isinstance(item.row_budget_rss_peak_delta_max_mb, int | float)
                    else None
                ),
                "row_budget_memory_observed": bool(item.row_budget_memory_observed),
                "ok": bool(item.ok),
                "error": item.error or None,
            }
            for item in runs
        ],
        "summary": {
            "total_runs": summary.total_runs,
            "ok_runs": summary.ok_runs,
            "failed_runs": summary.failed_runs,
            "p95_ms": round(summary.p95_ms, 2),
            "elapsed_avg_ms": round(summary.elapsed_avg_ms, 2),
            "rss_peak_delta_max_mb": round(summary.rss_peak_delta_max_mb, 2),
            "row_budget_memory_observed_runs": summary.row_budget_memory_observed_runs,
            "row_budget_rss_peak_delta_max_mb": round(summary.row_budget_rss_peak_delta_max_mb, 2),
        },
        "thresholds": {
            "max_p95_ms": float(max_p95_ms),
            "max_rss_peak_delta_mb": float(max_rss_peak_delta_mb),
            "max_failures": int(max_failures),
            "max_row_budget_rss_peak_delta_mb": float(max_row_budget_rss_peak_delta_mb),
            "min_row_budget_memory_observed_runs": int(min_row_budget_memory_observed_runs),
        },
        "passed": bool(passed),
        "failures": failures,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="knowledge.recall performance gate")
    parser.add_argument("--query", default="x", help="Recall query text (default: x)")
    parser.add_argument("--limit", type=int, default=2, help="Recall limit (default: 2)")
    parser.add_argument("--runs", type=int, default=5, help="Measured runs (default: 5)")
    parser.add_argument("--warm-runs", type=int, default=1, help="Warm runs (default: 1)")
    parser.add_argument(
        "--retrieval-mode",
        choices=("auto", "hybrid", "graph_only", "vector_only"),
        default="auto",
        help="Retrieval mode. auto=hybrid then fallback to graph_only if embedding unavailable.",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=float(os.environ.get("OMNI_KNOWLEDGE_RECALL_P95_MS", "2500")),
        help="Max allowed P95 latency in ms.",
    )
    parser.add_argument(
        "--max-rss-peak-delta-mb",
        type=float,
        default=float(os.environ.get("OMNI_KNOWLEDGE_RECALL_RSS_PEAK_DELTA_MB", "300")),
        help="Max allowed RSS peak delta in MiB.",
    )
    parser.add_argument(
        "--max-row-budget-rss-peak-delta-mb",
        type=float,
        default=float(
            os.environ.get(
                "OMNI_KNOWLEDGE_RECALL_ROW_BUDGET_RSS_PEAK_DELTA_MB",
                os.environ.get("OMNI_KNOWLEDGE_RECALL_RSS_PEAK_DELTA_MB", "300"),
            )
        ),
        help="Max allowed retrieval row_budget RSS peak delta max in MiB.",
    )
    parser.add_argument(
        "--min-row-budget-memory-observed-runs",
        type=int,
        default=int(os.environ.get("OMNI_KNOWLEDGE_RECALL_ROW_BUDGET_MEMORY_OBSERVED_MIN", "1")),
        help="Minimum successful runs that must include row_budget.memory observation.",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=int(os.environ.get("OMNI_KNOWLEDGE_RECALL_MAX_FAILURES", "0")),
        help="Max allowed failed runs.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Write JSON report to file (default: PRJ_RUNTIME/reports/knowledge_recall_perf_gate.json).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose run logs.")
    args = parser.parse_args()

    requested_mode = args.retrieval_mode
    fallback_reason = ""
    if requested_mode == "auto":
        effective_mode, runs, _, fallback_reason = await _run_auto_mode(
            query=args.query,
            limit=args.limit,
            warm_runs=args.warm_runs,
            runs=args.runs,
            verbose=args.verbose,
        )
    else:
        effective_mode = requested_mode
        runs, _ = await _run_batch(
            query=args.query,
            limit=args.limit,
            retrieval_mode=effective_mode,
            warm_runs=args.warm_runs,
            runs=args.runs,
            verbose=args.verbose,
        )

    summary = summarize_runs(runs)
    passed, failures = evaluate_gate(
        summary,
        max_p95_ms=args.max_p95_ms,
        max_rss_peak_delta_mb=args.max_rss_peak_delta_mb,
        max_failures=args.max_failures,
        max_row_budget_rss_peak_delta_mb=args.max_row_budget_rss_peak_delta_mb,
        min_row_budget_memory_observed_runs=args.min_row_budget_memory_observed_runs,
    )
    report = _to_json_payload(
        requested_mode=requested_mode,
        effective_mode=effective_mode,
        fallback_reason=fallback_reason,
        query=args.query,
        limit=args.limit,
        warm_runs=args.warm_runs,
        runs=runs,
        max_p95_ms=args.max_p95_ms,
        max_rss_peak_delta_mb=args.max_rss_peak_delta_mb,
        max_failures=args.max_failures,
        max_row_budget_rss_peak_delta_mb=args.max_row_budget_rss_peak_delta_mb,
        min_row_budget_memory_observed_runs=args.min_row_budget_memory_observed_runs,
        passed=passed,
        failures=failures,
    )

    output_path = Path(args.json_output) if args.json_output else _default_report_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("knowledge.recall perf gate")
        print("=" * 60)
        print(f"mode: requested={requested_mode} effective={effective_mode}")
        if fallback_reason:
            print(f"fallback: {fallback_reason}")
        print(f"runs: total={summary.total_runs} ok={summary.ok_runs} failed={summary.failed_runs}")
        print(
            f"metrics: p95={summary.p95_ms:.1f}ms avg={summary.elapsed_avg_ms:.1f}ms "
            f"rss_peak_delta_max={summary.rss_peak_delta_max_mb:.1f}MiB "
            "row_budget_rss_peak_delta_max="
            f"{summary.row_budget_rss_peak_delta_max_mb:.1f}MiB "
            "row_budget_memory_observed_runs="
            f"{summary.row_budget_memory_observed_runs}"
        )
        print(
            "thresholds: "
            f"p95<={args.max_p95_ms:.1f}ms "
            f"rss_peak_delta<={args.max_rss_peak_delta_mb:.1f}MiB "
            "row_budget_rss_peak_delta<="
            f"{args.max_row_budget_rss_peak_delta_mb:.1f}MiB "
            "row_budget_memory_observed_runs>="
            f"{args.min_row_budget_memory_observed_runs} "
            f"failures<={args.max_failures}"
        )
        print(f"report: {output_path}")
        if failures:
            print("gate failures:")
            for item in failures:
                print(f"  - {item}")
        print(f"result: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
