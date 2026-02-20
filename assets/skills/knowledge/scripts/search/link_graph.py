"""LinkGraph-only search (link reasoning, no vector)."""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from omni.rag.link_graph import (
    get_link_graph_backend,
    get_link_graph_stats_for_response,
    link_graph_hits_to_search_results,
)
from omni.rag.link_graph.models import LinkGraphSearchOptions

logger = get_logger("skill.knowledge.search.link_graph")


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


def _get_backend(paths: ConfigPaths | None = None):
    if paths is None:
        paths = ConfigPaths()
    return get_link_graph_backend(notebook_dir=str(paths.project_root))


async def run_link_graph_search(
    query: str,
    max_results: int = 10,
    search_options: LinkGraphSearchOptions | dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Run LinkGraph-only search; returns success, query, total, results, graph_stats."""
    options_model = (
        search_options
        if isinstance(search_options, LinkGraphSearchOptions)
        else LinkGraphSearchOptions.from_dict(search_options or {})
    )
    options_record = options_model.to_record()
    normalized_options = {k: v for k, v in options_record.items() if k != "schema"}

    backend = _get_backend(paths)
    bounded_results = max(1, int(max_results))
    planned = await backend.search_planned(
        query,
        limit=bounded_results,
        options=normalized_options,
    )
    if not isinstance(planned, dict):
        raise RuntimeError("link_graph search_planned contract violation: expected object payload")

    planned_query_raw = planned.get("query")
    parsed_query = str(planned_query_raw).strip() if planned_query_raw is not None else str(query)

    planned_options = planned.get("search_options")
    if not isinstance(planned_options, dict):
        raise RuntimeError(
            "link_graph search_planned contract violation: expected `search_options` object"
        )
    effective_options: dict[str, Any] = planned_options

    planned_hits = planned.get("hits")
    if not isinstance(planned_hits, list):
        raise RuntimeError("link_graph search_planned contract violation: expected `hits` list")
    graph_results = planned_hits

    results = link_graph_hits_to_search_results(
        graph_results,
        source="graph_search",
        reasoning="LinkGraph search hit",
    )
    graph_stats_payload = await get_link_graph_stats_for_response(
        backend,
        fallback={},
        include_meta=True,
    )
    graph_stats, graph_stats_meta = _split_graph_stats_payload(graph_stats_payload)
    return {
        "success": True,
        "query": query,
        "parsed_query": parsed_query,
        "search_options": effective_options,
        "total": len(results),
        "results": results,
        "graph_stats": graph_stats,
        "graph_stats_meta": graph_stats_meta,
    }


__all__ = ["run_link_graph_search"]
