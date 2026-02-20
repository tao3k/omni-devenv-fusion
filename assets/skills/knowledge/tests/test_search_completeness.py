"""
Completeness verification for unified knowledge search.

Contract: run_search(query, mode) returns a dict that always has "query",
and mode-specific keys so callers can handle results without branching on mode
by name. All async modes (hybrid, link_graph, vector) return "success": True.
"""

import pytest

# scripts/ on path via conftest
import search as search_module
from search import SEARCH_MODES, run_search, search_keyword


class TestSearchModesCompleteness:
    """Verify SEARCH_MODES and that each mode returns the expected shape."""

    def test_search_modes_defined(self):
        """All four modes are defined and ordered."""
        assert SEARCH_MODES == ("hybrid", "keyword", "link_graph", "vector")

    def test_keyword_returns_query_and_results(self):
        """mode=keyword returns query, count, results, scope (sync)."""
        out = search_keyword("test", scope="docs")
        assert "query" in out
        assert out["query"] == "test"
        assert "count" in out
        assert "results" in out
        assert "scope" in out

    @pytest.mark.asyncio
    async def test_hybrid_returns_success_query_merged(self):
        """mode=hybrid returns success, query, link_graph_total, merged."""
        out = await run_search("architecture", mode="hybrid", max_results=3)
        assert out.get("success") is True
        assert "query" in out
        assert "link_graph_total" in out
        assert "merged" in out
        assert "graph_stats_meta" in out
        assert isinstance(out["merged"], list)

    @pytest.mark.asyncio
    async def test_link_graph_returns_success_query_results(self, monkeypatch: pytest.MonkeyPatch):
        """mode=link_graph returns success, query, total, results."""

        async def _fake_link_graph_search(*args, **kwargs):
            query = str(args[0]) if args else str(kwargs.get("query", ""))
            return {
                "success": True,
                "query": query,
                "total": 0,
                "results": [],
                "graph_stats": {
                    "total_notes": 0,
                    "orphans": 0,
                    "links_in_graph": 0,
                    "nodes_in_graph": 0,
                },
                "graph_stats_meta": {},
            }

        monkeypatch.setattr(search_module, "run_link_graph_search", _fake_link_graph_search)
        out = await search_module.run_search("architecture", mode="link_graph", max_results=3)
        assert out.get("success") is True
        assert "query" in out
        assert "total" in out
        assert "results" in out
        assert "graph_stats_meta" in out
        assert isinstance(out["results"], list)

    @pytest.mark.asyncio
    async def test_vector_returns_success_query(self):
        """mode=vector returns success, query, and recall payload."""
        out = await run_search("architecture", mode="vector", max_results=3)
        assert out.get("success") is True
        assert "query" in out

    @pytest.mark.asyncio
    async def test_unknown_mode_falls_back_to_hybrid(self):
        """Unknown mode is treated as hybrid."""
        out = await run_search("test", mode="invalid_mode", max_results=2)
        assert out.get("success") is True
        assert "merged" in out
        assert "link_graph_total" in out
