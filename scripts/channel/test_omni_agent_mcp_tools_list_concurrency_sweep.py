#!/usr/bin/env python3
"""
Run MCP tools/list concurrency sweep and emit recommendation by SLO.

Outputs:
- JSON report: machine-readable sweep metrics + recommendation
- Markdown report: concise table for quick review
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import httpx

from omni.agent.mcp_server.tools_list_sweep import (
    SweepPoint,
    recommend_concurrency_by_slo,
    recommended_http_pool_limits,
)


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _nearest_rank_percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, int(len(sorted_values) * p) - 1))
    return sorted_values[idx]


def _default_report_paths(base_url: str) -> tuple[Path, Path]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    stem = f"mcp-tools-list-observability-{host.replace('.', '_')}-{port}-concurrency-sweep"
    report_root = Path(".run/reports")
    return report_root / f"{stem}.json", report_root / f"{stem}.md"


async def _call_tools_list(
    client: httpx.AsyncClient,
    rpc_url: str,
    request_id: int,
) -> float:
    started = time.perf_counter()
    response = await client.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    response.raise_for_status()
    payload = response.json()
    if payload.get("error") is not None:
        raise RuntimeError(f"tools/list returned error: {payload['error']}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("tools/list result is not an object")
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError("tools/list result.tools is not a list")
    return elapsed_ms


async def _run_benchmark(
    client: httpx.AsyncClient,
    rpc_url: str,
    *,
    total: int,
    concurrency: int,
    start_id: int,
) -> SweepPoint:
    semaphore = asyncio.Semaphore(concurrency)
    latencies_ms: list[float] = []
    errors = 0

    async def one(index: int) -> None:
        nonlocal errors
        async with semaphore:
            try:
                elapsed_ms = await _call_tools_list(client, rpc_url, start_id + index)
            except Exception:
                errors += 1
                return
            latencies_ms.append(elapsed_ms)

    started = time.perf_counter()
    await asyncio.gather(*(one(i) for i in range(total)))
    elapsed_s = time.perf_counter() - started

    sorted_lat = sorted(latencies_ms)
    p50_ms = _nearest_rank_percentile(sorted_lat, 0.50)
    p95_ms = _nearest_rank_percentile(sorted_lat, 0.95)
    p99_ms = _nearest_rank_percentile(sorted_lat, 0.99)
    rps = total / elapsed_s if elapsed_s > 0 else 0.0

    return SweepPoint(
        concurrency=concurrency,
        total=total,
        errors=errors,
        elapsed_s=round(elapsed_s, 3),
        rps=round(rps, 2),
        p50_ms=round(p50_ms, 2),
        p95_ms=round(p95_ms, 2),
        p99_ms=round(p99_ms, 2),
    )


def _parse_concurrency_values(raw: str) -> list[int]:
    values = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        value = int(token)
        if value <= 0:
            raise ValueError("concurrency values must be positive integers")
        values.append(value)
    if not values:
        raise ValueError("at least one concurrency value is required")
    return sorted(set(values))


def _build_markdown(
    *,
    base_url: str,
    points: list[SweepPoint],
    p95_slo_ms: float,
    p99_slo_ms: float,
    recommendation_concurrency: int | None,
    recommendation_reason: str,
    knee_concurrency: int | None,
) -> str:
    lines = [
        f"# MCP tools/list Concurrency Sweep ({base_url})",
        "",
        f"SLO target: `p95 <= {p95_slo_ms}ms`, `p99 <= {p99_slo_ms}ms`",
        "",
        "| Concurrency | Total | Errors | RPS | p50 (ms) | p95 (ms) | p99 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in points:
        lines.append(
            f"| {point.concurrency} | {point.total} | {point.errors} | {point.rps} | "
            f"{point.p50_ms} | {point.p95_ms} | {point.p99_ms} |"
        )
    lines.extend(
        [
            "",
            f"Estimated knee concurrency: `{knee_concurrency}`"
            if knee_concurrency
            else "Estimated knee concurrency: `not detected`",
            f"Recommended concurrency: `{recommendation_concurrency}`"
            if recommendation_concurrency
            else "Recommended concurrency: `none`",
            f"Recommendation reason: {recommendation_reason}",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MCP tools/list concurrency sweep and output recommendation."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:3002")
    parser.add_argument("--timeout-secs", type=float, default=30.0)
    parser.add_argument("--concurrency-values", default="40,80,120,160,200")
    parser.add_argument("--total", type=int, default=1000, help="Requests per concurrency point.")
    parser.add_argument("--warmup-calls", type=int, default=2)
    parser.add_argument("--p95-slo-ms", type=float, default=400.0)
    parser.add_argument("--p99-slo-ms", type=float, default=800.0)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument(
        "--allow-request-errors",
        action="store_true",
        help="Do not fail process exit when request errors are present.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict[str, object]:
    base_url = _normalize_base_url(args.base_url)
    health_url = f"{base_url}/health"
    rpc_url = f"{base_url}/"
    timeout = httpx.Timeout(args.timeout_secs)

    concurrency_values = _parse_concurrency_values(args.concurrency_values)
    max_connections, max_keepalive_connections = recommended_http_pool_limits(
        max(concurrency_values)
    )
    if args.total <= 0:
        raise ValueError("--total must be positive")
    if args.warmup_calls < 0:
        raise ValueError("--warmup-calls must be >= 0")

    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
    )
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        health_response = await client.get(health_url)
        health_response.raise_for_status()
        health_payload = health_response.json()

        for warmup_idx in range(args.warmup_calls):
            await _call_tools_list(client, rpc_url, warmup_idx + 1)

        points: list[SweepPoint] = []
        for index, concurrency in enumerate(concurrency_values):
            point = await _run_benchmark(
                client,
                rpc_url,
                total=args.total,
                concurrency=concurrency,
                start_id=10_000 + (index * 100_000),
            )
            points.append(point)

    recommendation = recommend_concurrency_by_slo(
        points,
        p95_slo_ms=args.p95_slo_ms,
        p99_slo_ms=args.p99_slo_ms,
    )

    mean_rps = round(statistics.mean(point.rps for point in points), 2)
    error_total = sum(point.errors for point in points)
    return {
        "base_url": base_url,
        "health_ok": True,
        "health_status": health_payload.get("status"),
        "slo": {"p95_ms": args.p95_slo_ms, "p99_ms": args.p99_slo_ms},
        "total_per_point": args.total,
        "concurrency_values": concurrency_values,
        "http_client_limits": {
            "max_connections": max_connections,
            "max_keepalive_connections": max_keepalive_connections,
        },
        "points": [asdict(point) for point in points],
        "summary": {
            "point_count": len(points),
            "error_total": error_total,
            "mean_rps": mean_rps,
        },
        "recommendation": {
            "recommended_concurrency": recommendation.recommended_concurrency,
            "reason": recommendation.reason,
            "feasible_concurrency": list(recommendation.feasible_concurrency),
            "knee_concurrency": recommendation.knee_concurrency,
        },
    }


def main() -> int:
    args = _parse_args()
    default_json_out, default_markdown_out = _default_report_paths(
        _normalize_base_url(args.base_url)
    )
    json_out = args.json_out or default_json_out
    markdown_out = args.markdown_out or default_markdown_out

    try:
        summary = asyncio.run(_run(args))
    except Exception as exc:
        print(f"sweep_failed: {exc}", file=sys.stderr)
        return 1

    points = [SweepPoint(**point) for point in summary["points"]]  # type: ignore[arg-type]
    recommendation = summary["recommendation"]  # type: ignore[assignment]

    print("=== MCP tools/list concurrency sweep ===")
    print(f"base_url: {summary['base_url']}")
    print(f"concurrency_values: {summary['concurrency_values']}")
    print(f"http_client_limits: {summary['http_client_limits']}")
    print(f"total_per_point: {summary['total_per_point']}")
    print(f"slo: {summary['slo']}")
    for point in points:
        print(
            "point: "
            f"c={point.concurrency} total={point.total} err={point.errors} "
            f"rps={point.rps} p50={point.p50_ms} p95={point.p95_ms} p99={point.p99_ms}"
        )
    print(
        "recommendation: "
        f"concurrency={recommendation['recommended_concurrency']} "
        f"knee={recommendation['knee_concurrency']} "
        f"reason={recommendation['reason']}"
    )

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(
        _build_markdown(
            base_url=str(summary["base_url"]),
            points=points,
            p95_slo_ms=float(summary["slo"]["p95_ms"]),  # type: ignore[index]
            p99_slo_ms=float(summary["slo"]["p99_ms"]),  # type: ignore[index]
            recommendation_concurrency=recommendation["recommended_concurrency"],  # type: ignore[index]
            recommendation_reason=str(recommendation["reason"]),  # type: ignore[index]
            knee_concurrency=recommendation["knee_concurrency"],  # type: ignore[index]
        ),
        encoding="utf-8",
    )
    print(f"json_out: {json_out}")
    print(f"markdown_out: {markdown_out}")
    print("--- summary_json ---")
    print(json.dumps(summary, ensure_ascii=False))

    if int(summary["summary"]["error_total"]) > 0 and not args.allow_request_errors:  # type: ignore[index]
        print("sweep_failed: request errors detected", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
