"""Unit tests for search.link_graph adapter backed by LinkGraph API."""

from __future__ import annotations

import types

import pytest
from search import link_graph as link_graph_mode


class _FakeBackend:
    async def search_planned(self, query: str, limit: int = 20, options=None):
        assert query == "architecture"
        assert limit == 3
        assert options == {
            "match_strategy": "fts",
            "case_sensitive": False,
            "sort_terms": [{"field": "score", "order": "desc"}],
            "filters": {},
        }
        return {
            "query": "architecture",
            "search_options": options,
            "hits": [
                types.SimpleNamespace(stem="n-1", title="Note 1", path="docs/n-1.md", score=0.9),
                types.SimpleNamespace(stem="n-2", title="Note 2", path="docs/n-2.md", score=0.7),
            ],
        }

    async def stats(self) -> dict[str, int]:
        return {"total_notes": 2, "orphans": 0, "links_in_graph": 1, "nodes_in_graph": 2}


@pytest.mark.asyncio
async def test_run_link_graph_search_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    monkeypatch.setattr(
        link_graph_mode, "get_link_graph_backend", lambda notebook_dir=None: _FakeBackend()
    )
    monkeypatch.setattr(
        link_graph_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = await link_graph_mode.run_link_graph_search("architecture", max_results=3, paths=paths)

    assert out["success"] is True
    assert out["query"] == "architecture"
    assert out["parsed_query"] == "architecture"
    assert out["search_options"]["match_strategy"] == "fts"
    assert out["search_options"]["case_sensitive"] is False
    assert out["search_options"]["sort_terms"] == [{"field": "score", "order": "desc"}]
    assert out["search_options"]["filters"] == {}
    assert out["total"] == 2
    assert out["graph_stats"]["total_notes"] == 2
    assert out["graph_stats_meta"] == {}
    assert out["results"][0]["id"] == "n-1"
    assert out["results"][0]["source"] == "graph_search"


@pytest.mark.asyncio
async def test_run_link_graph_search_forwards_custom_search_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    calls: list[dict] = []

    class _Backend:
        async def search_planned(self, query: str, limit: int = 20, options=None):
            del query, limit
            calls.append(options or {})
            return {
                "query": "architecture",
                "search_options": options or {},
                "hits": [
                    types.SimpleNamespace(stem="n-1", title="Note 1", path="docs/n-1.md", score=1.0)
                ],
            }

        async def stats(self) -> dict[str, int]:
            return {"total_notes": 1, "orphans": 0, "links_in_graph": 0, "nodes_in_graph": 1}

    monkeypatch.setattr(
        link_graph_mode, "get_link_graph_backend", lambda notebook_dir=None: _Backend()
    )
    monkeypatch.setattr(
        link_graph_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = await link_graph_mode.run_link_graph_search(
        "architecture",
        max_results=3,
        search_options={
            "match_strategy": "exact",
            "case_sensitive": True,
            "sort_terms": [{"field": "title", "order": "asc"}],
            "filters": {
                "link_to": {"seeds": ["a"]},
                "linked_by": {"seeds": ["b"]},
                "related": {"seeds": ["c"], "max_distance": 3},
            },
            "created_after": 1_700_000_000,
            "created_before": 1_800_000_000,
            "modified_after": 1_710_000_000,
            "modified_before": 1_810_000_000,
        },
        paths=paths,
    )

    assert out["search_options"] == {
        "match_strategy": "exact",
        "case_sensitive": True,
        "sort_terms": [{"field": "title", "order": "asc"}],
        "filters": {
            "link_to": {"seeds": ["a"]},
            "linked_by": {"seeds": ["b"]},
            "related": {"seeds": ["c"], "max_distance": 3},
        },
        "created_after": 1_700_000_000,
        "created_before": 1_800_000_000,
        "modified_after": 1_710_000_000,
        "modified_before": 1_810_000_000,
    }
    assert calls == [
        {
            "match_strategy": "exact",
            "case_sensitive": True,
            "sort_terms": [{"field": "title", "order": "asc"}],
            "filters": {
                "link_to": {"seeds": ["a"]},
                "linked_by": {"seeds": ["b"]},
                "related": {"seeds": ["c"], "max_distance": 3},
            },
            "created_after": 1_700_000_000,
            "created_before": 1_800_000_000,
            "modified_after": 1_710_000_000,
            "modified_before": 1_810_000_000,
        }
    ]


@pytest.mark.asyncio
async def test_run_link_graph_search_prefers_planned_search_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    class _Backend:
        async def search_planned(self, query: str, limit: int = 20, options=None):
            assert query == "tag:(architecture OR design) -tag:draft sort:path_asc"
            assert limit == 3
            assert isinstance(options, dict)
            return {
                "query": "architecture design",
                "search_options": {
                    "match_strategy": "fts",
                    "case_sensitive": False,
                    "sort_terms": [{"field": "path", "order": "asc"}],
                    "filters": {"tags": {"any": ["architecture", "design"], "not": ["draft"]}},
                },
                "hits": [
                    types.SimpleNamespace(
                        stem="n-1",
                        title="Architecture Note",
                        path="docs/n-1.md",
                        score=0.88,
                    )
                ],
            }

        async def stats(self) -> dict[str, int]:
            return {"total_notes": 1, "orphans": 0, "links_in_graph": 0, "nodes_in_graph": 1}

    monkeypatch.setattr(
        link_graph_mode, "get_link_graph_backend", lambda notebook_dir=None: _Backend()
    )
    monkeypatch.setattr(
        link_graph_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = await link_graph_mode.run_link_graph_search(
        "tag:(architecture OR design) -tag:draft sort:path_asc",
        max_results=3,
        paths=paths,
    )

    assert out["success"] is True
    assert out["query"] == "tag:(architecture OR design) -tag:draft sort:path_asc"
    assert out["parsed_query"] == "architecture design"
    assert out["search_options"] == {
        "match_strategy": "fts",
        "case_sensitive": False,
        "sort_terms": [{"field": "path", "order": "asc"}],
        "filters": {"tags": {"any": ["architecture", "design"], "not": ["draft"]}},
    }
    assert out["total"] == 1
    assert out["results"][0]["id"] == "n-1"


@pytest.mark.asyncio
async def test_run_link_graph_search_rejects_legacy_flat_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    class _Backend:
        async def search_planned(self, query: str, limit: int = 20, options=None):
            del query, limit, options
            return {"query": "", "search_options": {}, "hits": []}

        async def stats(self) -> dict[str, int]:
            return {"total_notes": 0, "orphans": 0, "links_in_graph": 0, "nodes_in_graph": 0}

    monkeypatch.setattr(
        link_graph_mode, "get_link_graph_backend", lambda notebook_dir=None: _Backend()
    )
    monkeypatch.setattr(
        link_graph_mode,
        "get_link_graph_stats_for_response",
        lambda backend, **kwargs: backend.stats(),
    )
    paths = types.SimpleNamespace(project_root=tmp_path)

    with pytest.raises(ValueError, match="unknown fields: sort"):
        await link_graph_mode.run_link_graph_search(
            "architecture",
            max_results=3,
            search_options={"sort": "score_desc"},
            paths=paths,
        )
