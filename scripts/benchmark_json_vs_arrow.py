#!/usr/bin/env python3
"""Benchmark: vector search JSON path vs Arrow IPC path.

Compares:
  - JSON: store.search_optimized() → list of JSON strings → parse_vector_payload each
  - Arrow: store.search_optimized_ipc() → IPC bytes → pyarrow.Table → VectorPayload.from_arrow_table

Usage:
  # Use synced store (after omni sync) - recommended
  uv run python scripts/benchmark_json_vs_arrow.py --use-cache [--iters 50] [--limit 20]
  # Or index into a temp dir from repo
  uv run python scripts/benchmark_json_vs_arrow.py --repo . --iters 30

Requires: omni_core_rs. With --use-cache requires existing skills table (omni sync). Without: repo with assets/skills.
"""

from __future__ import annotations

import io
import statistics
import sys
import time
from pathlib import Path

# Add repo root for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_json_path(store, table_name: str, query_vector: list[float], limit: int, iters: int):
    from omni.foundation.services.vector_schema import parse_vector_payload

    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        raw_list = store.search_optimized(table_name, query_vector, limit, None)
        payloads = [parse_vector_payload(raw) for raw in raw_list]
        times.append(time.perf_counter() - t0)
    return times


def _run_arrow_path(
    store, table_name: str, query_vector: list[float], limit: int, iters: int, projection: bool
):
    import pyarrow.ipc
    from omni.foundation.services.vector_schema import VectorPayload

    proj = ["id", "content", "_distance", "metadata"] if projection else None
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        ipc_bytes = store.search_optimized_ipc(
            table_name, query_vector, limit, None, projection=proj
        )
        table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
        payloads = VectorPayload.from_arrow_table(table)
        times.append(time.perf_counter() - t0)
    return times


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark JSON vs Arrow vector search path")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use project synced store (.cache/omni-vector); no indexing",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT,
        help="Repo root (for assets/skills when not --use-cache)",
    )
    parser.add_argument("--iters", type=int, default=50, help="Iterations per path")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Search limit (use 100+ to see larger Arrow advantage)",
    )
    parser.add_argument(
        "--projection",
        action="store_true",
        help="Use IPC projection (id, content, _distance, metadata) for Arrow path",
    )
    parser.add_argument("--dim", type=int, default=384, help="Query vector dimension")
    args = parser.parse_args()

    try:
        from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore
        from omni.foundation.utils.asyncio import run_async_blocking
    except ImportError:
        print("Cannot import omni.foundation; run from repo with uv run python scripts/...")
        return 1

    if not RUST_AVAILABLE:
        print("omni_core_rs not available; skip benchmark")
        return 0

    store = None
    table_name = "skills"
    dim = args.dim
    if args.use_cache:
        try:
            import re
            from omni.foundation.config.database import get_vector_db_path
            from omni.foundation.services.index_dimension import get_embedding_dimension_status

            cache_path = get_vector_db_path()
            if cache_path.is_dir():
                dim_status = get_embedding_dimension_status()
                dim = (
                    dim_status.index_dim
                    if dim_status.index_dim is not None
                    else dim_status.current_dim
                )
                store = RustVectorStore(str(cache_path), dim, True)
                health = store.analyze_table_health(table_name)
                if health.get("row_count", 0) == 0:
                    print("skills table has 0 rows; run omni sync first")
                    return 0
                # If index was built with different dim (e.g. 1536), retry with dim from error
                try:
                    store.search_optimized_ipc(table_name, [0.0] * dim, 1, None)
                except RuntimeError as e:
                    m = re.search(r"vector dim\((\d+)\)", str(e))
                    if m:
                        dim = int(m.group(1))
                        store = RustVectorStore(str(cache_path), dim, True)
            else:
                print("Vector cache dir not found; run omni sync")
                return 0
        except Exception as e:
            print("Failed to use cache:", e)
            return 0
    if store is None:
        tmp = Path("/tmp/omni-bench-json-arrow")
        tmp.mkdir(parents=True, exist_ok=True)
        store = RustVectorStore(str(tmp), args.dim, True)
        skills_base = args.repo / "assets" / "skills"
        if not skills_base.is_dir():
            print("assets/skills not found; skip benchmark")
            return 0
        n = run_async_blocking(store.index_skill_tools(str(args.repo), table_name))
        if n == 0:
            print("index_skill_tools returned 0; skip benchmark")
            return 0

    query_vector = [0.0] * dim

    json_times = _run_json_path(store, table_name, query_vector, args.limit, args.iters)
    arrow_times = _run_arrow_path(
        store, table_name, query_vector, args.limit, args.iters, args.projection
    )

    json_mean = statistics.mean(json_times) * 1000
    json_stdev = statistics.stdev(json_times) * 1000 if len(json_times) > 1 else 0
    arrow_mean = statistics.mean(arrow_times) * 1000
    arrow_stdev = statistics.stdev(arrow_times) * 1000 if len(arrow_times) > 1 else 0
    ratio = json_mean / arrow_mean if arrow_mean > 0 else 0

    print("Vector search (limit={}, iters={})".format(args.limit, args.iters))
    print("  JSON path:  {:.2f} ms ± {:.2f}".format(json_mean, json_stdev))
    print("  Arrow path: {:.2f} ms ± {:.2f}".format(arrow_mean, arrow_stdev))
    print("  Ratio (JSON/Arrow): {:.2f}x".format(ratio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
