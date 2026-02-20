"""Common LinkGraph policy orchestration for knowledge.recall."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .policy import (
    fetch_graph_rows_by_policy,
    get_link_graph_retrieval_plan_schema_id,
    plan_link_graph_retrieval,
    resolve_link_graph_policy_config,
    serialize_link_graph_retrieval_plan,
)


@dataclass(frozen=True, slots=True)
class LinkGraphRecallPolicyDecision:
    """Decision payload consumed by knowledge.recall."""

    retrieval_path: str = "vector_only"
    retrieval_reason: str = "vector_default"
    graph_backend: str = ""
    graph_hit_count: int = 0
    graph_confidence_score: float = 0.0
    graph_confidence_level: str = "none"
    retrieval_plan_schema_id: str = ""
    retrieval_plan: dict[str, Any] | None = None
    graph_rows: tuple[dict[str, Any], ...] = ()
    graph_only_empty: bool = False


def _override_retrieval_plan(
    payload: dict[str, Any] | None,
    *,
    selected_mode: str,
    reason: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    out = dict(payload)
    out["selected_mode"] = selected_mode
    out["reason"] = reason
    return out


def _base_decision(
    *,
    selected_mode: str,
    reason: str,
    backend_name: str,
    hit_count: int,
    confidence_score: Any,
    confidence_level: Any,
    plan_record: dict[str, Any] | None,
    schema_id: str,
) -> LinkGraphRecallPolicyDecision:
    return LinkGraphRecallPolicyDecision(
        retrieval_path=str(selected_mode or "vector_only"),
        retrieval_reason=str(reason or "vector_default"),
        graph_backend=str(backend_name or ""),
        graph_hit_count=max(0, int(hit_count)),
        graph_confidence_score=max(0.0, min(1.0, float(confidence_score or 0.0))),
        graph_confidence_level=str(confidence_level or "none"),
        retrieval_plan_schema_id=str(schema_id or ""),
        retrieval_plan=plan_record,
    )


async def evaluate_link_graph_recall_policy(
    *,
    query: str,
    limit: int,
    retrieval_mode: str,
    store: Any,
    collection: str = "knowledge_chunks",
) -> LinkGraphRecallPolicyDecision:
    """Evaluate policy + optional graph-row fetch for recall single-call path."""
    try:
        policy_config = resolve_link_graph_policy_config(mode=retrieval_mode)
        plan = await plan_link_graph_retrieval(
            query,
            limit=limit,
            mode=policy_config.mode,
            config=policy_config,
        )
        plan_record = serialize_link_graph_retrieval_plan(plan)
        schema_id = get_link_graph_retrieval_plan_schema_id() if plan_record else ""

        base = _base_decision(
            selected_mode=str(getattr(plan, "selected_mode", "vector_only")),
            reason=str(getattr(plan, "reason", "vector_default")),
            backend_name=str(getattr(plan, "backend_name", "")),
            hit_count=len(getattr(plan, "graph_hits", ()) or ()),
            confidence_score=getattr(plan, "graph_confidence_score", 0.0),
            confidence_level=getattr(plan, "graph_confidence_level", "none"),
            plan_record=plan_record,
            schema_id=schema_id,
        )

        if base.retrieval_path != "graph_only":
            return base

        graph_rows = await fetch_graph_rows_by_policy(
            store=store,
            collection=collection,
            source_hints=list(getattr(plan, "source_hints", ()) or ()),
            limit=limit,
            rows_per_source=policy_config.graph_rows_per_source,
        )
        if graph_rows:
            return replace(base, graph_rows=tuple(graph_rows))

        if str(getattr(plan, "requested_mode", "") or "") == "graph_only":
            return replace(
                base,
                retrieval_reason="graph_only_empty",
                graph_only_empty=True,
            )

        return replace(
            base,
            retrieval_path="vector_only",
            retrieval_reason="graph_empty_fallback_vector",
            retrieval_plan=_override_retrieval_plan(
                base.retrieval_plan,
                selected_mode="vector_only",
                reason="graph_empty_fallback_vector",
            ),
        )
    except Exception:
        return LinkGraphRecallPolicyDecision(
            retrieval_path="vector_only",
            retrieval_reason="policy_error_fallback_vector",
        )


__all__ = [
    "LinkGraphRecallPolicyDecision",
    "evaluate_link_graph_recall_policy",
]
