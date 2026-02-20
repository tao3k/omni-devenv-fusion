#!/usr/bin/env python3
"""
Profile knowledge.recall: timing + memory (RSS) to isolate latency and memory issues.

Uses the same code path as `omni skill run knowledge.recall` (run_skill).
Run from repo root to test before blaming MCP.

Usage:
    uv run python scripts/recall_profile.py --verbose
    uv run python scripts/recall_profile.py -v --query "什么是 librarian"
    uv run python scripts/recall_profile.py --runs 3 --json
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import resource
import sys
import time
from typing import Any


def _progress(msg: str, verbose: bool = False) -> None:
    """Print progress to stderr (always visible, flush immediately)."""
    if verbose:
        print(f"  [recall] {msg}", file=sys.stderr, flush=True)


def _rss_mb() -> float:
    """Current process RSS in MiB."""
    try:
        r = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(r, "ru_maxrss", 0) or 0
        if sys.platform == "darwin":
            return round(rss / (1024 * 1024), 2)
        return round(rss / 1024, 2)
    except Exception:
        return 0.0


async def _run_recall(
    query: str,
    limit: int = 5,
    chunked: bool = False,
    verbose: bool = False,
) -> tuple[float, float, float, Any]:
    """Run knowledge.recall, return (elapsed_sec, rss_before_mb, rss_after_mb, result)."""
    from omni.core.skills import run_skill

    _progress("init: get_vector_store, run_skill...", verbose)
    rss_before = _rss_mb()
    gc.collect()
    t0 = time.perf_counter()

    async def _heartbeat() -> None:
        """Print heartbeat every 5s when verbose (shows where it blocks)."""
        n = 0
        while True:
            await asyncio.sleep(5)
            n += 1
            elapsed = time.perf_counter() - t0
            _progress(f"heartbeat {n}: {elapsed:.0f}s elapsed (recall still running)", verbose)

    args = {"query": query, "limit": limit, "chunked": chunked}
    hb_task: asyncio.Task | None = None
    if verbose:
        hb_task = asyncio.create_task(_heartbeat())
    try:
        result = await run_skill("knowledge", "recall", args)
    except Exception as e:
        result = {"error": str(e)}
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

    elapsed = time.perf_counter() - t0
    rss_after = _rss_mb()
    _progress(f"done: {elapsed:.1f}s, RSS Δ{rss_after - rss_before:+.0f} MiB", verbose)

    return elapsed, rss_before, rss_after, result


def _summarize_result(result: Any) -> str:
    """Extract a short summary from recall result."""
    if isinstance(result, dict):
        if "error" in result:
            return f"ERROR: {result['error'][:100]}"
        count = result.get("all_chunks_count") or result.get("results", [])
        if isinstance(count, list):
            count = len(count)
        return f"chunks={count}"
    return str(result)[:80]


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile knowledge.recall: timing + memory (same path as omni skill run)"
    )
    parser.add_argument(
        "--query",
        "-q",
        default="什么是 librarian",
        help="Recall query (default: 什么是 librarian)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=5,
        help="Max results (default: 5)",
    )
    parser.add_argument(
        "--chunked",
        action="store_true",
        help="Use chunked workflow (default: False for faster single-call)",
    )
    parser.add_argument(
        "--runs",
        "-n",
        type=int,
        default=1,
        help="Number of runs (default: 1)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--gc-between",
        action="store_true",
        help="Force GC between runs to measure per-call memory",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose: DEBUG logs + progress prints (see where it blocks)",
    )
    args = parser.parse_args()

    if args.verbose:
        from omni.foundation.config.logging import configure_logging

        configure_logging(level="DEBUG", verbose=True)
        print("recall_profile: verbose=ON (DEBUG logs + progress)", file=sys.stderr, flush=True)

    runs: list[dict] = []
    for i in range(args.runs):
        elapsed, rss_before, rss_after, result = await _run_recall(
            query=args.query,
            limit=args.limit,
            chunked=args.chunked,
            verbose=args.verbose,
        )
        delta_mb = round(rss_after - rss_before, 2)
        summary = _summarize_result(result)
        runs.append(
            {
                "run": i + 1,
                "elapsed_sec": round(elapsed, 2),
                "rss_before_mb": rss_before,
                "rss_after_mb": rss_after,
                "delta_mb": delta_mb,
                "summary": summary,
            }
        )
        if args.gc_between and i < args.runs - 1:
            gc.collect()

    if args.json:
        out = {
            "query": args.query,
            "limit": args.limit,
            "chunked": args.chunked,
            "runs": runs,
            "avg_elapsed_sec": round(sum(r["elapsed_sec"] for r in runs) / len(runs), 2),
            "max_delta_mb": max(r["delta_mb"] for r in runs),
        }
        print(json.dumps(out, indent=2))
        return 0

    # Human-readable report
    print("=" * 60)
    print("knowledge.recall profile (same path as omni skill run)")
    print("=" * 60)
    print(f"Query:  {args.query!r}")
    print(f"Limit:  {args.limit}")
    print(f"Chunked: {args.chunked}")
    print(f"Runs:   {args.runs}")
    print("-" * 60)
    for r in runs:
        status = "ok" if "ERROR" not in r["summary"] else "FAIL"
        print(
            f"  Run {r['run']}: {r['elapsed_sec']:.2f}s  "
            f"RSS {r['rss_before_mb']:.1f}→{r['rss_after_mb']:.1f} MiB "
            f"(Δ{r['delta_mb']:+.1f})  {r['summary'][:40]}  [{status}]"
        )
    print("-" * 60)
    avg_sec = sum(r["elapsed_sec"] for r in runs) / len(runs)
    max_delta = max(r["delta_mb"] for r in runs)
    print(f"Avg elapsed: {avg_sec:.2f}s")
    print(f"Max RSS delta: {max_delta:+.1f} MiB")
    print("")
    print("If delta_mb is large (>100): check recall/vector/graph for leaks.")
    print("If elapsed is high: check embedding HTTP, vector search, dual-core boost.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
