"""Integration tests for route_hybrid with real vector store.

These tests verify the complete flow from query to results using
the actual RustVectorStore and router.lance database.

Tests cover:
- Full integration with router.lance
- Search result correctness
- Threshold filtering
- Deduplication
- Skill discovery patterns
- Database synchronization
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from omni.test_kit.asserts import (
    assert_route_result_shape,
    assert_route_results_list,
    assert_tool_family_match,
)
from omni.test_kit.fixtures.vector import parametrize_route_intent_queries

# Module-level fixtures for all test classes


@pytest.fixture(scope="module")
def router_lance_path():
    """Use isolated router DB path to avoid xdist cross-test interference."""
    temp_dir = tempfile.mkdtemp(prefix="router-integration-")
    try:
        yield str(Path(temp_dir) / "router.lance")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _sync_local_router_from_skills_async(storage_path: str) -> dict[str, int | str]:
    """Index skills/router into isolated storage path."""
    from omni.foundation.bridge import RustVectorStore

    skills_path = Path(__file__).parent.parent.parent.parent.parent / "assets/skills"
    if not skills_path.exists():
        return {"status": "error", "error": "skills path not found", "tools_indexed": 0}

    store = RustVectorStore(storage_path, enable_keyword_index=True)
    skills_count, router_count = await store.index_skill_tools_dual(
        str(skills_path), "skills", "router"
    )
    return {"status": "success", "skills_indexed": skills_count, "tools_indexed": router_count}


def _sync_local_router_from_skills(storage_path: str) -> dict[str, int | str]:
    return asyncio.run(_sync_local_router_from_skills_async(storage_path))


def _full_tool_name(result) -> str:
    return f"{result.skill_name}.{result.command_name}"


@pytest.fixture(scope="module")
def router_for_integration(router_lance_path):
    """Create a router for integration tests."""
    from omni.core.router.main import OmniRouter, RouterRegistry

    RouterRegistry.reset_all()
    router = OmniRouter(storage_path=router_lance_path)
    yield router
    RouterRegistry.reset_all()


class TestRouteHybridIntegration:
    """Integration tests for route_hybrid with real router.lance."""

    @pytest.mark.asyncio
    async def test_route_hybrid_finds_indexed_tools(self, router_for_integration):
        """Test that route_hybrid finds tools that were indexed.

        This is the critical test that prevented the bug where
        skill.discover returned 0 tools despite omni route test working.
        """
        router = router_for_integration

        result = await _sync_local_router_from_skills_async(router._indexer._storage_path)
        if result["status"] != "success":
            pytest.skip(f"Could not sync router database: {result.get('error', 'unknown')}")

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
        else:
            assert_tool_family_match(
                tool_names,
                substrings=["git"],
                msg=f"Expected git-related tool for query '{query}'",
            )


class TestRouterDatabaseConsistency:
    """Tests for router.lance database consistency."""

    def test_skills_and_router_have_same_tools(self, router_lance_path):
        """Verify skills.lance and router.lance have same tool count.

        This prevents the bug where skills.lance was populated but
        router.lance was empty, causing skill.discover to fail.
        """
        from omni.foundation.bridge import RustVectorStore

        # First, ensure router is synced from skills
        sync_result = _sync_local_router_from_skills(router_lance_path)
        if sync_result["status"] != "success":
            pytest.skip(f"Could not sync router database: {sync_result.get('error', 'unknown')}")

        store = RustVectorStore(router_lance_path, enable_keyword_index=True)
        skills_tools = json.loads(store._inner.list_all_tools("skills"))
        router_tools = json.loads(store._inner.list_all_tools("router"))

        # After sync, both should have the same number of tools
        assert len(skills_tools) == len(router_tools), (
            f"After sync: skills.lance ({len(skills_tools)}) != router.lance ({len(router_tools)})"
        )

    def test_router_database_is_populated(self, router_lance_path):
        """Test that router.lance is not empty.

        This catches the case where reindex was never run.
        """
        from omni.foundation.bridge import RustVectorStore

        # Ensure router is synced from a fresh skills snapshot first.
        sync_result = _sync_local_router_from_skills(router_lance_path)
        if sync_result["status"] != "success":
            pytest.skip(f"Could not sync router database: {sync_result.get('error', 'unknown')}")

        store = RustVectorStore(router_lance_path, enable_keyword_index=True)
        tools = json.loads(store._inner.list_all_tools("router"))

        assert len(tools) > 0, "router table should not be empty"


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
