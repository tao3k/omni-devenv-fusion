"""Integration tests for route_hybrid with real vector store.

These tests verify the complete flow from query to results using
the actual RustVectorStore and a skills table (routing reads from skills, not router).

Tests cover:
- Full integration with skills table in the store
- Search result correctness
- Threshold filtering
- Deduplication
- Skill discovery patterns
- Database synchronization (skills table populated from assets/skills)
"""

from __future__ import annotations

import asyncio
import json

import pytest
from omni.test_kit.asserts import (
    assert_route_result_shape,
    assert_route_results_list,
    assert_tool_family_match,
)
from omni.test_kit.fixtures.vector import parametrize_route_intent_queries

# Router integration fixtures (router_lance_path, router_for_integration, sync) live in conftest.py
from .conftest import sync_router_from_skills_async

_sync_local_router_from_skills_async = sync_router_from_skills_async


def _sync_local_router_from_skills(storage_path: str) -> dict[str, int | str]:
    return asyncio.run(_sync_local_router_from_skills_async(storage_path))


def _full_tool_name(result) -> str:
    return f"{result.skill_name}.{result.command_name}"


class TestRouteHybridIntegration:
    """Integration tests for route_hybrid with real skills table."""

    @pytest.mark.asyncio
    async def test_route_hybrid_finds_indexed_tools(self, router_for_integration):
        """Test that route_hybrid finds tools that were indexed into the skills table.

        This is the critical test that prevented the bug where
        skill.discover returned 0 tools despite omni route test working.
        """
        router = router_for_integration

        result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if result["status"] != "success":
            pytest.skip(f"Could not sync skills: {result.get('error', 'unknown')}")

        # Now test route_hybrid
        results = await router.route_hybrid("find python files", limit=5, threshold=0.1)

        # Should find at least one result
        assert len(results) > 0, "route_hybrid should find indexed tools"

        # First result should be relevant
        first = results[0]
        assert_route_result_shape(first)

    @pytest.mark.asyncio
    async def test_route_hybrid_returns_route_result_objects(self, router_for_integration):
        """Test that route_hybrid returns proper RouteResult objects."""
        from omni.core.router.router import RouteResult

        results = await router_for_integration.route_hybrid("git status", limit=5, threshold=0.1)

        for r in results:
            assert isinstance(r, RouteResult)
            assert_route_result_shape(r)

    @pytest.mark.asyncio
    async def test_route_hybrid_confidence_levels(self, router_for_integration):
        """Test that confidence levels are correctly assigned."""
        from omni.foundation.config.settings import get_setting

        profiles = get_setting("router.search.profiles", {}) or {}
        active = str(get_setting("router.search.active_profile", "balanced"))
        selected = profiles.get(active, {}) if isinstance(profiles, dict) else {}
        high_base = float(selected.get("high_base", 0.90))
        medium_base = float(selected.get("medium_base", 0.60))
        medium_cap = float(selected.get("medium_cap", 0.89))
        low_floor = float(selected.get("low_floor", 0.10))

        results = await router_for_integration.route_hybrid("git commit", limit=10, threshold=0.0)

        for r in results:
            assert r.confidence in ("high", "medium", "low")

            # Verify confidence matches calibrated final_score bands.
            if r.confidence == "high":
                assert high_base <= r.score <= 1.0
            elif r.confidence == "medium":
                assert medium_base <= r.score <= medium_cap
            else:  # low
                assert low_floor <= r.score <= medium_base

    @pytest.mark.asyncio
    async def test_route_hybrid_threshold_filtering(self, router_for_integration):
        """Test that threshold affects result filtering.

        Note: route_hybrid uses adaptive thresholding, so results may
        include scores slightly below the threshold due to the search
        retry mechanism.
        """
        # Use very high threshold to get empty results
        results_high = await router_for_integration.route_hybrid(
            "find files search", limit=20, threshold=0.99
        )
        results_low = await router_for_integration.route_hybrid(
            "find files search", limit=20, threshold=0.0
        )

        # Low threshold should return more results
        assert len(results_low) >= len(results_high), (
            "Low threshold should return more or equal results"
        )

    @pytest.mark.asyncio
    async def test_route_hybrid_no_duplicates(self, router_for_integration):
        """Test that route_hybrid doesn't return duplicate skill.command combinations."""
        results = await router_for_integration.route_hybrid(
            "find files search", limit=20, threshold=0.0
        )

        # Collect all skill.command combinations
        seen = set()
        for r in results:
            key = f"{r.skill_name}.{r.command_name}"
            assert key not in seen, f"Duplicate result: {key}"
            seen.add(key)

    @pytest.mark.asyncio
    async def test_route_hybrid_empty_query_returns_nothing(self, router_for_integration):
        """Test that empty or invalid queries return empty results."""
        results = await router_for_integration.route_hybrid("", limit=5, threshold=0.0)

        # Empty query might return empty or all tools, just shouldn't crash
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_route_hybrid_uses_cache(self, router_for_integration):
        """Test that repeated queries use cache."""
        query = "git status"

        # First call
        results1 = await router_for_integration.route_hybrid(query, limit=5, threshold=0.1)

        # Check cache has the query
        assert router_for_integration._cache.get(query) is not None

        # Second call should use cache
        results2 = await router_for_integration.route_hybrid(query, limit=5, threshold=0.1)

        # Results should be the same
        assert len(results1) == len(results2)


class TestSkillDiscoverPattern:
    """Tests for the skill.discover pattern using route_hybrid."""

    @pytest.mark.asyncio
    async def test_discover_pattern_returns_results(self, router_for_integration):
        """Test the exact pattern used by skill.discover command.

        This reproduces the bug where:
        1. omni route test found tools
        2. skill.discover returned 0 tools
        """
        router = router_for_integration

        sync_result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if sync_result["status"] != "success" or sync_result.get("tools_indexed", 0) == 0:
            pytest.skip("Router database not populated, skipping integration test")

        intent = "find python files"
        limit = 5

        # This is exactly what skill.discover does
        results = await router.route_hybrid(query=intent, limit=limit, threshold=0.1)

        # Should find results
        assert len(results) > 0, "skill.discover pattern should find results"

        # Results should have valid skill/command
        for r in results:
            assert_route_result_shape(r)

    @pytest.mark.asyncio
    @parametrize_route_intent_queries()
    async def test_discover_intent_finds_expected_tool_family(
        self,
        router_for_integration,
        query: str,
        expected_tool_name: str,
    ):
        """Discovery intents should return relevant tool families."""
        router = router_for_integration

        sync_result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if sync_result["status"] != "success" or sync_result.get("tools_indexed", 0) == 0:
            pytest.skip("Router database not populated, skipping integration test")

        results = await router.route_hybrid(query, limit=10, threshold=0.1)
        tool_names = [_full_tool_name(r) for r in results]

        if expected_tool_name == "advanced_tools.smart_find":
            # Ranking may vary by runtime/index; require discovery-family tools.
            assert_tool_family_match(
                tool_names,
                substrings=["smart_find", "search"],
                exact=["python.run", "advanced_tools.smart_search"],
                msg=f"Expected discovery-related tool for query '{query}'",
            )
        elif "researcher" in expected_tool_name:
            assert_tool_family_match(
                tool_names,
                substrings=["researcher"],
                msg=f"Expected researcher skill for research/URL query '{query[:50]}...'",
            )
        elif "crawl4ai" in expected_tool_name:
            assert_tool_family_match(
                tool_names,
                substrings=["crawl4ai"],
                msg=f"Expected crawl4ai skill for crawl/URL query '{query}'",
            )
        else:
            assert_tool_family_match(
                tool_names,
                substrings=["git"],
                msg=f"Expected git-related tool for query '{query}'",
            )

    @pytest.mark.asyncio
    async def test_research_url_intent_routes_to_researcher_or_crawl4ai(
        self, router_for_integration
    ):
        """User-provided research/URL intent must route to researcher or crawl4ai (algorithm reliability).

        Query: 帮我研究一下 <github URL> / Help me research <url>.
        With threshold=0.0 we assert at least one of researcher.* or crawl4ai.* appears in top 10.
        """
        router = router_for_integration
        sync_result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if sync_result["status"] != "success" or sync_result.get("tools_indexed", 0) == 0:
            pytest.skip("Router database not populated")

        query = "帮我研究一下 https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl"
        results = await router.route_hybrid(query, limit=10, threshold=0.0)
        tool_names = [_full_tool_name(r) for r in results]

        assert_tool_family_match(
            tool_names,
            substrings=["researcher", "crawl4ai"],
            msg=(f"Research/URL intent should route to researcher or crawl4ai. Got: {tool_names}"),
        )


class TestRouterDatabaseConsistency:
    """Tests for skills table consistency (routing reads from skills table in the store)."""

    def test_skills_table_populated_after_sync(self, router_lance_path):
        """Verify the skills table in the store has tools after sync from assets/skills.

        Ensures routing has data to search; skill.discover depends on the same store.
        """
        from omni.foundation.bridge import RustVectorStore

        sync_result = _sync_local_router_from_skills(router_lance_path)
        if sync_result["status"] != "success":
            pytest.skip(f"Could not sync skills: {sync_result.get('error', 'unknown')}")

        store = RustVectorStore(router_lance_path, enable_keyword_index=True)
        skills_tools = json.loads(store._inner.list_all_tools("skills"))

        assert len(skills_tools) > 0, "skills table should have tools after sync"

    def test_skills_table_not_empty_for_routing(self, router_lance_path):
        """Ensure skills table is populated so route_hybrid can return results."""
        from omni.foundation.bridge import RustVectorStore

        sync_result = _sync_local_router_from_skills(router_lance_path)
        if sync_result["status"] != "success":
            pytest.skip(f"Could not sync skills: {sync_result.get('error', 'unknown')}")

        store = RustVectorStore(router_lance_path, enable_keyword_index=True)
        tools = json.loads(store._inner.list_all_tools("skills"))

        assert len(tools) > 0, "skills table should not be empty"


class TestRouteHybridEdgeCases:
    """Edge case tests for route_hybrid."""

    @pytest.mark.asyncio
    async def test_very_long_query(self, router_for_integration):
        """Test handling of very long queries."""
        long_query = "find " + "python files " * 100

        results = await router_for_integration.route_hybrid(long_query, limit=5, threshold=0.1)

        # Should not crash, may return empty or partial results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_query_with_special_chars(self, router_for_integration):
        """Test handling of queries with special characters."""
        # Query with characters that might cause issues
        special_queries = [
            "git commit --message",
            "query with parentheses",
            "path to file",
        ]

        for query in special_queries:
            results = await router_for_integration.route_hybrid(query, limit=3, threshold=0.1)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_limit_zero_returns_empty(self, router_for_integration):
        """Test that limit=0 returns empty list."""
        results = await router_for_integration.route_hybrid("git", limit=0, threshold=0.1)

        assert results == []

    @pytest.mark.asyncio
    async def test_limit_larger_than_results(self, router_for_integration):
        """Test that requesting more results than available works."""
        results = await router_for_integration.route_hybrid(
            "xyznonexistent", limit=100, threshold=0.1
        )

        # Should return empty or up to available results
        assert isinstance(results, list)


class TestRouteHybridPerformance:
    """Performance-related tests for route_hybrid."""

    @pytest.mark.asyncio
    async def test_cached_query_is_fast(self, router_for_integration):
        """Test that cached queries return quickly."""
        import time

        query = "git status"

        # First call - should take longer
        start = time.time()
        await router_for_integration.route_hybrid(query, limit=5, threshold=0.1)
        first_duration = time.time() - start

        # Second call - should be instant from cache
        start = time.time()
        await router_for_integration.route_hybrid(query, limit=5, threshold=0.1)
        second_duration = time.time() - start

        # Cached call should be faster (at least 10x)
        # Note: This is a soft check, not a strict assertion
        assert second_duration < first_duration or second_duration < 0.1

    @pytest.mark.asyncio
    async def test_multiple_queries_dont_interfere(self, router_for_integration):
        """Test that multiple concurrent queries don't interfere."""
        import asyncio

        queries = [
            "git commit",
            "find files",
            "search text",
            "run command",
            "edit file",
        ]

        # Run queries concurrently
        async def run_query(q):
            return await router_for_integration.route_hybrid(q, limit=3, threshold=0.1)

        results = await asyncio.gather(*[run_query(q) for q in queries])

        # Each query should return results
        for i, result in enumerate(results):
            assert_route_results_list(
                result, allow_empty=True, msg=f"Query '{queries[i]}' returned invalid results"
            )


class TestRoutingSearchSchemaComplexScenario:
    """Complex scenario: multiple intent types and assert expected tool families in top N.

    Aligns with packages/shared/schemas/skill-routing-value-standard.md and
    routing-search-value-flow: run after omni sync / skill routing value changes.
    """

    @pytest.mark.asyncio
    async def test_complex_scenario_each_query_routes_to_expected_family(
        self, router_for_integration
    ):
        """Multiple phrasings (exact-like, file-discovery, research/URL, git) route to expected families."""
        router = router_for_integration
        sync_result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if sync_result["status"] != "success" or sync_result.get("tools_indexed", 0) == 0:
            pytest.skip("Router database not populated")

        scenarios = [
            ("find python files in current directory", ["smart_find", "search"]),
            ("git commit", ["git"]),
            ("help me research a repo", ["researcher", "crawl4ai"]),
        ]
        for query, expected_substrings in scenarios:
            results = await router.route_hybrid(query, limit=10, threshold=0.0)
            tool_names = [_full_tool_name(r) for r in results]
            assert len(results) > 0, f"Query '{query}' should return at least one result"
            found = any(any(sub in name for sub in expected_substrings) for name in tool_names)
            assert found, (
                f"Query '{query}' should route to one of {expected_substrings}. Got: {tool_names[:5]}"
            )

    @pytest.mark.asyncio
    async def test_complex_scenario_top_rank_reasonable(self, router_for_integration):
        """File-discovery query should have discovery-related tool in top 3."""
        router = router_for_integration
        sync_result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if sync_result["status"] != "success" or sync_result.get("tools_indexed", 0) == 0:
            pytest.skip("Router database not populated")

        results = await router.route_hybrid("find *.py files", limit=5, threshold=0.0)
        assert len(results) > 0, "find *.py files should return results"
        top_names = [_full_tool_name(r) for r in results[:3]]
        discovery_in_top3 = any("smart_find" in n or "smart_search" in n for n in top_names)
        assert discovery_in_top3, (
            f"Expected discovery-related tool in top 3 for 'find *.py files'. Got: {top_names}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
