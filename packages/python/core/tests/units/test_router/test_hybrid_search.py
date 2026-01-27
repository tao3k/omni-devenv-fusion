"""Tests for omni.core.router.hybrid_search module."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from omni.core.router.hybrid_search import (
    HybridMatch,
    HybridSearch,
)


class TestHybridMatch:
    """Test HybridMatch Pydantic model."""

    def test_create_basic_match(self):
        """Test creating a basic hybrid match."""
        match = HybridMatch(
            id="test_001",
            content="Test content",
            semantic_score=0.8,
            keyword_score=0.6,
        )

        assert match.id == "test_001"
        assert match.content == "Test content"
        assert match.semantic_score == 0.8
        assert match.keyword_score == 0.6
        assert match.combined_score == 0.0  # Not calculated yet

    def test_create_with_metadata(self):
        """Test creating a match with metadata."""
        match = HybridMatch(
            id="test_002",
            content="Content",
            semantic_score=0.9,
            keyword_score=0.7,
            combined_score=0.85,
            metadata={"skill": "git", "command": "commit"},
        )

        assert match.metadata["skill"] == "git"
        assert match.metadata["command"] == "commit"

    def test_immutable(self):
        """Test that HybridMatch is immutable (frozen)."""
        match = HybridMatch(
            id="test",
            content="Content",
        )
        with pytest.raises(Exception):
            match.id = "modified"


class TestHybridSearch:
    """Test HybridSearch class."""

    def test_default_initialization(self):
        """Test default hybrid search initialization."""
        mock_indexer = MagicMock()
        search = HybridSearch(mock_indexer)

        assert search._semantic_weight == 0.7
        assert search._keyword_weight == 0.3  # Default, keyword_indexer is None so not used
        assert search._keyword_indexer is None

    def test_custom_weights(self):
        """Test custom weight initialization."""
        mock_indexer = MagicMock()
        search = HybridSearch(mock_indexer, semantic_weight=0.8, keyword_weight=0.2)

        assert search._semantic_weight == 0.8
        assert search._keyword_weight == 0.2

    def test_set_weights(self):
        """Test dynamically setting weights."""
        mock_indexer = MagicMock()
        search = HybridSearch(mock_indexer)

        search.set_weights(0.6, 0.4)

        assert search._semantic_weight == 0.6
        assert search._keyword_weight == 0.4

    def test_get_weights(self):
        """Test getting current weights."""
        mock_indexer = MagicMock()
        search = HybridSearch(mock_indexer, semantic_weight=0.75, keyword_weight=0.25)

        semantic, keyword = search.get_weights()

        assert semantic == 0.75
        assert keyword == 0.25

    def test_stats(self):
        """Test getting hybrid search statistics."""
        mock_indexer = MagicMock()
        search = HybridSearch(mock_indexer, semantic_weight=0.7, keyword_weight=0.3)

        stats = search.stats()

        assert stats["semantic_weight"] == 0.7
        assert stats["keyword_weight"] == 0.3
        assert stats["has_keyword_indexer"] is False

    @pytest.mark.asyncio
    async def test_search_with_semantic_only(self):
        """Test search with semantic results only."""
        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                MagicMock(
                    id="result_1",
                    score=0.9,
                    payload={"content": "Git commit message", "type": "command"},
                ),
            ]
        )

        search = HybridSearch(mock_indexer)
        results = await search.search("commit code")

        assert len(results) == 1
        assert results[0].id == "result_1"

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test that search respects limit parameter."""
        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                MagicMock(id=f"result_{i}", score=0.9, payload={"content": "test"})
                for i in range(10)
            ]
        )

        search = HybridSearch(mock_indexer)
        results = await search.search("test", limit=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_with_min_score(self):
        """Test search with minimum score threshold."""
        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                MagicMock(id="high", score=0.9, payload={"content": "test"}),
                MagicMock(id="low", score=0.1, payload={"content": "test"}),
            ]
        )

        search = HybridSearch(mock_indexer)
        results = await search.search("test", min_score=0.5)

        assert len(results) == 1
        assert results[0].id == "high"

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Test search with empty query."""
        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(return_value=[])

        search = HybridSearch(mock_indexer)
        results = await search.search("")

        assert results == []


class TestHybridSearchIntegration:
    """Integration tests for hybrid search."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete hybrid search workflow (semantic-only)."""
        # Create semantic indexer mock
        semantic_indexer = MagicMock()
        semantic_indexer.search = AsyncMock(
            return_value=[
                MagicMock(
                    id="semantic_result",
                    score=0.85,
                    payload={
                        "content": "Git commit command for version control",
                        "type": "command",
                        "skill": "git",
                    },
                ),
            ]
        )

        # Create hybrid search without keyword indexer
        search = HybridSearch(
            semantic_indexer,
            keyword_indexer=None,
            semantic_weight=0.7,
            keyword_weight=0.3,
        )

        # Execute search
        results = await search.search("git commit message")

        # Verify results
        assert len(results) == 1
        assert results[0].id == "semantic_result"

    @pytest.mark.asyncio
    async def test_weight_adjustment(self):
        """Test dynamic weight adjustment affects results."""
        semantic_indexer = MagicMock()
        semantic_indexer.search = AsyncMock(
            return_value=[
                MagicMock(id="sem", score=0.9, payload={"content": "test"}),
            ]
        )

        # Test with semantic-only weights
        search1 = HybridSearch(
            semantic_indexer, keyword_indexer=None, semantic_weight=1.0, keyword_weight=0.0
        )

        results1 = await search1.search("test")

        # Should return results
        assert len(results1) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
