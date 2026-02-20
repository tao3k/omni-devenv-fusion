"""Tests for LinkGraph recall policy orchestration helper."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import omni.rag.link_graph.recall_policy as recall_policy
from omni.rag.link_graph.models import LinkGraphHit
from omni.rag.link_graph.policy import LinkGraphSourceHint


def _policy_config(mode: str = "hybrid") -> SimpleNamespace:
    return SimpleNamespace(mode=mode, graph_rows_per_source=4)


def _plan(
    *,
    requested_mode: str,
    selected_mode: str,
    reason: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        reason=reason,
        backend_name="fake",
        graph_hits=[LinkGraphHit(stem="a", score=0.88, path="docs/a.md")],
        source_hints=[LinkGraphSourceHint(source_filter="a.md", stem="a", graph_score=0.88)],
        graph_confidence_score=0.88,
        graph_confidence_level="high",
    )


@pytest.mark.asyncio
async def test_evaluate_link_graph_recall_policy_returns_graph_rows(
    monkeypatch: pytest.MonkeyPatch,
):
    """Graph-only selected with fetched rows should return graph path + rows."""
    monkeypatch.setattr(
        recall_policy,
        "resolve_link_graph_policy_config",
        lambda mode=None: _policy_config(mode or "hybrid"),
    )

    async def _fake_plan(*_args, **_kwargs):
        return _plan(
            requested_mode="hybrid",
            selected_mode="graph_only",
            reason="graph_sufficient",
        )

    monkeypatch.setattr(
        recall_policy,
        "plan_link_graph_retrieval",
        _fake_plan,
    )
    monkeypatch.setattr(
        recall_policy,
        "serialize_link_graph_retrieval_plan",
        lambda _plan_obj: {"schema": "omni.link_graph.retrieval_plan.v1"},
    )
    monkeypatch.setattr(
        recall_policy,
        "get_link_graph_retrieval_plan_schema_id",
        lambda: "https://schemas.omni.dev/omni.link_graph.retrieval_plan.v1.schema.json",
    )

    async def _fake_fetch(**_kwargs):
        return [
            {
                "content": "graph row",
                "source": "docs/a.md",
                "score": 0.91,
                "title": "A",
                "section": "",
            }
        ]

    monkeypatch.setattr(recall_policy, "fetch_graph_rows_by_policy", _fake_fetch)

    decision = await recall_policy.evaluate_link_graph_recall_policy(
        query="architecture",
        limit=3,
        retrieval_mode="hybrid",
        store=object(),
        collection="knowledge_chunks",
    )

    assert decision.retrieval_path == "graph_only"
    assert decision.retrieval_reason == "graph_sufficient"
    assert decision.graph_only_empty is False
    assert len(decision.graph_rows) == 1
    assert decision.retrieval_plan_schema_id.endswith(
        "/omni.link_graph.retrieval_plan.v1.schema.json"
    )


@pytest.mark.asyncio
async def test_evaluate_link_graph_recall_policy_marks_graph_only_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    """Requested graph_only with no rows should return graph_only_empty."""
    monkeypatch.setattr(
        recall_policy,
        "resolve_link_graph_policy_config",
        lambda mode=None: _policy_config(mode or "graph_only"),
    )

    async def _fake_plan(*_args, **_kwargs):
        return _plan(
            requested_mode="graph_only",
            selected_mode="graph_only",
            reason="graph_only_requested_empty",
        )

    monkeypatch.setattr(
        recall_policy,
        "plan_link_graph_retrieval",
        _fake_plan,
    )
    monkeypatch.setattr(
        recall_policy, "serialize_link_graph_retrieval_plan", lambda _plan_obj: None
    )
    monkeypatch.setattr(recall_policy, "get_link_graph_retrieval_plan_schema_id", lambda: "")

    async def _fake_fetch(**_kwargs):
        return []

    monkeypatch.setattr(recall_policy, "fetch_graph_rows_by_policy", _fake_fetch)

    decision = await recall_policy.evaluate_link_graph_recall_policy(
        query="missing",
        limit=3,
        retrieval_mode="graph_only",
        store=object(),
        collection="knowledge_chunks",
    )

    assert decision.retrieval_path == "graph_only"
    assert decision.retrieval_reason == "graph_only_empty"
    assert decision.graph_only_empty is True
    assert decision.graph_rows == ()


@pytest.mark.asyncio
async def test_evaluate_link_graph_recall_policy_falls_back_to_vector_when_graph_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    """Graph-selected but empty rows should become vector fallback with plan override."""
    monkeypatch.setattr(
        recall_policy,
        "resolve_link_graph_policy_config",
        lambda mode=None: _policy_config(mode or "hybrid"),
    )

    async def _fake_plan(*_args, **_kwargs):
        return _plan(
            requested_mode="hybrid",
            selected_mode="graph_only",
            reason="graph_sufficient",
        )

    monkeypatch.setattr(
        recall_policy,
        "plan_link_graph_retrieval",
        _fake_plan,
    )
    monkeypatch.setattr(
        recall_policy,
        "serialize_link_graph_retrieval_plan",
        lambda _plan_obj: {
            "schema": "omni.link_graph.retrieval_plan.v1",
            "selected_mode": "graph_only",
            "reason": "graph_sufficient",
        },
    )
    monkeypatch.setattr(recall_policy, "get_link_graph_retrieval_plan_schema_id", lambda: "schema")

    async def _fake_fetch(**_kwargs):
        return []

    monkeypatch.setattr(recall_policy, "fetch_graph_rows_by_policy", _fake_fetch)

    decision = await recall_policy.evaluate_link_graph_recall_policy(
        query="architecture",
        limit=3,
        retrieval_mode="hybrid",
        store=object(),
        collection="knowledge_chunks",
    )

    assert decision.retrieval_path == "vector_only"
    assert decision.retrieval_reason == "graph_empty_fallback_vector"
    assert decision.retrieval_plan is not None
    assert decision.retrieval_plan.get("selected_mode") == "vector_only"
    assert decision.retrieval_plan.get("reason") == "graph_empty_fallback_vector"


@pytest.mark.asyncio
async def test_evaluate_link_graph_recall_policy_handles_exceptions(
    monkeypatch: pytest.MonkeyPatch,
):
    """Policy errors should degrade to vector-only without raising."""

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(recall_policy, "resolve_link_graph_policy_config", _boom)

    decision = await recall_policy.evaluate_link_graph_recall_policy(
        query="x",
        limit=1,
        retrieval_mode="hybrid",
        store=object(),
        collection="knowledge_chunks",
    )
    assert decision.retrieval_path == "vector_only"
    assert decision.retrieval_reason == "policy_error_fallback_vector"
