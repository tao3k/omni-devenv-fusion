"""Common response builders for knowledge retrieval skill payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from omni.foundation.api.response_payloads import (
    build_status_error_response,
    build_status_message_response,
)


def build_recall_search_response(
    *,
    query: str,
    keywords: list[str] | None,
    collection: str,
    preview: bool,
    retrieval_mode: str,
    retrieval_path: str,
    retrieval_reason: str,
    graph_backend: str,
    graph_hit_count: int,
    graph_confidence_score: float,
    graph_confidence_level: str,
    retrieval_plan_schema_id: str | None = None,
    retrieval_plan: dict[str, Any] | None = None,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build normalized recall success payload."""
    rows = list(results or [])
    return {
        "query": query,
        "keywords": list(keywords or []),
        "collection": collection,
        "found": len(rows),
        "status": "success",
        "preview": bool(preview),
        "retrieval_mode": retrieval_mode,
        "retrieval_path": retrieval_path,
        "retrieval_reason": retrieval_reason,
        "graph_backend": graph_backend,
        "graph_hit_count": int(graph_hit_count),
        "graph_confidence_score": float(graph_confidence_score),
        "graph_confidence_level": graph_confidence_level,
        "retrieval_plan_schema_id": retrieval_plan_schema_id or None,
        "retrieval_plan": retrieval_plan,
        "results": rows,
    }


def build_recall_error_response(
    *,
    query: str,
    error: str,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build normalized recall error payload."""
    return {
        "query": query,
        "status": "error",
        "error": str(error),
        "results": list(results or []),
    }


def build_recall_chunked_response(
    *,
    query: str,
    status: str,
    error: str | None = None,
    preview_results: list[dict[str, Any]] | None = None,
    batches: list[list[dict[str, Any]]] | None = None,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build normalized chunked recall payload for one-shot workflow results."""
    rows = list(results or [])
    return {
        "query": query,
        "status": status,
        "error": str(error) if error is not None else None,
        "preview_results": list(preview_results or []),
        "batches": list(batches or []),
        "all_chunks_count": len(rows),
        "results": rows,
    }


def extract_graph_confidence(
    retrieval_plan: Mapping[str, Any] | None,
    *,
    default_score: float = 0.0,
    default_level: str = "none",
) -> tuple[float, str]:
    """Extract graph confidence score + level from serialized retrieval plan."""
    if not isinstance(retrieval_plan, Mapping):
        return float(default_score), str(default_level)
    score = float(retrieval_plan.get("graph_confidence_score", default_score) or default_score)
    level = str(retrieval_plan.get("graph_confidence_level", default_level) or default_level)
    return score, level


def override_retrieval_plan_mode(
    retrieval_plan: dict[str, Any] | None,
    *,
    selected_mode: str,
    reason: str,
) -> dict[str, Any] | None:
    """Return a copied retrieval plan with selected_mode/reason overridden."""
    if not isinstance(retrieval_plan, dict):
        return None
    updated = dict(retrieval_plan)
    updated["selected_mode"] = selected_mode
    updated["reason"] = reason
    return updated


__all__ = [
    "build_recall_chunked_response",
    "build_recall_error_response",
    "build_recall_search_response",
    "build_status_error_response",
    "build_status_message_response",
    "extract_graph_confidence",
    "override_retrieval_plan_mode",
]
