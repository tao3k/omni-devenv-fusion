#!/usr/bin/env python3
"""
Benchmark wendao search latency for local regression checks.

Examples:
  uv run python scripts/benchmark_wendao_search.py
  uv run python scripts/benchmark_wendao_search.py --query architecture --runs 8
  uv run python scripts/benchmark_wendao_search.py --max-p95-ms 250 --max-avg-ms 180
  uv run python scripts/benchmark_wendao_search.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunResult:
    elapsed_ms: float
    ok: bool
    result_count: int
    error: str | None


def _resolve_project_root() -> Path:
    prj_root = os.environ.get("PRJ_ROOT")
    if prj_root:
        return Path(prj_root).expanduser().resolve()
    raw = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    return Path(raw).resolve()


def _resolve_binary(project_root: Path, binary: str | None, build: bool, release: bool) -> Path:
    if binary:
        resolved = Path(binary).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"wendao binary not found: {resolved}")
        return resolved

    profile = "release" if release else "debug"
    default_bin = project_root / "target" / profile / "wendao"
    if build or not default_bin.exists():
        cmd = ["cargo", "build", "-p", "xiuxian-wendao", "--bin", "wendao"]
        if release:
            cmd.append("--release")
        subprocess.run(cmd, cwd=project_root, check=True)
    if not default_bin.exists():
        raise FileNotFoundError(f"wendao binary not found after build: {default_bin}")
    return default_bin


def _build_cmd(
    *,
    binary: Path,
    root: Path,
    query: str,
    limit: int,
    match_strategy: str,
    sort_terms: list[str],
    case_sensitive: bool,
) -> list[str]:
    cmd = [
        str(binary),
        "--root",
        str(root),
        "search",
        query,
        "--limit",
        str(limit),
        "--match-strategy",
        match_strategy,
    ]
    for term in sort_terms:
        cmd.extend(["--sort-term", term])
    if case_sensitive:
        cmd.append("--case-sensitive")
    return cmd


def _run_once(cmd: list[str], timeout_s: float) -> RunResult:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            error=f"timeout ({timeout_s}s)",
        )

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if proc.returncode != 0:
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            error=(proc.stderr or proc.stdout or f"exit={proc.returncode}").strip(),
        )

    try:
        payload = json.loads(proc.stdout)
        results = payload.get("results")
        count = len(results) if isinstance(results, list) else 0
    except Exception as exc:  # noqa: BLE001
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            error=f"invalid-json: {exc}",
        )

    return RunResult(
        elapsed_ms=elapsed_ms,
        ok=True,
        result_count=count,
        error=None,
    )


def _p95_ms(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    idx = max(0, int(round(0.95 * (len(sorted_values) - 1))))
    return sorted_values[idx]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark wendao search latency")
    parser.add_argument("--root", default=".", help="Notebook root for wendao --root")
    parser.add_argument("--query", default="architecture", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Search limit")
    parser.add_argument(
        "--match-strategy",
        default="fts",
        choices=("fts", "path_fuzzy", "exact", "re"),
        help="wendao search match strategy",
    )
    parser.add_argument(
        "--sort-term",
        action="append",
        default=[],
        help="Repeatable sort term (e.g. score_desc, path_asc)",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Enable case sensitive search",
    )
    parser.add_argument("--warm-runs", type=int, default=1, help="Warm-up runs")
    parser.add_argument("--runs", type=int, default=7, help="Measured runs")
    parser.add_argument("--timeout-s", type=float, default=20.0, help="Timeout per run")
    parser.add_argument(
        "--binary",
        default=None,
        help="Path to wendao binary (default: target/debug/wendao)",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Use target/release/wendao and build with --release when needed",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Do not build wendao automatically",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=0.0,
        help="Fail if P95 exceeds this threshold (disabled when <=0)",
    )
    parser.add_argument(
        "--max-avg-ms",
        type=float,
        default=0.0,
        help="Fail if average exceeds this threshold (disabled when <=0)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    try:
        project_root = _resolve_project_root()
        binary = _resolve_binary(
            project_root,
            args.binary,
            build=not args.no_build,
            release=bool(args.release),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    cmd = _build_cmd(
        binary=binary,
        root=Path(args.root).expanduser().resolve(),
        query=args.query,
        limit=max(1, int(args.limit)),
        match_strategy=args.match_strategy,
        sort_terms=args.sort_term,
        case_sensitive=bool(args.case_sensitive),
    )

    for _ in range(max(0, int(args.warm_runs))):
        _run_once(cmd, timeout_s=float(args.timeout_s))

    measured: list[RunResult] = []
    for _ in range(max(1, int(args.runs))):
        measured.append(_run_once(cmd, timeout_s=float(args.timeout_s)))

    elapsed_values = [r.elapsed_ms for r in measured]
    ok_runs = [r for r in measured if r.ok]
    failures = [r.error for r in measured if not r.ok and r.error]

    avg_ms = statistics.fmean(elapsed_values) if elapsed_values else 0.0
    median_ms = statistics.median(elapsed_values) if elapsed_values else 0.0
    p95 = _p95_ms(elapsed_values)
    min_ms = min(elapsed_values) if elapsed_values else 0.0
    max_ms = max(elapsed_values) if elapsed_values else 0.0
    avg_result_count = (
        statistics.fmean([float(r.result_count) for r in ok_runs]) if ok_runs else 0.0
    )

    gates_failed: list[str] = []
    if args.max_p95_ms > 0 and p95 > args.max_p95_ms:
        gates_failed.append(f"p95_ms={p95:.2f} > {args.max_p95_ms:.2f}")
    if args.max_avg_ms > 0 and avg_ms > args.max_avg_ms:
        gates_failed.append(f"avg_ms={avg_ms:.2f} > {args.max_avg_ms:.2f}")
    if failures:
        gates_failed.append(f"run_failures={len(failures)}")

    payload: dict[str, Any] = {
        "schema": "omni.wendao.search_benchmark.v1",
        "binary": str(binary),
        "profile": "release" if args.release else "debug",
        "cmd": cmd,
        "warm_runs": int(args.warm_runs),
        "runs": int(args.runs),
        "summary": {
            "avg_ms": round(avg_ms, 2),
            "median_ms": round(median_ms, 2),
            "p95_ms": round(p95, 2),
            "min_ms": round(min_ms, 2),
            "max_ms": round(max_ms, 2),
            "ok_runs": len(ok_runs),
            "failed_runs": len(measured) - len(ok_runs),
            "avg_result_count": round(avg_result_count, 2),
        },
        "thresholds": {
            "max_p95_ms": float(args.max_p95_ms),
            "max_avg_ms": float(args.max_avg_ms),
        },
        "gates_failed": gates_failed,
        "runs_detail": [asdict(item) for item in measured],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print("wendao search benchmark")
        print("=" * 48)
        print(f"binary: {binary}")
        print(f"profile: {'release' if args.release else 'debug'}")
        print(f"query: {args.query!r}  strategy={args.match_strategy}")
        print(
            "latency(ms): "
            f"avg={avg_ms:.2f} median={median_ms:.2f} p95={p95:.2f} "
            f"min={min_ms:.2f} max={max_ms:.2f}"
        )
        print(
            f"runs: total={len(measured)} ok={len(ok_runs)} "
            f"failed={len(measured) - len(ok_runs)} "
            f"avg_result_count={avg_result_count:.2f}"
        )
        if failures:
            print("errors:")
            for err in failures[:5]:
                print(f"  - {err}")
        if gates_failed:
            print("gate: FAIL")
            for gate in gates_failed:
                print(f"  - {gate}")
        else:
            print("gate: PASS")

    return 1 if gates_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
