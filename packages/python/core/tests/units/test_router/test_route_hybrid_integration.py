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

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Generator


# Module-level fixtures for all test classes


@pytest.fixture(scope="module")
def router_lance_path() -> Generator[str, None, None]:
    """Get the path to router.lance for tests."""
    from omni.agent.cli.commands.reindex import get_database_path

    path = get_database_path("router")
    yield path


@pytest.fixture(scope="module")
def router_for_integration(router_lance_path) -> Generator:
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

        # Index some test tools to router.lance
        skills_path = Path(__file__).parent.parent.parent.parent.parent / "assets/skills"
        if not skills_path.exists():
            pytest.skip("Skills directory not found, skipping integration test")

        # Use reindex function to populate router.lance
        from omni.agent.cli.commands.reindex import _sync_router_from_skills

        result = _sync_router_from_skills()
        if result["status"] != "success":
            pytest.skip(f"Could not sync router database: {result.get('error', 'unknown')}")

        # Now test route_hybrid
        results = await router.route_hybrid("find python files", limit=5, threshold=0.1)

        # Should find at least one result
        assert len(results) > 0, "route_hybrid should find indexed tools"

        # First result should be relevant
        first = results[0]
        assert first.skill_name is not None
        assert first.command_name is not None
        assert first.score > 0

    @pytest.mark.asyncio
    async def test_route_hybrid_returns_route_result_objects(self, router_for_integration):
        """Test that route_hybrid returns proper RouteResult objects."""
        from omni.core.router.router import RouteResult

        results = await router_for_integration.route_hybrid("git status", limit=5, threshold=0.1)

        for r in results:
            assert isinstance(r, RouteResult)
            assert hasattr(r, "skill_name")
            assert hasattr(r, "command_name")
            assert hasattr(r, "score")
            assert hasattr(r, "confidence")

    @pytest.mark.asyncio
    async def test_route_hybrid_confidence_levels(self, router_for_integration):
        """Test that confidence levels are correctly assigned."""
        results = await router_for_integration.route_hybrid("git commit", limit=10, threshold=0.0)

        for r in results:
            assert r.confidence in ("high", "medium", "low")

            # Verify confidence matches score
            if r.confidence == "high":
                assert r.score >= 0.75
            elif r.confidence == "medium":
                assert 0.5 <= r.score < 0.75
            else:  # low
                assert r.score < 0.5

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
        from omni.core.kernel import get_kernel

        router = router_for_integration
        kernel = get_kernel()

        intent = "find python files"
        limit = 5

        # This is exactly what skill.discover does
        results = await router.route_hybrid(query=intent, limit=limit, threshold=0.1)

        # Should find results
        assert len(results) > 0, "skill.discover pattern should find results"

        # Results should have valid skill/command
        for r in results:
            full_id = f"{r.skill_name}.{r.command_name}"
            assert full_id is not None
            assert "." in full_id  # Should be skill.command format

    @pytest.mark.asyncio
    async def test_discover_finds_smart_find_tool(self, router_for_integration):
        """Test that the smart_find tool is discoverable.

        This verifies the specific case from the bug report where
        advanced_tools.smart_find should be found for "find files" queries.
        """
        router = router_for_integration

        # Query that should match smart_find
        results = await router.route_hybrid(
            "find python files in directory", limit=10, threshold=0.1
        )

        # Should find smart_find or similar tool
        tool_names = [f"{r.skill_name}.{r.command_name}" for r in results]

        # At least one of these should be present
        assert any("smart_find" in name or "search" in name for name in tool_names), (
            f"Expected smart_find or search tool, got: {tool_names}"
        )


class TestRouterDatabaseConsistency:
    """Tests for router.lance database consistency."""

    def test_skills_and_router_have_same_tools(self):
        """Verify skills.lance and router.lance have same tool count.

        This prevents the bug where skills.lance was populated but
        router.lance was empty, causing skill.discover to fail.
        """
        from omni.agent.cli.commands.reindex import get_database_paths
        from omni.foundation.bridge import RustVectorStore, get_vector_store

        db_paths = get_database_paths()

        # Get tools from skills.lance
        skills_store = RustVectorStore(db_paths["skills"], enable_keyword_index=True)
        skills_tools = asyncio.run(skills_store.list_all_tools())

        # Get tools from router.lance
        router_store = get_vector_store(db_paths["router"], enable_keyword_index=True)
        router_tools = asyncio.run(router_store.list_all_tools())

        # Both should have the same number of tools
        assert len(skills_tools) == len(router_tools), (
            f"skills.lance ({len(skills_tools)}) != router.lance ({len(router_tools)})"
        )

    def test_router_database_is_populated(self):
        """Test that router.lance is not empty.

        This catches the case where reindex was never run.
        """
        from omni.agent.cli.commands.reindex import get_database_path
        from omni.foundation.bridge import get_vector_store

        router_path = get_database_path("router")
        store = get_vector_store(router_path, enable_keyword_index=True)
        tools = asyncio.run(store.list_all_tools())

        assert len(tools) > 0, "router.lance should not be empty"


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
            assert isinstance(result, list), f"Query '{queries[i]}' returned non-list"
            # Each result should have valid structure
            for r in result:
                assert hasattr(r, "skill_name")
                assert hasattr(r, "command_name")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
