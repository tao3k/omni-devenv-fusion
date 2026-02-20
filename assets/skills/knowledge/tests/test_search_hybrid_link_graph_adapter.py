"""Unit tests for search.hybrid adapter routed by LinkGraph policy."""

from __future__ import annotations

import types

import pytest
from search import hybrid as hybrid_mode


class _FakeBackend:
    async def stats(self) -> dict[str, int]:
        return {"total_notes": 2, "orphans": 0, "links_in_graph": 1, "nodes_in_graph": 2}


def _make_plan(selected_mode: str, reason: str, hits: list[types.SimpleNamespace]):
    return types.SimpleNamespace(
        requested_mode="hybrid",
        selected_mode=selected_mode,
        reason=reason,
        backend_name="link_graph",
        graph_hits=hits,
        graph_confidence_score=0.72,
        graph_confidence_level="high",
    )


@pytest.mark.asyncio
async def test_run_hybrid_search_graph_only_skips_vector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def _fake_plan(*args, **kwargs):
        del args, kwargs
        return _make_plan(
            "graph_only",
            "graph_sufficient",
            [types.SimpleNamespace(stem="a", title="Doc A", path="docs/a.md", score=0.9)],
        )

    async def _fail_vector(*args, **kwargs):
        raise AssertionError("vector fallback should not be called")

    monkeypatch.setattr(
        hybrid_mode, "get_link_graph_backend", lambda notebook_dir=None: _FakeBackend()
    )
    monkeypatch.setattr(
        hybrid_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    monkeypatch.setattr(
        hybrid_mode,
        "resolve_link_graph_policy_config",
        lambda mode=None: types.SimpleNamespace(mode="hybrid"),
    )
    monkeypatch.setattr(hybrid_mode, "plan_link_graph_retrieval", _fake_plan)
    monkeypatch.setattr(hybrid_mode, "run_vector_search", _fail_vector)

    out = await hybrid_mode.run_hybrid_search(
        "architecture",
        max_results=3,
        use_hybrid=True,
        paths=types.SimpleNamespace(project_root=tmp_path),
    )

    assert out["success"] is True
    assert out["policy"]["selected_mode"] == "graph_only"
    assert out["vector_total"] == 0
    assert out["merged_total"] == 1
    assert out["graph_stats_meta"] == {}
    assert out["merged"][0]["source"] == "graph_search"


@pytest.mark.asyncio
async def test_run_hybrid_search_vector_fallback_merges_overlap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def _fake_plan(*args, **kwargs):
        del args, kwargs
        return _make_plan(
            "vector_only",
            "graph_insufficient",
            [types.SimpleNamespace(stem="a", title="Doc A", path="docs/a.md", score=0.2)],
        )

    async def _fake_vector(*args, **kwargs):
        del args, kwargs
        return {
            "success": True,
            "results": [
                {"source": "docs/a.md", "title": "Doc A", "score": 0.88, "content": "A content"},
                {"source": "docs/b.md", "title": "Doc B", "score": 0.76, "content": "B content"},
            ],
        }

    monkeypatch.setattr(
        hybrid_mode, "get_link_graph_backend", lambda notebook_dir=None: _FakeBackend()
    )
    monkeypatch.setattr(
        hybrid_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    monkeypatch.setattr(
        hybrid_mode,
        "resolve_link_graph_policy_config",
        lambda mode=None: types.SimpleNamespace(mode="hybrid"),
    )
    monkeypatch.setattr(hybrid_mode, "plan_link_graph_retrieval", _fake_plan)
    monkeypatch.setattr(hybrid_mode, "run_vector_search", _fake_vector)

    out = await hybrid_mode.run_hybrid_search(
        "architecture",
        max_results=5,
        use_hybrid=True,
        paths=types.SimpleNamespace(project_root=tmp_path),
    )

    assert out["success"] is True
    assert out["policy"]["selected_mode"] == "vector_only"
    assert out["link_graph_total"] == 1
    assert out["vector_total"] == 2
    assert out["merged_total"] == 2
    assert out["graph_stats_meta"] == {}
    assert out["merged"][0]["source"] == "hybrid"
