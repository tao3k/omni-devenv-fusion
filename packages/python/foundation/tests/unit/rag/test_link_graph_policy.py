"""Tests for LinkGraph retrieval policy routing."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import omni.rag.link_graph.policy as link_graph_policy
from omni.rag.link_graph.models import LinkGraphHit
from omni.rag.link_graph.policy import (
    LinkGraphPolicyConfig,
    LinkGraphSourceHint,
    fetch_graph_rows_by_policy,
    get_link_graph_retrieval_plan_schema_id,
    plan_link_graph_retrieval,
    serialize_link_graph_retrieval_plan,
)


class _FakeBackend:
    def __init__(self, hits: list[LinkGraphHit]) -> None:
        self.backend_name = "fake"
        self._hits = hits
        self.calls: list[tuple[str, int, str]] = []

    async def search_planned(self, query: str, limit: int = 20, options=None) -> dict[str, object]:
        strategy = str(getattr(options, "match_strategy", "none"))
        self.calls.append((query, limit, strategy))
        return {
            "query": query,
            "search_options": {"match_strategy": strategy},
            "hits": list(self._hits),
        }


class _SlowBackend:
    def __init__(self, *, backend_name: str = "wendao") -> None:
        self.backend_name = backend_name
        self.calls: list[tuple[str, int, str]] = []

    async def search_planned(self, query: str, limit: int = 20, options=None) -> dict[str, object]:
        strategy = str(getattr(options, "match_strategy", "none"))
        self.calls.append((query, limit, strategy))
        await asyncio.sleep(0.2)
        return {
            "query": query,
            "search_options": {"match_strategy": strategy},
            "hits": [LinkGraphHit(stem="slow", score=0.9, path="docs/slow.md")],
        }


class _FakeStore:
    def __init__(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, str]] = []

    async def list_all(
        self, collection: str, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append((collection, str(source_filter or "")))
        return list(self._rows.get(str(source_filter or ""), []))


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_hybrid_prefers_graph_when_sufficient() -> None:
    backend = _FakeBackend(
        [
            LinkGraphHit(stem="a", score=0.9, path="docs/a.md"),
            LinkGraphHit(stem="b", score=0.7, path="docs/b.md"),
        ]
    )
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=3,
        max_sources=4,
        min_graph_hits=2,
        min_graph_score=0.5,
    )

    plan = await plan_link_graph_retrieval(
        "retrieval policy",
        limit=3,
        backend=backend,
        config=config,
    )

    assert plan.requested_mode == "hybrid"
    assert plan.selected_mode == "graph_only"
    assert plan.reason == "graph_sufficient"
    assert len(plan.source_hints) > 0
    assert plan.graph_confidence_score > 0.0
    assert plan.graph_confidence_level in {"low", "medium", "high"}
    assert plan.budget.candidate_limit == 9
    assert plan.budget.max_sources == 4
    assert plan.budget.rows_per_source == 8
    assert plan.to_record()["schema"] == "omni.link_graph.retrieval_plan.v1"
    assert backend.calls[0] == ("retrieval policy", 9, "fts")


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_hybrid_falls_back_vector_when_insufficient() -> None:
    backend = _FakeBackend([LinkGraphHit(stem="a", score=0.1, path="docs/a.md")])
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=2,
        max_sources=4,
        min_graph_hits=2,
        min_graph_score=0.4,
    )

    plan = await plan_link_graph_retrieval("short", limit=5, backend=backend, config=config)
    assert plan.selected_mode == "vector_only"
    assert plan.reason == "graph_insufficient"
    assert len(plan.graph_hits) == 1
    assert plan.graph_confidence_level in {"low", "medium"}
    assert plan.budget.candidate_limit == 10


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_graph_only_keeps_mode_when_empty() -> None:
    backend = _FakeBackend([])
    config = LinkGraphPolicyConfig(mode="graph_only", max_sources=3)
    plan = await plan_link_graph_retrieval("missing", limit=2, backend=backend, config=config)
    assert plan.requested_mode == "graph_only"
    assert plan.selected_mode == "graph_only"
    assert plan.reason == "graph_only_requested_empty"
    assert plan.graph_confidence_level == "none"
    assert plan.graph_confidence_score == 0.0


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_hybrid_timeout_falls_back_to_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _SlowBackend(backend_name="wendao")
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=2,
        max_sources=4,
        min_graph_hits=1,
        min_graph_score=0.1,
    )
    link_graph_policy._PLAN_CACHE.clear()

    def _fake_get_setting(key: str, default=None):
        if key == "link_graph.policy.search_timeout_seconds":
            return 0.01
        return default

    monkeypatch.setattr(link_graph_policy, "get_setting", _fake_get_setting)
    plan = await plan_link_graph_retrieval("slow query", limit=2, backend=backend, config=config)

    assert plan.selected_mode == "vector_only"
    assert plan.reason == "graph_search_timeout"
    assert len(plan.graph_hits) == 0
    assert backend.calls == [("slow query", 4, "fts")]
    assert link_graph_policy.take_recent_graph_search_timeout("slow query") is True
    assert link_graph_policy.take_recent_graph_search_timeout("slow query") is False
    link_graph_policy._PLAN_CACHE.clear()


def test_policy_search_timeout_adapts_for_machine_like_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get_setting(key: str, default=None):
        return default

    monkeypatch.setattr(link_graph_policy, "get_setting", _fake_get_setting)
    timeout_machine, bucket_machine = link_graph_policy._policy_search_timeout_seconds(
        "wendao",
        "skip-proximity-after-timeout-1771471189-22808",
    )
    timeout_natural, bucket_natural = link_graph_policy._policy_search_timeout_seconds(
        "wendao",
        "How to optimize link graph recall timeout behavior for markdown notes?",
    )
    assert bucket_machine == "machine_like"
    assert bucket_natural in {"normal", "long_natural"}
    assert timeout_machine < timeout_natural


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_machine_like_query_uses_exact_strategy() -> None:
    link_graph_policy._PLAN_CACHE.clear()
    backend = _FakeBackend([LinkGraphHit(stem="a", score=0.9, path="docs/a.md")])
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=2,
        max_sources=4,
        min_graph_hits=1,
        min_graph_score=0.1,
    )

    await plan_link_graph_retrieval(
        "skip-proximity-after-timeout-1771471189-22808",
        limit=3,
        backend=backend,
        config=config,
    )

    assert backend.calls
    assert backend.calls[0][2] == "exact"
    link_graph_policy._PLAN_CACHE.clear()


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_path_like_query_uses_path_fuzzy_strategy() -> None:
    link_graph_policy._PLAN_CACHE.clear()
    backend = _FakeBackend([LinkGraphHit(stem="a", score=0.9, path="docs/a.md")])
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=2,
        max_sources=4,
        min_graph_hits=1,
        min_graph_score=0.1,
    )

    await plan_link_graph_retrieval(
        "docs/architecture/graph.md",
        limit=3,
        backend=backend,
        config=config,
    )

    assert backend.calls
    assert backend.calls[0][2] == "path_fuzzy"
    link_graph_policy._PLAN_CACHE.clear()


@pytest.mark.asyncio
async def test_plan_link_graph_retrieval_reuses_cache_for_same_query() -> None:
    link_graph_policy._PLAN_CACHE.clear()
    backend = _FakeBackend([LinkGraphHit(stem="a", score=0.9, path="docs/a.md")])
    config = LinkGraphPolicyConfig(
        mode="hybrid",
        candidate_multiplier=2,
        max_sources=4,
        min_graph_hits=1,
        min_graph_score=0.1,
    )

    first = await plan_link_graph_retrieval("cache-query", limit=3, backend=backend, config=config)
    second = await plan_link_graph_retrieval("cache-query", limit=3, backend=backend, config=config)

    assert first == second
    assert len(backend.calls) == 1
    link_graph_policy._PLAN_CACHE.clear()


@pytest.mark.asyncio
async def test_fetch_graph_rows_by_policy_respects_source_hints_and_limits() -> None:
    store = _FakeStore(
        {
            "a.md": [
                {
                    "id": "row-a-0",
                    "content": "alpha 0",
                    "metadata": {"source": "docs/a.md", "chunk_index": 0, "title": "A"},
                },
                {
                    "id": "row-a-1",
                    "content": "alpha 1",
                    "metadata": {"source": "docs/a.md", "chunk_index": 1, "title": "A"},
                },
            ],
            "b.md": [
                {
                    "id": "row-b-0",
                    "content": "beta 0",
                    "metadata": {"source": "docs/b.md", "chunk_index": 0, "title": "B"},
                }
            ],
        }
    )
    hints = [
        LinkGraphSourceHint(source_filter="a.md", stem="a", graph_score=0.9),
        LinkGraphSourceHint(source_filter="b.md", stem="b", graph_score=0.8),
    ]

    rows = await fetch_graph_rows_by_policy(
        store=store,
        collection="knowledge_chunks",
        source_hints=hints,
        limit=2,
        rows_per_source=1,
    )

    assert [row["source"] for row in rows] == ["docs/a.md", "docs/b.md"]
    assert rows[0]["score"] >= rows[1]["score"]
    assert len(store.calls) == 2


@pytest.mark.asyncio
async def test_fetch_graph_rows_by_policy_emits_retrieval_row_budget_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, dict[str, Any]]] = []

    def _capture(phase: str, _duration_ms: float, **extra: Any) -> None:
        recorded.append((phase, dict(extra)))

    monkeypatch.setattr(link_graph_policy, "_record_phase", _capture)

    store = _FakeStore(
        {
            "a.md": [
                {
                    "id": "row-a-0",
                    "content": "alpha 0",
                    "metadata": {"source": "docs/a.md", "chunk_index": 0, "title": "A"},
                },
                {
                    "id": "row-a-1",
                    "content": "alpha 1",
                    "metadata": {"source": "docs/a.md", "chunk_index": 1, "title": "A"},
                },
            ],
        }
    )
    hints = [LinkGraphSourceHint(source_filter="a.md", stem="a", graph_score=0.9)]

    rows = await fetch_graph_rows_by_policy(
        store=store,
        collection="knowledge_chunks",
        source_hints=hints,
        limit=2,
        rows_per_source=2,
    )

    retrieval_events = [extra for phase, extra in recorded if phase == "retrieval.rows.graph"]
    assert len(retrieval_events) == 1
    event = retrieval_events[0]
    assert event["mode"] == "graph"
    assert event["collection"] == "knowledge_chunks"
    assert event["fetch_limit"] == 2
    assert event["rows_fetched"] == 2
    assert event["rows_parsed"] == 2
    assert event["rows_returned"] == len(rows) == 2
    assert event["rows_capped"] == 0
    assert event["source_hint_count"] == 1
    assert event["rows_per_source"] == 2
    assert event["total_cap"] == 8


@pytest.mark.asyncio
async def test_fetch_graph_rows_by_policy_emits_zero_budget_when_hints_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, dict[str, Any]]] = []

    def _capture(phase: str, _duration_ms: float, **extra: Any) -> None:
        recorded.append((phase, dict(extra)))

    monkeypatch.setattr(link_graph_policy, "_record_phase", _capture)

    rows = await fetch_graph_rows_by_policy(
        store=object(),
        collection="knowledge_chunks",
        source_hints=[],
        limit=3,
        rows_per_source=4,
    )
    assert rows == []

    retrieval_events = [extra for phase, extra in recorded if phase == "retrieval.rows.graph"]
    assert len(retrieval_events) == 1
    event = retrieval_events[0]
    assert event["mode"] == "graph"
    assert event["fetch_limit"] == 3
    assert event["rows_fetched"] == 0
    assert event["rows_parsed"] == 0
    assert event["rows_returned"] == 0
    assert event["rows_capped"] == 0
    assert event["source_hint_count"] == 0
    assert event["rows_per_source"] == 4
    assert event["total_cap"] == 12


def test_serialize_link_graph_retrieval_plan_supports_plain_objects() -> None:
    plan = type(
        "PlanObj",
        (),
        {
            "requested_mode": "hybrid",
            "selected_mode": "vector_only",
            "reason": "graph_insufficient",
            "backend_name": "fake",
            "graph_hits": [],
            "source_hints": [],
            "graph_confidence_score": 0.2,
            "graph_confidence_level": "low",
            "budget": type(
                "BudgetObj",
                (),
                {"candidate_limit": 10, "max_sources": 3, "rows_per_source": 8},
            )(),
        },
    )()
    payload = serialize_link_graph_retrieval_plan(plan)
    assert payload is not None
    assert payload["schema"] == "omni.link_graph.retrieval_plan.v1"
    assert payload["selected_mode"] == "vector_only"


def test_get_link_graph_retrieval_plan_schema_id() -> None:
    schema_id = get_link_graph_retrieval_plan_schema_id()
    assert schema_id.endswith("/omni.link_graph.retrieval_plan.v1.schema.json")
