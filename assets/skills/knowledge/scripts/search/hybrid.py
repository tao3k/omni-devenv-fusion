"""Hybrid search routed by common LinkGraph retrieval policy."""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from omni.rag.link_graph import (
    get_link_graph_backend,
    get_link_graph_stats_for_response,
    link_graph_hits_to_hybrid_results,
    merge_hybrid_results,
    plan_link_graph_retrieval,
    resolve_link_graph_policy_config,
    vector_rows_to_hybrid_results,
)

try:
    from .vector import run_vector_search
except ImportError:
    import importlib.util
    from pathlib import Path

    _vector_path = Path(__file__).with_name("vector.py")
    _vector_spec = importlib.util.spec_from_file_location(
        "_skill_knowledge_search_vector", _vector_path
    )
    if _vector_spec and _vector_spec.loader:
        _vector_module = importlib.util.module_from_spec(_vector_spec)
        _vector_spec.loader.exec_module(_vector_module)
        run_vector_search = _vector_module.run_vector_search
    else:
        raise

logger = get_logger("skill.knowledge.search.hybrid")


def _normalize_graph_stats(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        raw = {}
    out: dict[str, int] = {}
    for key in ("total_notes", "orphans", "links_in_graph", "nodes_in_graph"):
        try:
            out[key] = max(0, int(raw.get(key, 0) or 0))
        except (TypeError, ValueError):
            out[key] = 0
    return out


def _split_graph_stats_payload(payload: Any) -> tuple[dict[str, int], dict[str, Any]]:
    if isinstance(payload, tuple) and len(payload) == 2:
        stats, meta = payload
        stats_row = _normalize_graph_stats(stats)
        meta_row = meta if isinstance(meta, dict) else {}
        return stats_row, dict(meta_row)
    return _normalize_graph_stats(payload), {}


def _extract_vector_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in ("results", "preview_results", "merged", "vector_results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


async def _run_vector_fallback(
    query: str,
    *,
    limit: int,
    paths: ConfigPaths,
) -> list[dict[str, Any]]:
    payload = await run_vector_search(
        query=query,
        limit=limit,
        collection="knowledge_chunks",
        paths=paths,
    )
    return vector_rows_to_hybrid_results(_extract_vector_rows(payload))


async def run_hybrid_search(
    query: str,
    max_results: int = 10,
    use_hybrid: bool = True,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Run graph-first policy; fallback to vector only when graph is insufficient."""
    if paths is None:
        paths = ConfigPaths()
    limit = max(1, int(max_results))
    backend = get_link_graph_backend(notebook_dir=str(paths.project_root))
    policy_config = resolve_link_graph_policy_config(mode="hybrid")
    plan = await plan_link_graph_retrieval(
        query,
        limit=limit,
        mode=policy_config.mode,
        backend=backend,
        config=policy_config,
    )

    graph_results = link_graph_hits_to_hybrid_results(
        plan.graph_hits,
        source="graph_search",
        reasoning=f"LinkGraph policy: {plan.reason}",
    )
    vector_results: list[dict[str, Any]] = []
    if use_hybrid and plan.selected_mode == "vector_only":
        try:
            vector_results = await _run_vector_fallback(query, limit=limit, paths=paths)
        except Exception as exc:
            logger.warning("Hybrid vector fallback failed: %s", exc)

    merged_all = merge_hybrid_results(graph_results, vector_results)
    graph_stats_payload = await get_link_graph_stats_for_response(
        backend,
        fallback={},
        include_meta=True,
    )
    graph_stats, graph_stats_meta = _split_graph_stats_payload(graph_stats_payload)

    return {
        "success": True,
        "query": query,
        "link_graph_results": graph_results[:limit],
        "link_graph_total": len(graph_results),
        "vector_total": len(vector_results),
        "merged": merged_all[:limit],
        "merged_total": len(merged_all),
        "graph_stats": graph_stats,
        "graph_stats_meta": graph_stats_meta,
        "policy": {
            "requested_mode": plan.requested_mode,
            "selected_mode": plan.selected_mode,
            "reason": plan.reason,
            "backend": plan.backend_name,
            "graph_confidence_score": plan.graph_confidence_score,
            "graph_confidence_level": plan.graph_confidence_level,
        },
    }


__all__ = ["run_hybrid_search"]
