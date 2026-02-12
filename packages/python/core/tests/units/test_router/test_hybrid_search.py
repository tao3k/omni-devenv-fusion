"""Tests for omni.core.router.hybrid_search module - Rust-Native Implementation.

These tests verify the Rust-native hybrid search implementation that delegates
to omni-vector's search_tools for vector search + keyword rescue.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omni.test_kit.fixtures.vector import make_tool_search_payload


def _stub_embed(search) -> None:
    """Inject deterministic async embedding to keep tests hermetic."""
    search._embed_func = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]])


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

    def test_get_weights_reads_rust_profile(self):
        """Weights should be sourced from Rust profile, not Python constants."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.get_search_profile = MagicMock(
            return_value={
                "semantic_weight": 0.9,
                "keyword_weight": 1.7,
                "rrf_k": 20,
                "implementation": "rust-profile-test",
            }
        )
        semantic, keyword = search.get_weights()
        assert semantic == 0.9
        assert keyword == 1.7


class TestHybridSearchWithMockedStore:
    """Test HybridSearch with mocked Rust store."""

    @pytest.mark.asyncio
    async def test_search_calls_rust_store(self):
        """Test that search delegates to Rust store.search_tools."""
        from omni.core.router.hybrid_search import HybridSearch

        # Create mock results that Rust would return
        mock_results = [
            make_tool_search_payload(
                score=0.95,
                final_score=0.97,
                tool_name="commit",
                file_path="git/scripts/commit.py",
                routing_keywords=["commit", "git"],
                input_schema="{}",
            )
        ]

        with patch.object(
            MagicMock(), "search_tools", new_callable=AsyncMock, return_value=mock_results
        ):
            # We need to patch the store's search_tools
            search = HybridSearch()
            _stub_embed(search)
            search._store.search_tools = AsyncMock(return_value=mock_results)

            results = await search.search("git commit")

            # Verify store was called
            search._store.search_tools.assert_called_once()

            # Verify results format
            assert len(results) == 1
            assert results[0]["id"] == "git.commit"
            assert results[0]["skill_name"] == "git"
            assert results[0]["command"] == "commit"
            assert results[0]["confidence"] == "high"
            assert results[0]["final_score"] == 0.97

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test that limit is passed to Rust store."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
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
        _stub_embed(search)
        search._store.search_tools = AsyncMock(return_value=[])

        await search.search("test", min_score=0.7)

        # Verify threshold was passed
        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("threshold") == 0.7

    @pytest.mark.asyncio
    async def test_search_with_confidence_profile_override(self):
        """Confidence profile override should be forwarded to Rust bridge."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(return_value=[])

        profile = {
            "high_threshold": 0.81,
            "medium_threshold": 0.55,
            "low_floor": 0.12,
        }
        await search.search("test", confidence_profile=profile)

        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("confidence_profile") == profile

    @pytest.mark.asyncio
    async def test_search_with_rerank_override(self):
        """Rerank override should be forwarded to Rust bridge."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(return_value=[])

        await search.search("test", rerank=False)

        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("rerank") is False

    @pytest.mark.asyncio
    async def test_search_passes_query_for_keyword_rescue(self):
        """Test that query text is passed for keyword rescue."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
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
            make_tool_search_payload(
                name="python.run",
                description="Run Python code",
                score=0.88,
                final_score=0.86,
                confidence="medium",
                skill_name="python",
                tool_name="run",
                file_path="python/scripts/run.py",
                routing_keywords=["python", "run", "execute"],
                input_schema='{"type": "object", "properties": {"code": {"type": "string"}}}',
                category="python",
            )
        ]

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(return_value=mock_results)

        results = await search.search("run python")

        assert len(results) == 1
        result = results[0]

        # All required fields should be present
        assert "id" in result
        assert "description" in result
        assert "score" in result
        assert "confidence" in result
        assert "final_score" in result
        assert "skill_name" in result
        assert "tool_name" in result
        assert "command" in result
        assert "file_path" in result
        assert "routing_keywords" in result
        assert "input_schema" in result
        assert "payload" in result
        assert "metadata" in result["payload"]
        assert result["tool_name"] == "python.run"
        assert result["routing_keywords"] == ["python", "run", "execute"]
        assert result["payload"]["metadata"]["tool_name"] == "python.run"
        assert result["payload"]["metadata"]["routing_keywords"] == ["python", "run", "execute"]
        assert result["payload"]["metadata"]["input_schema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_empty_results_on_error(self):
        """Test that empty list is returned on error."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(return_value=[])

        results = await search.search("nonexistent_tool_xyz")

        assert results == []

    @pytest.mark.asyncio
    async def test_invalid_payload_is_skipped(self):
        """Invalid tool-search payload should be ignored by parser."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(
            return_value=[
                {"name": "git.commit", "score": 0.9},  # missing schema/tool_name
            ]
        )
        results = await search.search("git commit")
        assert results == []

    @pytest.mark.asyncio
    async def test_uuid_like_tool_name_is_skipped(self):
        """UUID-like tool names must be filtered out from router results."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        search._store.search_tools = AsyncMock(
            return_value=[
                {
                    "schema": "omni.vector.tool_search.v1",
                    "name": "6f9619ff-8b86-d011-b42d-00cf4fc964ff",
                    "description": "bad record",
                    "score": 0.95,
                    "final_score": 0.92,
                    "confidence": "high",
                    "skill_name": "unknown",
                    "tool_name": "6f9619ff-8b86-d011-b42d-00cf4fc964ff",
                    "file_path": "",
                    "routing_keywords": [],
                    "input_schema": "{}",
                    "intents": [],
                    "category": "unknown",
                },
                {
                    **make_tool_search_payload(
                        name="advanced_tools.smart_find",
                        tool_name="advanced_tools.smart_find",
                        description="Find files",
                        score=0.91,
                        final_score=0.89,
                        skill_name="advanced_tools",
                        file_path="assets/skills/advanced_tools/scripts/search.py",
                        routing_keywords=["find", "files"],
                        input_schema="{}",
                        category="search",
                    )
                },
            ]
        )
        results = await search.search("find python files")
        assert len(results) == 1
        assert results[0]["id"] == "advanced_tools.smart_find"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
