#!/usr/bin/env python3
"""
Benchmark wendao related latency and subgraph diagnostics for regression gates.

Examples:
  uv run python scripts/benchmark_wendao_related.py --stem b
  uv run python scripts/benchmark_wendao_related.py --stem b --runs 7 --warm-runs 2
  uv run python scripts/benchmark_wendao_related.py --stem b --max-p95-ms 300 --expect-subgraph-count-min 1
  uv run python scripts/benchmark_wendao_related.py --stem b --json
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

from omni.foundation.config.link_graph_runtime import (
    LINK_GRAPH_CACHE_VALKEY_URL_ENV,
    get_link_graph_cache_valkey_url,
)


@dataclass
class RunResult:
    elapsed_ms: float
    ok: bool
    result_count: int
    subgraph_count: int
    kernel_duration_ms: float
    partition_duration_ms: float
    fusion_duration_ms: float
    total_duration_ms: float
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
    stem: str,
    max_distance: int,
    limit: int,
    ppr_alpha: float | None,
    ppr_max_iter: int | None,
    ppr_tol: float | None,
    ppr_subgraph_mode: str | None,
) -> list[str]:
    cmd = [
        str(binary),
        "--root",
        str(root),
        "related",
        stem,
        "--max-distance",
        str(max_distance),
        "--limit",
        str(limit),
        "--verbose",
    ]
    if ppr_alpha is not None:
        cmd.extend(["--ppr-alpha", str(ppr_alpha)])
    if ppr_max_iter is not None:
        cmd.extend(["--ppr-max-iter", str(ppr_max_iter)])
    if ppr_tol is not None:
        cmd.extend(["--ppr-tol", str(ppr_tol)])
    if ppr_subgraph_mode:
        cmd.extend(["--ppr-subgraph-mode", ppr_subgraph_mode])
    return cmd


def _run_once(cmd: list[str], timeout_s: float) -> RunResult:
    start = time.perf_counter()
    env = os.environ.copy()
    # Unified resolver: settings (wendao.yaml) first, then VALKEY_URL env fallback.
    env[LINK_GRAPH_CACHE_VALKEY_URL_ENV] = get_link_graph_cache_valkey_url(env=env)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            subgraph_count=0,
            kernel_duration_ms=0.0,
            partition_duration_ms=0.0,
            fusion_duration_ms=0.0,
            total_duration_ms=0.0,
            error=f"timeout ({timeout_s}s)",
        )

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if proc.returncode != 0:
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            subgraph_count=0,
            kernel_duration_ms=0.0,
            partition_duration_ms=0.0,
            fusion_duration_ms=0.0,
            total_duration_ms=0.0,
            error=(proc.stderr or proc.stdout or f"exit={proc.returncode}").strip(),
        )

    try:
        payload = json.loads(proc.stdout)
        results = payload.get("results")
        result_count = len(results) if isinstance(results, list) else 0
        diagnostics = payload.get("diagnostics")
        if not isinstance(diagnostics, dict):
            raise ValueError("missing diagnostics payload")
        subgraph_count = int(diagnostics.get("subgraph_count", 0))
        kernel_duration_ms = float(diagnostics.get("kernel_duration_ms", 0.0))
        partition_duration_ms = float(diagnostics.get("partition_duration_ms", 0.0))
        fusion_duration_ms = float(diagnostics.get("fusion_duration_ms", 0.0))
        total_duration_ms = float(diagnostics.get("total_duration_ms", 0.0))
    except Exception as exc:  # noqa: BLE001
        return RunResult(
            elapsed_ms=elapsed_ms,
            ok=False,
            result_count=0,
            subgraph_count=0,
            kernel_duration_ms=0.0,
            partition_duration_ms=0.0,
            fusion_duration_ms=0.0,
            total_duration_ms=0.0,
            error=f"invalid-json: {exc}",
        )

    return RunResult(
        elapsed_ms=elapsed_ms,
        ok=True,
        result_count=result_count,
        subgraph_count=subgraph_count,
        kernel_duration_ms=kernel_duration_ms,
        partition_duration_ms=partition_duration_ms,
        fusion_duration_ms=fusion_duration_ms,
        total_duration_ms=total_duration_ms,
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
    parser = argparse.ArgumentParser(description="Benchmark wendao related latency")
    parser.add_argument("--root", default=".", help="Notebook root for wendao --root")
    parser.add_argument("--stem", required=True, help="Seed note stem/id/path for related")
    parser.add_argument("--max-distance", type=int, default=2, help="Related max distance")
    parser.add_argument("--limit", type=int, default=20, help="Related output limit")
    parser.add_argument("--ppr-alpha", type=float, default=None, help="PPR alpha")
    parser.add_argument("--ppr-max-iter", type=int, default=None, help="PPR max iter")
    parser.add_argument("--ppr-tol", type=float, default=None, help="PPR tolerance")
    parser.add_argument(
        "--ppr-subgraph-mode",
        choices=("auto", "disabled", "force"),
        default=None,
        help="PPR subgraph mode",
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
        help="Fail if end-to-end P95 exceeds this threshold (disabled when <=0)",
    )
    parser.add_argument(
        "--max-avg-ms",
        type=float,
        default=0.0,
        help="Fail if end-to-end average exceeds this threshold (disabled when <=0)",
    )
    parser.add_argument(
        "--expect-subgraph-count-min",
        type=int,
        default=0,
        help="Fail if average subgraph_count is below this value (disabled when <=0)",
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
        stem=args.stem,
        max_distance=max(1, int(args.max_distance)),
        limit=max(1, int(args.limit)),
        ppr_alpha=args.ppr_alpha,
        ppr_max_iter=args.ppr_max_iter,
        ppr_tol=args.ppr_tol,
        ppr_subgraph_mode=args.ppr_subgraph_mode,
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
    avg_subgraph_count = (
        statistics.fmean([float(r.subgraph_count) for r in ok_runs]) if ok_runs else 0.0
    )
    avg_kernel_duration_ms = (
        statistics.fmean([float(r.kernel_duration_ms) for r in ok_runs]) if ok_runs else 0.0
    )
    avg_partition_duration_ms = (
        statistics.fmean([float(r.partition_duration_ms) for r in ok_runs]) if ok_runs else 0.0
    )
    avg_fusion_duration_ms = (
        statistics.fmean([float(r.fusion_duration_ms) for r in ok_runs]) if ok_runs else 0.0
    )
    avg_total_duration_ms = (
        statistics.fmean([float(r.total_duration_ms) for r in ok_runs]) if ok_runs else 0.0
    )

    gates_failed: list[str] = []
    if args.max_p95_ms > 0 and p95 > args.max_p95_ms:
        gates_failed.append(f"p95_ms={p95:.2f} > {args.max_p95_ms:.2f}")
    if args.max_avg_ms > 0 and avg_ms > args.max_avg_ms:
        gates_failed.append(f"avg_ms={avg_ms:.2f} > {args.max_avg_ms:.2f}")
    if args.expect_subgraph_count_min > 0 and avg_subgraph_count < args.expect_subgraph_count_min:
        gates_failed.append(
            f"avg_subgraph_count={avg_subgraph_count:.2f} < {args.expect_subgraph_count_min}"
        )
    if failures:
        gates_failed.append(f"run_failures={len(failures)}")

    payload: dict[str, Any] = {
        "schema": "omni.wendao.related_benchmark.v1",
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
            "avg_subgraph_count": round(avg_subgraph_count, 2),
            "avg_kernel_duration_ms": round(avg_kernel_duration_ms, 2),
            "avg_partition_duration_ms": round(avg_partition_duration_ms, 2),
            "avg_fusion_duration_ms": round(avg_fusion_duration_ms, 2),
            "avg_total_duration_ms": round(avg_total_duration_ms, 2),
        },
        "thresholds": {
            "max_p95_ms": float(args.max_p95_ms),
            "max_avg_ms": float(args.max_avg_ms),
            "expect_subgraph_count_min": int(args.expect_subgraph_count_min),
        },
        "gates_failed": gates_failed,
        "runs_detail": [asdict(item) for item in measured],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print("wendao related benchmark")
        print("=" * 48)
        print(f"binary: {binary}")
        print(f"profile: {'release' if args.release else 'debug'}")
        print(
            f"stem: {args.stem!r} max_distance={args.max_distance} "
            f"limit={args.limit} subgraph_mode={args.ppr_subgraph_mode or 'default'}"
        )
        print(
            "latency(ms): "
            f"avg={avg_ms:.2f} median={median_ms:.2f} p95={p95:.2f} "
            f"min={min_ms:.2f} max={max_ms:.2f}"
        )
        print(
            "diagnostics(ms): "
            f"kernel={avg_kernel_duration_ms:.2f} "
            f"partition={avg_partition_duration_ms:.2f} "
            f"fusion={avg_fusion_duration_ms:.2f} "
            f"total={avg_total_duration_ms:.2f} "
            f"avg_subgraph_count={avg_subgraph_count:.2f}"
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
