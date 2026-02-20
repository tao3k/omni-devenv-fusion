#!/usr/bin/env python3
"""
Phase-level profiling for knowledge.recall to isolate latency bottlenecks.

Times: init, embed, vector_search, dual_core, total.
Run: uv run python scripts/recall_profile_phases.py
     uv run python scripts/recall_profile_phases.py --query "什么是 librarian"
"""

from __future__ import annotations

import argparse
import asyncio
import resource
import sys
import time
from typing import Any

from omni.foundation.runtime.skill_optimization import is_low_signal_query


def _rss_mb() -> float:
    try:
        r = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(r, "ru_maxrss", 0) or 0
        if sys.platform == "darwin":
            return round(rss / (1024 * 1024), 2)
        return round(rss / 1024, 2)
    except Exception:
        return 0.0


async def _time_phase(name: str, coro) -> tuple[float, Any]:
    t0 = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - t0
    return elapsed, result


async def main() -> int:
    parser = argparse.ArgumentParser(description="Phase-level recall profiling")
    parser.add_argument(
        "--query",
        "-q",
        default="什么是 librarian",
        help="Recall query (default: 什么是 librarian)",
    )
    parser.add_argument("--limit", "-l", type=int, default=5, help="Result limit")
    args = parser.parse_args()

    query = args.query
    limit = args.limit
    fetch_limit = max(limit * 4, 20)
    low_signal = is_low_signal_query(query, min_non_space_chars=2)

    phases: dict[str, float] = {}
    rss: dict[str, float] = {}

    # Phase 0: init (get_vector_store, get_store_for_collection)
    rss["start"] = _rss_mb()
    t0 = time.perf_counter()
    from omni.foundation import get_vector_store

    vector_store = get_vector_store()
    store = vector_store.get_store_for_collection("knowledge_chunks")
    phases["init"] = time.perf_counter() - t0
    rss["after_init"] = _rss_mb()

    if not store:
        print("ERROR: Vector store not available")
        return 1

    # Phase 1a: embedding only
    t0 = time.perf_counter()
    vector: list[float] | None = None
    try:
        from omni.agent.cli.mcp_embed import embed_via_mcp
        from omni.foundation.services.vector.search import search_embed_timeout

        timeout = search_embed_timeout()
        vectors = await asyncio.wait_for(
            embed_via_mcp([query], port=3002, path="/messages/", timeout=timeout),
            timeout=timeout,
        )
        vector = vectors[0] if vectors else None
    except Exception as e:
        print(f"  embed failed: {e}, trying HTTP fallback...")
        from omni.foundation.config.settings import get_setting
        from omni.foundation.embedding_client import get_embedding_client

        base_url = get_setting("embedding.client_url") or (
            f"http://127.0.0.1:{int(get_setting('embedding.http_port', 18501))}"
        )
        emb_client = get_embedding_client(base_url)
        vectors = await emb_client.embed_batch([query], timeout_seconds=5)
        vector = vectors[0] if vectors else None
    phases["embed"] = time.perf_counter() - t0
    rss["after_embed"] = _rss_mb()

    if not vector:
        print("ERROR: No embedding vector")
        return 1

    # Phase 1b: vector search (Rust)
    t0 = time.perf_counter()
    from omni.foundation.services.vector_schema import build_search_options_json

    options_json = build_search_options_json({})
    raw_results = []
    if hasattr(store, "search_optimized_ipc"):
        try:
            import io

            import pyarrow.ipc

            ipc_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    store.search_optimized_ipc,
                    "knowledge_chunks",
                    vector,
                    fetch_limit,
                    options_json,
                    projection=["id", "content", "_distance", "metadata"],
                ),
                timeout=10,
            )
            table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
            from omni.foundation.services.vector.models import SearchResult
            from omni.foundation.services.vector_schema import VectorPayload

            for p in VectorPayload.from_arrow_table(table):
                score = p.score if p.score is not None else 1.0 / (1.0 + max(p.distance or 0, 0.0))
                raw_results.append(
                    SearchResult(
                        content=p.content,
                        metadata=p.metadata,
                        distance=p.distance,
                        score=score,
                        id=p.id,
                    )
                )
        except Exception as e:
            print(f"  IPC search failed: {e}")
    if not raw_results and hasattr(store, "search_optimized"):
        results_json = await asyncio.to_thread(
            store.search_optimized,
            "knowledge_chunks",
            vector,
            fetch_limit,
            options_json,
        )
        from omni.foundation.services.vector.models import SearchResult
        from omni.foundation.services.vector_schema import parse_vector_payload

        for raw in results_json:
            payload = parse_vector_payload(raw)
            rid, content, metadata, distance = payload.to_search_result_fields()
            score = payload.score or (1.0 / (1.0 + max(distance, 0.0)))
            raw_results.append(
                SearchResult(
                    content=content, metadata=metadata, distance=distance, score=score, id=rid
                )
            )
    phases["vector_search"] = time.perf_counter() - t0
    rss["after_search"] = _rss_mb()

    # Convert to result_dicts for dual_core
    result_dicts = []
    for r in raw_results:
        meta = r.metadata if isinstance(getattr(r, "metadata", None), dict) else {}
        result_dicts.append(
            {
                "content": r.content,
                "source": meta.get("source") or r.id,
                "score": r.score if r.score is not None else (1.0 / (1.0 + max(r.distance, 0.0))),
                "title": meta.get("title", ""),
                "section": meta.get("section", ""),
            }
        )

    # Phase 2: dual_core boost (split into sub-phases)
    phases["dual_core"] = 0.0
    phases["dual_core_graph"] = 0.0
    phases["dual_core_kg"] = 0.0
    if not low_signal:
        try:
            from omni.rag.dual_core import (
                apply_kg_recall_boost,
                compute_fusion_weights,
                link_graph_proximity_boost,
            )

            t_fusion = time.perf_counter()
            fusion = compute_fusion_weights(query)
            phases["dual_core_fusion"] = time.perf_counter() - t_fusion

            t_graph = time.perf_counter()
            result_dicts = await link_graph_proximity_boost(
                result_dicts, query, fusion_scale=fusion.link_graph_proximity_scale
            )
            phases["dual_core_graph"] = time.perf_counter() - t_graph

            t_kg = time.perf_counter()
            result_dicts = apply_kg_recall_boost(
                result_dicts,
                query,
                fusion_scale=fusion.link_graph_entity_scale,
                intent_keywords=fusion.intent_keywords,
            )
            phases["dual_core_kg"] = time.perf_counter() - t_kg

            phases["dual_core"] = (
                phases["dual_core_fusion"] + phases["dual_core_graph"] + phases["dual_core_kg"]
            )
        except Exception as e:
            print(f"  dual_core skipped: {e}")
    else:
        phases["dual_core_skipped_low_signal"] = 1.0
    rss["after_dual_core"] = _rss_mb()

    # Second run (cache warm): same query to measure graph cache hit.
    phases2: dict[str, float] = {}
    if not low_signal:
        try:
            from omni.rag.dual_core import link_graph_proximity_boost

            t_graph2 = time.perf_counter()
            result_dicts2 = [dict(r) for r in result_dicts]
            result_dicts2 = await link_graph_proximity_boost(result_dicts2, query, fusion_scale=1.0)
            phases2["dual_core_graph"] = time.perf_counter() - t_graph2
        except Exception:
            pass

    # Report
    print("=" * 60)
    print("knowledge.recall phase breakdown")
    print("=" * 60)
    print(f"Query: {query!r}  limit={limit}  fetch_limit={fetch_limit}")
    if low_signal:
        print(
            "Note: low-signal query detected -> dual_core skipped (matches production recall path)"
        )
    print("-" * 60)
    total = sum(
        v for k, v in phases.items() if k in ("init", "embed", "vector_search", "dual_core")
    )
    for name in (
        "init",
        "embed",
        "vector_search",
        "dual_core_fusion",
        "dual_core_graph",
        "dual_core_kg",
        "dual_core",
    ):
        sec = phases.get(name, 0)
        if sec == 0 and name not in phases:
            continue
        pct = (sec / total * 100) if total else 0
        print(f"  {name:20} {sec:8.2f}s  ({pct:.0f}% of total)")
    print("-" * 60)
    print(f"  {'TOTAL':20} {total:8.2f}s")
    if phases2:
        graph2 = phases2.get("dual_core_graph", 0)
        print()
        print(f"  (2nd run, graph cache warm: dual_core_graph={graph2:.2f}s)")
    print()
    print("RSS (MiB):", rss)
    print("  delta init:", round(rss["after_init"] - rss["start"], 1))
    print("  delta embed:", round(rss.get("after_embed", rss["after_init"]) - rss["after_init"], 1))
    print(
        "  delta search:", round(rss["after_search"] - rss.get("after_embed", rss["after_init"]), 1)
    )
    print("  delta dual_core:", round(rss["after_dual_core"] - rss["after_search"], 1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
