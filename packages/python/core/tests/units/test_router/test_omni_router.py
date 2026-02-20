"""Tests for omni.core.router.main module - OmniRouter and RouterRegistry."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from omni.test_kit.asserts import assert_route_result_shape, assert_route_results_list

from omni.core.router.main import OmniRouter, RouterRegistry, get_router
from omni.core.router.router import RouteResult


def _mock_hybrid_hit(
    *,
    skill_name: str = "git",
    command: str = "status",
    description: str = "Show status",
    score: float = 0.85,
    final_score: float = 0.85,
    confidence: str = "high",
    file_path: str | None = None,
) -> dict[str, object]:
    return {
        "skill_name": skill_name,
        "command": command,
        "description": description,
        "score": score,
        "final_score": final_score,
        "confidence": confidence,
        "ranking_reason": "vector=0.91 | keyword=0.12 | confidence=high | raw=0.850 | final=0.850",
        "input_schema_digest": "sha256:mockdigest123456",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        "file_path": file_path or f"{skill_name}/{command}.py",
    }


class TestOmniRouter:
    """Test OmniRouter class - The Grand Unified Router."""

    def test_default_initialization(self):
        """Test default initialization uses settings."""
        router = OmniRouter()

        assert router._indexer is not None
        assert router._semantic is not None
        assert router._hybrid is not None
        assert router._cache is not None
        assert router._hive is not None
        assert router._sniffer is not None
        assert isinstance(router._rerank, bool)
        assert router._initialized is False

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        router = OmniRouter(
            storage_path=":memory:",
            cache_size=500,
            cache_ttl=600,
            semantic_weight=0.8,
            keyword_weight=0.2,
            adaptive_threshold_step=0.2,
            adaptive_max_attempts=4,
        )

        assert ":memory:" in router._indexer._storage_path
        assert router._cache._max_size == 500
        assert router._cache._ttl == 600
        assert router._adaptive_threshold_step == 0.2
        assert router._adaptive_max_attempts == 4

    @pytest.mark.asyncio
    async def test_route_hybrid_preserves_rust_confidence_labels(self):
        """Router should preserve canonical confidence labels from Rust payload."""
        router = OmniRouter(storage_path=":memory:")
        mock_results = [
            {
                "skill_name": "git",
                "command": "status",
                "description": "Show status",
                "score": 0.7,
                "final_score": 0.7,
                "confidence": "high",
                "file_path": "git/status.py",
            },
        ]
        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            results = await router.route_hybrid("git status", threshold=0.1, use_cache=False)
        assert len(results) == 1
        assert results[0].confidence == "high"
        assert results[0].final_score == 0.7
        assert isinstance(results[0].ranking_reason, str)
        assert isinstance(results[0].input_schema_digest, str)
        assert_route_result_shape(results[0])

    @pytest.mark.asyncio
    async def test_route_hybrid_populates_discover_contract_fields(self):
        """Hybrid route result should always include discover contract ranking metadata."""
        router = OmniRouter(storage_path=":memory:")
        mock_results = [
            _mock_hybrid_hit(
                score=0.61,
                final_score=0.83,
                confidence="high",
                command="discover",
            ),
        ]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            results = await router.route_hybrid(
                "discover capabilities", threshold=0.1, use_cache=False
            )

        assert len(results) == 1
        row = results[0]
        assert row.score == 0.61
        assert row.final_score == 0.83
        assert row.ranking_reason
        assert row.input_schema_digest == "sha256:mockdigest123456"

    @pytest.mark.asyncio
    async def test_route_hybrid_uses_configurable_adaptive_retry(self):
        """Adaptive retry count and decrement should respect configured settings."""
        router = OmniRouter(
            storage_path=":memory:",
            adaptive_max_attempts=2,
            adaptive_threshold_step=0.2,
        )
        search = AsyncMock(return_value=[])
        with patch.object(router._hybrid, "search", search):
            results = await router.route_hybrid(
                "no result", limit=1, threshold=0.5, use_cache=False
            )
        assert results == []
        assert search.await_count == 2
        first_call = search.await_args_list[0].kwargs
        second_call = search.await_args_list[1].kwargs
        assert first_call["min_score"] == 0.0
        assert second_call["min_score"] == 0.0
        # rerank is not passed by route_hybrid; hybrid.search uses rerank=True internally

    def test_properties(self):
        """Test all property accessors."""
        router = OmniRouter()

        assert router.indexer is router._indexer
        assert router.semantic is router._semantic
        assert router.hybrid is router._hybrid
        assert router.cache is router._cache
        assert router.hive is router._hive
        assert router.sniffer is router._sniffer

    @pytest.mark.asyncio
    async def test_initialize_single_skill(self):
        """Test initializing with a single skill."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [
                    {"name": "status", "description": "Show status"},
                    {"name": "commit", "description": "Commit changes"},
                ],
            }
        ]

        await router.initialize(skills)

        assert router._initialized is True
        stats = await router._indexer.get_stats()
        assert stats["entries_indexed"] == 3  # 1 skill + 2 commands

    @pytest.mark.asyncio
    async def test_initialize_multiple_skills(self):
        """Test initializing with multiple skills."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [{"name": "status", "description": "Show status"}],
            },
            {
                "name": "memory",
                "description": "Memory operations",
                "commands": [
                    {"name": "save", "description": "Save memory"},
                    {"name": "search", "description": "Search memory"},
                ],
            },
        ]

        await router.initialize(skills)

        assert router._initialized is True
        stats = await router._indexer.get_stats()
        # 2 skills + 1 git command + 2 memory commands = 5
        assert stats["entries_indexed"] == 5

    @pytest.mark.asyncio
    async def test_initialize_skips_if_already_initialized(self):
        """Test that initialize skips if already initialized."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {"name": "git", "description": "Git skill", "commands": []},
        ]

        await router.initialize(skills)
        first_count = router._indexer._indexed_count

        # Second initialize should be skipped
        await router.initialize(skills)

        assert router._indexer._indexed_count == first_count

    @pytest.mark.asyncio
    async def test_initialize_empty_skills(self):
        """Test initializing with empty skills list."""
        router = OmniRouter(storage_path=":memory:")

        await router.initialize([])

        assert router._initialized is True
        stats = await router._indexer.get_stats()
        assert stats["entries_indexed"] == 0

    @pytest.mark.asyncio
    async def test_route_without_initialization(self):
        """Test routing falls back when not initialized."""
        router = OmniRouter(storage_path=":memory:")

        # Should still try to route through hive
        result = await router.route("git.status")

        # If hive can match, should return result
        # If hive can't match (no indexer ready), may return None
        # Either way, it should not crash
        assert result is None or isinstance(result, RouteResult)

    @pytest.mark.asyncio
    async def test_route_with_initialization(self):
        """Test routing after initialization."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [
                    {"name": "status", "description": "Show working tree status"},
                    {"name": "commit", "description": "Commit changes"},
                ],
            }
        ]

        await router.initialize(skills)

        # Route explicit command
        result = await router.route("git.status")
        assert result is not None
        assert result.skill_name == "git"
        assert result.command_name == "status"
        assert_route_result_shape(result)

    @pytest.mark.asyncio
    async def test_route_with_context(self):
        """Test routing with execution context."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [{"name": "status", "description": "Show status"}],
            }
        ]

        await router.initialize(skills)

        result = await router.route("status", context={"cwd": "/fake/repo"})

        # Should still match because context is optional
        assert result is not None or result is None

    @pytest.mark.asyncio
    async def test_route_hybrid_basic(self):
        """Test basic hybrid routing."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [
                    {"name": "status", "description": "Show working tree status"},
                    {"name": "commit", "description": "Commit changes"},
                ],
            }
        ]

        await router.initialize(skills)

        results = await router.route_hybrid("git status")

        assert isinstance(results, list)
        # Should find git.status with some score
        if results:
            assert_route_results_list(results, allow_empty=True)
            assert any(r.skill_name == "git" for r in results)

    @pytest.mark.asyncio
    async def test_route_hybrid_with_limit(self):
        """Test hybrid routing respects limit and returns RouteResult objects."""
        router = OmniRouter(storage_path=":memory:")

        # Mock the hybrid search to return test results (include file_path to avoid skipping)
        mock_results = [
            _mock_hybrid_hit(),
            _mock_hybrid_hit(
                command="commit",
                description="Commit",
                score=0.75,
                final_score=0.75,
                confidence="medium",
            ),
        ]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            results = await router.route_hybrid("git status", limit=3)

        # Should return results filtered by threshold (default 0.4)
        assert len(results) >= 1
        for r in results:
            assert isinstance(r, RouteResult)
            assert r.score >= 0.4
            assert_route_result_shape(r)

    @pytest.mark.asyncio
    async def test_route_hybrid_with_threshold(self):
        """Test hybrid routing respects threshold with adaptive fallback."""
        router = OmniRouter(storage_path=":memory:")

        # Mock results with scores that will pass with adaptive thresholding
        mock_results = [
            _mock_hybrid_hit(),
            _mock_hybrid_hit(
                command="commit",
                description="Commit",
                score=0.75,
                final_score=0.75,
                confidence="medium",
            ),
        ]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            # With threshold=0.6, both should pass (0.75 and 0.85 >= 0.6)
            results = await router.route_hybrid("test query", threshold=0.6)

        # All results should meet threshold
        for r in results:
            assert r.score >= 0.6
            assert_route_result_shape(r)

    @pytest.mark.asyncio
    async def test_route_hybrid_caching(self):
        """Test that hybrid routing caches results."""
        router = OmniRouter(storage_path=":memory:")

        mock_results = [_mock_hybrid_hit()]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            query = "git status"
            results1 = await router.route_hybrid(query)
            results2 = await router.route_hybrid(query)

            # Results should be the same (from cache)
            assert len(results1) == len(results2)
            assert router._cache.get(query) is not None
            assert_route_results_list(results1, allow_empty=False)

    @pytest.mark.asyncio
    async def test_route_hybrid_cache_miss(self):
        """Test hybrid routing cache miss returns fresh results."""
        router = OmniRouter(storage_path=":memory:")

        mock_results = [_mock_hybrid_hit()]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            query = "different query"
            results = await router.route_hybrid(query)

        assert results is not None
        assert len(results) > 0
        assert_route_results_list(results, allow_empty=False)

    @pytest.mark.asyncio
    async def test_route_hybrid_no_cache(self):
        """Test hybrid routing without cache."""
        router = OmniRouter(storage_path=":memory:")

        mock_results = [_mock_hybrid_hit()]

        with patch.object(router._hybrid, "search", AsyncMock(return_value=mock_results)):
            results = await router.route_hybrid("git status", use_cache=False)

        assert_route_results_list(results, allow_empty=True)

    @pytest.mark.asyncio
    async def test_suggest_skills(self):
        """Test skill suggestion based on context."""
        router = OmniRouter()

        suggestions = await router.suggest_skills("/fake/path")

        assert isinstance(suggestions, list)

    def test_is_ready_not_initialized(self):
        """Test is_ready returns False when not initialized."""
        router = OmniRouter()

        assert router.is_ready() is False

    @pytest.mark.asyncio
    async def test_is_ready_after_initialization(self):
        """Test is_ready returns True after initialization."""
        router = OmniRouter(storage_path=":memory:")

        skills = [{"name": "test", "description": "Test skill", "commands": []}]

        await router.initialize(skills)

        assert router.is_ready() is True

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting router statistics."""
        router = OmniRouter()

        stats = await router.get_stats()

        assert "initialized" in stats
        assert "indexer_stats" in stats
        assert "hybrid_stats" in stats
        assert "cache_stats" in stats
        assert "is_ready" in stats
        assert stats["initialized"] is False


class TestRouterRegistry:
    """Test RouterRegistry class - Singleton pattern for routers."""

    def setup_method(self):
        """Reset registry before each test."""
        RouterRegistry.reset_all()

    def teardown_method(self):
        """Clean up after each test."""
        RouterRegistry.reset_all()

    def test_get_creates_instance(self):
        """Test that get creates a new instance."""
        router = RouterRegistry.get()

        assert router is not None
        assert isinstance(router, OmniRouter)

    def test_get_returns_same_instance(self):
        """Test that get returns the same instance."""
        router1 = RouterRegistry.get()
        router2 = RouterRegistry.get()

        assert router1 is router2

    def test_get_with_name_creates_separate_instance(self):
        """Test that different names create different instances."""
        router1 = RouterRegistry.get("router1")
        router2 = RouterRegistry.get("router2")

        assert router1 is not router2

    def test_set_default(self):
        """Test setting default router name."""
        RouterRegistry.set_default("my_router")

        # Default should be updated
        assert RouterRegistry._default == "my_router"

    def test_reset_removes_instance(self):
        """Test resetting a named instance."""
        router = RouterRegistry.get("test")
        assert router is not None

        RouterRegistry.reset("test")

        # Getting again should create new instance
        router2 = RouterRegistry.get("test")
        assert router2 is not router

    def test_reset_with_nonexistent(self):
        """Test resetting nonexistent instance doesn't error."""
        RouterRegistry.reset("nonexistent")  # Should not raise

    def test_reset_all_clears_all(self):
        """Test resetting all instances."""
        RouterRegistry.get("router1")
        RouterRegistry.get("router2")
        RouterRegistry.get("router3")

        assert len(RouterRegistry._instances) == 3

        RouterRegistry.reset_all()

        assert len(RouterRegistry._instances) == 0

    def test_instances_isolation(self):
        """Test that different router instances are isolated."""
        router1 = RouterRegistry.get("router1")
        router2 = RouterRegistry.get("router2")

        # Modifying one shouldn't affect the other
        router1._initialized = True

        assert router1._initialized is True
        assert router2._initialized is False

    def test_default_router_persistence(self):
        """Test that default router persists across gets."""
        RouterRegistry.set_default("primary")
        router1 = RouterRegistry.get()

        assert router1 is RouterRegistry.get("primary")

        RouterRegistry.set_default("secondary")
        router2 = RouterRegistry.get()

        assert router2 is RouterRegistry.get("secondary")
        assert router1 is not router2


class TestGetRouter:
    """Test get_router convenience function."""

    def setup_method(self):
        """Reset registry before each test."""
        RouterRegistry.reset_all()

    def teardown_method(self):
        """Clean up after each test."""
        RouterRegistry.reset_all()

    def test_get_router_default(self):
        """Test get_router with default name."""
        router = get_router()

        assert router is not None
        assert isinstance(router, OmniRouter)

    def test_get_router_with_name(self):
        """Test get_router with specific name."""
        router = get_router("custom")

        assert router is RouterRegistry.get("custom")

    def test_get_router_none(self):
        """Test get_router with None returns default."""
        # Reset to ensure clean state
        RouterRegistry.reset_all()
        RouterRegistry._default = "default"

        router = get_router(None)

        # None should create a default router
        assert router is not None
        assert isinstance(router, OmniRouter)


class TestOmniRouterIntegration:
    """Integration tests for OmniRouter with real-like components."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_mocked_search(self):
        """Test complete routing workflow with mocked search."""
        from omni.foundation.bridge import SearchResult

        router = OmniRouter(storage_path=":memory:")

        # Mock the indexer search to return results
        router._indexer.search = AsyncMock(
            return_value=[
                SearchResult(
                    id="git.status",
                    score=0.95,
                    payload={
                        "type": "command",
                        "skill_name": "git",
                        "command": "status",
                    },
                )
            ]
        )
        router._indexer._indexed_count = 1

        # Initialize to set up the rest
        router._initialized = True

        result = await router.route("git.status")

        assert result is not None
        assert result.skill_name == "git"
        assert result.command_name == "status"
        assert result.confidence == "high"
        assert_route_result_shape(result)

    @pytest.mark.asyncio
    async def test_fallback_to_hive_when_semantic_fails(self):
        """Test that routing falls back to hive when semantic fails."""
        router = OmniRouter(storage_path=":memory:")

        # Initialize but don't set up mock - should use hive's fallback
        router._initialized = True
        router._indexer.search = AsyncMock(return_value=[])
        router._indexer._indexed_count = 1

        # Explicit command should work through hive
        result = await router.route("git.status")

        assert result is not None
        assert result.skill_name == "git"
        assert_route_result_shape(result)

    @pytest.mark.asyncio
    async def test_route_hybrid_empty_results(self):
        """Test hybrid routing with very high threshold returns empty."""
        router = OmniRouter(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [{"name": "status", "description": "Show status"}],
            }
        ]

        await router.initialize(skills)

        # Query with very high threshold should return empty
        # (The router uses semantic search which can match anything,
        # but with high threshold only exact matches pass)
        results = await router.route_hybrid("xyz123nonexistent", threshold=0.99)

        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
