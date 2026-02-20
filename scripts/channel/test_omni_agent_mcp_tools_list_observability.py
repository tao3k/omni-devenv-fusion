#!/usr/bin/env python3
"""
Probe tools/list observability and performance for a running Omni MCP SSE server.

What this script checks in one run:
1. /health is reachable
2. tools/list returns valid payload + tool count + payload size
3. embed/batch returns vectors and dimension
4. tools/list latency profile (sequential sample + concurrent benchmarks)
5. Optional log scan for Dynamic Loader + tools/list stats lines
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, int(len(sorted_values) * p) - 1))
    return sorted_values[idx]


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


@dataclass
class SequentialStats:
    count: int
    first_ms: float
    second_ms: float
    min_ms: float
    median_ms: float
    max_ms: float


@dataclass
class BenchmarkStats:
    total: int
    concurrency: int
    errors: int
    elapsed_s: float
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


async def _call_tools_list(
    client: httpx.AsyncClient,
    rpc_url: str,
    request_id: int,
) -> tuple[float, int, int]:
    started = time.perf_counter()
    resp = await client.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error") is not None:
        raise RuntimeError(f"tools/list returned error: {payload['error']}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("tools/list result is not an object")
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError("tools/list result.tools is not a list")
    return elapsed_ms, len(resp.content), len(tools)


async def _run_sequential_profile(
    client: httpx.AsyncClient,
    rpc_url: str,
    *,
    sample_count: int,
    sleep_ms: int,
    start_id: int,
) -> SequentialStats:
    latencies: list[float] = []
    for i in range(sample_count):
        elapsed_ms, _, _ = await _call_tools_list(client, rpc_url, start_id + i)
        latencies.append(elapsed_ms)
        if sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000.0)

    sorted_lat = sorted(latencies)
    second = sorted_lat[1] if len(sorted_lat) > 1 else sorted_lat[0]
    return SequentialStats(
        count=len(sorted_lat),
        first_ms=round(sorted_lat[0], 2),
        second_ms=round(second, 2),
        min_ms=round(sorted_lat[0], 2),
        median_ms=round(statistics.median(sorted_lat), 2),
        max_ms=round(sorted_lat[-1], 2),
    )


async def _run_benchmark(
    client: httpx.AsyncClient,
    rpc_url: str,
    *,
    total: int,
    concurrency: int,
    start_id: int,
) -> BenchmarkStats:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors = 0

    async def one(idx: int) -> None:
        nonlocal errors
        async with semaphore:
            try:
                elapsed_ms, _, _ = await _call_tools_list(client, rpc_url, start_id + idx)
            except Exception:
                errors += 1
                return
            latencies.append(elapsed_ms)

    started = time.perf_counter()
    await asyncio.gather(*(one(i) for i in range(total)))
    elapsed_s = time.perf_counter() - started
    sorted_lat = sorted(latencies)

    p50 = _percentile(sorted_lat, 0.50)
    p95 = _percentile(sorted_lat, 0.95)
    p99 = _percentile(sorted_lat, 0.99)
    rps = (total / elapsed_s) if elapsed_s > 0 else 0.0

    return BenchmarkStats(
        total=total,
        concurrency=concurrency,
        errors=errors,
        elapsed_s=round(elapsed_s, 3),
        rps=round(rps, 2),
        p50_ms=round(p50, 2),
        p95_ms=round(p95, 2),
        p99_ms=round(p99, 2),
    )


_TOOLS_STATS_LINE_RE = re.compile(
    r"requests=(?P<requests>\d+)\s+hit_rate=(?P<hit_rate>[0-9.]+)%\s+"
    r"cache_hits=(?P<cache_hits>\d+)\s+cache_misses=(?P<cache_misses>\d+)\s+"
    r"build_count=(?P<build_count>\d+)\s+build_failures=(?P<build_failures>\d+)\s+"
    r"build_avg_ms=(?P<build_avg_ms>[0-9.]+)\s+build_max_ms=(?P<build_max_ms>[0-9.]+)"
)


def _scan_log_file(log_file: Path) -> dict[str, Any]:
    if not log_file.exists():
        return {"exists": False}

    content = log_file.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    dynamic_loader_lines = [line for line in lines if "Dynamic Loader" in line]
    tools_stats_lines = [line for line in lines if "[MCP] tools/list stats" in line]
    tools_served_debug_lines = [line for line in lines if "tools/list served" in line]

    parsed_stats: dict[str, Any] | None = None
    if tools_stats_lines:
        match = _TOOLS_STATS_LINE_RE.search(tools_stats_lines[-1])
        if match:
            parsed_stats = {
                "requests": int(match.group("requests")),
                "hit_rate_pct": float(match.group("hit_rate")),
                "cache_hits": int(match.group("cache_hits")),
                "cache_misses": int(match.group("cache_misses")),
                "build_count": int(match.group("build_count")),
                "build_failures": int(match.group("build_failures")),
                "build_avg_ms": float(match.group("build_avg_ms")),
                "build_max_ms": float(match.group("build_max_ms")),
            }

    return {
        "exists": True,
        "path": str(log_file),
        "dynamic_loader_count": len(dynamic_loader_lines),
        "tools_list_stats_count": len(tools_stats_lines),
        "tools_list_served_debug_count": len(tools_served_debug_lines),
        "last_dynamic_loader_line": dynamic_loader_lines[-1] if dynamic_loader_lines else None,
        "last_tools_list_stats_line": tools_stats_lines[-1] if tools_stats_lines else None,
        "parsed_last_tools_list_stats": parsed_stats,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot tools/list observability + benchmark probe for a running Omni MCP server."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:3002")
    parser.add_argument("--timeout-secs", type=float, default=30.0)
    parser.add_argument("--sequential-samples", type=int, default=20)
    parser.add_argument("--sequential-sleep-ms", type=int, default=50)
    parser.add_argument("--bench-small-total", type=int, default=200)
    parser.add_argument("--bench-small-concurrency", type=int, default=40)
    parser.add_argument("--bench-large-total", type=int, default=1000)
    parser.add_argument("--bench-large-concurrency", type=int, default=100)
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional runtime log file path for Dynamic Loader/tools-list stats checks.",
    )
    parser.add_argument(
        "--allow-request-errors",
        action="store_true",
        help="Do not fail process exit on benchmark request errors.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write full JSON summary.",
    )
    return parser.parse_args()


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    base_url = _normalize_base_url(args.base_url)
    health_url = f"{base_url}/health"
    rpc_url = f"{base_url}/"
    embed_url = f"{base_url}/embed/batch"

    timeout = httpx.Timeout(args.timeout_secs)
    async with httpx.AsyncClient(timeout=timeout) as client:
        health_resp = await client.get(health_url)
        health_resp.raise_for_status()

        first_latency_ms, payload_bytes, tool_count = await _call_tools_list(client, rpc_url, 1)
        sequential = await _run_sequential_profile(
            client,
            rpc_url,
            sample_count=args.sequential_samples,
            sleep_ms=args.sequential_sleep_ms,
            start_id=1000,
        )

        small = await _run_benchmark(
            client,
            rpc_url,
            total=args.bench_small_total,
            concurrency=args.bench_small_concurrency,
            start_id=10_000,
        )
        large = await _run_benchmark(
            client,
            rpc_url,
            total=args.bench_large_total,
            concurrency=args.bench_large_concurrency,
            start_id=20_000,
        )

        embed_resp = await client.post(embed_url, json={"texts": ["obs-probe-a", "obs-probe-b"]})
        embed_resp.raise_for_status()
        embed_payload = embed_resp.json()
        vectors = embed_payload.get("vectors")
        if not isinstance(vectors, list) or not vectors or not isinstance(vectors[0], list):
            raise RuntimeError("embed/batch returned invalid vectors payload")

    log_scan = _scan_log_file(args.log_file) if args.log_file else None

    return {
        "base_url": base_url,
        "health_ok": True,
        "tools_list": {
            "tool_count": tool_count,
            "payload_bytes": payload_bytes,
            "first_call_ms": round(first_latency_ms, 2),
        },
        "embed_batch": {
            "vector_count": len(vectors),
            "vector_dim": len(vectors[0]),
        },
        "sequential_profile": asdict(sequential),
        "benchmarks": {
            "small": asdict(small),
            "large": asdict(large),
        },
        "log_scan": log_scan,
    }


def main() -> int:
    args = _parse_args()
    try:
        summary = asyncio.run(_run_probe(args))
    except Exception as exc:
        print(f"probe_failed: {exc}", file=sys.stderr)
        return 1

    small_errors = int(summary["benchmarks"]["small"]["errors"])
    large_errors = int(summary["benchmarks"]["large"]["errors"])
    error_total = small_errors + large_errors

    print("=== MCP tools/list observability probe ===")
    print(f"base_url: {summary['base_url']}")
    print(
        "tools/list: "
        f"count={summary['tools_list']['tool_count']} "
        f"payload_bytes={summary['tools_list']['payload_bytes']} "
        f"first_call_ms={summary['tools_list']['first_call_ms']}"
    )
    print(
        "embed/batch: "
        f"vectors={summary['embed_batch']['vector_count']} "
        f"dim={summary['embed_batch']['vector_dim']}"
    )
    print(f"sequential: {summary['sequential_profile']}")
    print(f"bench_small: {summary['benchmarks']['small']}")
    print(f"bench_large: {summary['benchmarks']['large']}")
    if summary["log_scan"] is not None:
        print(f"log_scan: {summary['log_scan']}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"json_out: {args.json_out}")

    print("--- summary_json ---")
    print(json.dumps(summary, ensure_ascii=False))

    if error_total > 0 and not args.allow_request_errors:
        print(
            f"probe_failed: benchmark request errors detected (errors={error_total})",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
