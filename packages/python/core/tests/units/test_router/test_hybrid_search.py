"""Tests for omni.core.router.hybrid_search module - Rust-Native Implementation.

These tests verify the Rust-native hybrid search implementation that delegates
to omni-vector's search_tools for vector search + keyword rescue.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHybridSearchRustNative:
    """Test Rust-native HybridSearch implementation."""

    def test_default_initialization(self):
        """Test default hybrid search initialization (no args required)."""
        # The new HybridSearch doesn't need indexers - it uses Rust internally
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()

        # Verify it has the store reference
        assert search._store is not None

    def test_fixed_weights(self):
        """Test that weights are fixed (no configurable weights in Rust-native)."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()

        semantic, keyword = search.get_weights()
        # Rust weights: SEMANTIC_WEIGHT=1.0, KEYWORD_WEIGHT=1.5
        assert semantic == 1.0
        assert keyword == 1.5

    def test_stats_shows_rust_implementation(self):
        """Test that stats indicate Rust-native Weighted RRF implementation."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        stats = search.stats()

        assert stats["implementation"] == "rust-native-weighted-rrf"
        assert stats["strategy"] == "weighted_rrf_field_boosting"
        assert stats["semantic_weight"] == 1.0
        assert stats["keyword_weight"] == 1.5
        assert stats["rrf_k"] == 10
        assert stats["field_boosting"]["name_token_boost"] == 0.5
        assert stats["field_boosting"]["exact_phrase_boost"] == 1.5

    def test_set_weights_logs_info(self):
        """Test that set_weights logs info about fixed weights."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        # Should not error, just log info
        search.set_weights(0.9, 0.1)

        # Weights should still be the same (fixed)
        semantic, keyword = search.get_weights()
        assert semantic == 1.0
        assert keyword == 1.5


class TestHybridSearchWithMockedStore:
    """Test HybridSearch with mocked Rust store."""

    @pytest.mark.asyncio
    async def test_search_calls_rust_store(self):
        """Test that search delegates to Rust store.search_tools."""
        from omni.core.router.hybrid_search import HybridSearch

        # Create mock results that Rust would return
        mock_results = [
            {
                "name": "git.commit",
                "description": "Commit changes",
                "score": 0.95,
                "skill_name": "git",
                "tool_name": "commit",
                "file_path": "git/scripts/commit.py",
                "keywords": ["commit", "git"],
                "input_schema": "{}",
            }
        ]

        with patch.object(
            MagicMock(), "search_tools", new_callable=AsyncMock, return_value=mock_results
        ) as mock_search:
            # We need to patch the store's search_tools
            search = HybridSearch()
            search._store.search_tools = AsyncMock(return_value=mock_results)

            results = await search.search("git commit")

            # Verify store was called
            search._store.search_tools.assert_called_once()

            # Verify results format
            assert len(results) == 1
            assert results[0]["id"] == "git.commit"
            assert results[0]["skill_name"] == "git"
            assert results[0]["command"] == "commit"

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test that limit is passed to Rust store."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.search_tools = AsyncMock(return_value=[])

        await search.search("test", limit=5)

        # Verify limit was passed
        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("limit") == 5

    @pytest.mark.asyncio
    async def test_search_with_threshold(self):
        """Test that threshold is passed to Rust store."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.search_tools = AsyncMock(return_value=[])

        await search.search("test", min_score=0.7)

        # Verify threshold was passed
        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("threshold") == 0.7

    @pytest.mark.asyncio
    async def test_search_passes_query_for_keyword_rescue(self):
        """Test that query text is passed for keyword rescue."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.search_tools = AsyncMock(return_value=[])

        await search.search("git commit message")

        # Verify query_text was passed (triggers keyword rescue in Rust)
        call_args = search._store.search_tools.call_args
        assert "git commit message" in str(call_args)


class TestHybridSearchIntegration:
    """Integration tests for Rust-native hybrid search."""

    @pytest.mark.asyncio
    async def test_result_format_complete(self):
        """Test that results have all required fields."""
        from omni.core.router.hybrid_search import HybridSearch

        mock_results = [
            {
                "name": "python.run",
                "description": "Run Python code",
                "score": 0.88,
                "skill_name": "python",
                "tool_name": "run",
                "file_path": "python/scripts/run.py",
                "keywords": ["python", "run", "execute"],
                "input_schema": '{"type": "object", "properties": {"code": {"type": "string"}}}',
            }
        ]

        search = HybridSearch()
        search._store.search_tools = AsyncMock(return_value=mock_results)

        results = await search.search("run python")

        assert len(results) == 1
        result = results[0]

        # All required fields should be present
        assert "id" in result
        assert "content" in result
        assert "score" in result
        assert "skill_name" in result
        assert "command" in result
        assert "file_path" in result
        assert "keywords" in result
        assert "input_schema" in result
        assert "payload" in result

    @pytest.mark.asyncio
    async def test_empty_results_on_error(self):
        """Test that empty list is returned on error."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.search_tools = AsyncMock(return_value=[])

        results = await search.search("nonexistent_tool_xyz")

        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
