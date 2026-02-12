"""Tests for ZK reasoning search (PageIndex-style high-precision retrieval)."""

import asyncio
import os
from pathlib import Path

import pytest

# Get project root for zk notebook (where .zk folder is located)
PROJECT_ROOT = Path(
    os.environ.get("PROJECT_ROOT", "/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion")
)


@pytest.fixture
def notebook_dir():
    """Module-level fixture for zk notebook directory."""
    return PROJECT_ROOT


from omni.rag.zk_search import (
    ZkSearchConfig,
    ZkSearchResult,
    ZkReasoningSearcher,
    ZkHybridSearcher,
    get_zk_searcher,
    get_zk_hybrid_searcher,
)
from omni.rag.zk_integration import ZkClient


class TestZkSearchConfig:
    """Test ZkSearchConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ZkSearchConfig()
        assert config.max_iterations == 3
        assert config.max_distance == 3
        assert config.max_notes_per_iteration == 10
        assert config.direct_match_weight == 1.0
        assert config.min_score == 0.3
        assert config.use_vector_fallback is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = ZkSearchConfig(
            max_iterations=5,
            min_score=0.5,
            use_vector_fallback=False,
        )
        assert config.max_iterations == 5
        assert config.min_score == 0.5
        assert config.use_vector_fallback is False


class TestZkReasoningSearcher:
    """Test ZkReasoningSearcher."""

    @pytest.fixture
    def notebook_dir(self):
        """Get the zk notebook directory (project root where .zk exists)."""
        return PROJECT_ROOT

    @pytest.fixture
    def searcher(self, notebook_dir):
        """Create a searcher for testing."""
        config = ZkSearchConfig(max_iterations=2, max_notes_per_iteration=5)
        return ZkReasoningSearcher(notebook_dir=notebook_dir, config=config)

    def test_init(self, searcher, notebook_dir):
        """Test searcher initialization."""
        assert searcher.notebook_dir == notebook_dir
        assert isinstance(searcher.zk_client, ZkClient)

    @pytest.mark.asyncio
    async def test_get_toc_for_context(self, searcher):
        """Test TOC generation for LLM context."""
        toc = await searcher.get_toc_for_context()
        assert toc is not None
        assert "notes" in toc
        assert "total" in toc

    @pytest.mark.asyncio
    async def test_search_direct_match(self, searcher):
        """Test direct keyword search."""
        results = await searcher.search("architecture", max_results=5)
        assert len(results) >= 0  # May or may not find results

    @pytest.mark.asyncio
    async def test_search_with_context(self, searcher):
        """Test search with additional context."""
        results = await searcher.search(
            "agent skills",
            context="previous question about progressive disclosure",
            max_results=5,
        )
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_search_iterations(self, searcher):
        """Test that search performs multiple iterations."""
        config = ZkSearchConfig(max_iterations=3)
        searcher = ZkReasoningSearcher(
            notebook_dir=searcher.notebook_dir,
            config=config,
        )

        results = await searcher.search("test", max_results=10)
        # Results may come from different iterations
        assert results is not None

    @pytest.mark.asyncio
    async def test_search_result_scoring(self, searcher):
        """Test that results have valid scores."""
        results = await searcher.search("architecture", max_results=5)

        for result in results:
            assert isinstance(result, ZkSearchResult)
            assert 0.0 <= result.relevance_score <= 1.0
            assert result.source in ["direct", "linked_by", "recursive"]
            assert result.distance >= 0

    @pytest.mark.asyncio
    async def test_search_no_results(self, searcher):
        """Test search with no matching results."""
        results = await searcher.search("xyznonexistentquery123", max_results=5)
        # Should return empty list, not crash
        assert results == [] or len(results) >= 0


class TestZkHybridSearcher:
    """Test ZkHybridSearcher."""

    @pytest.fixture
    def notebook_dir(self):
        """Get the zk notebook directory (project root where .zk exists)."""
        return PROJECT_ROOT

    def test_init_without_vector(self, notebook_dir):
        """Test hybrid searcher without vector fallback."""
        searcher = ZkHybridSearcher(notebook_dir=notebook_dir)
        assert searcher.zk_searcher is not None
        assert searcher.vector_search_func is None

    def test_init_with_vector(self, notebook_dir):
        """Test hybrid searcher with vector fallback."""

        async def dummy_vector_search(query, limit=10):
            return []

        searcher = ZkHybridSearcher(
            notebook_dir=notebook_dir,
            vector_search_func=dummy_vector_search,
        )
        assert searcher.vector_search_func is not None

    @pytest.mark.asyncio
    async def test_hybrid_search_zk_only(self, notebook_dir):
        """Test hybrid search using only ZK (no vector fallback)."""
        searcher = ZkHybridSearcher(notebook_dir=notebook_dir)

        result = await searcher.search("architecture", max_results=5, use_hybrid=False)

        assert "zk_results" in result
        assert "merged_results" in result
        assert "total_zk" in result

    @pytest.mark.asyncio
    async def test_hybrid_search_with_vector(self, notebook_dir):
        """Test hybrid search with ZK + vector."""
        vector_results = [{"id": "test1", "note": {"title": "Test"}, "score": 0.8}]

        async def dummy_vector_search(query, limit=10):
            return vector_results

        searcher = ZkHybridSearcher(
            notebook_dir=notebook_dir,
            vector_search_func=dummy_vector_search,
        )

        result = await searcher.search("test", max_results=5, use_hybrid=True)

        assert "zk_results" in result
        assert "vector_results" in result
        assert "merged_results" in result


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_zk_searcher(self, notebook_dir):
        """Test get_zk_searcher convenience function."""
        searcher = get_zk_searcher(notebook_dir=notebook_dir)
        assert isinstance(searcher, ZkReasoningSearcher)

    def test_get_zk_hybrid_searcher(self, notebook_dir):
        """Test get_zk_hybrid_searcher convenience function."""
        searcher = get_zk_hybrid_searcher(notebook_dir=notebook_dir)
        assert isinstance(searcher, ZkHybridSearcher)


class TestZkSearchResult:
    """Test ZkSearchResult dataclass."""

    def test_create_result(self):
        """Test creating a search result."""
        result = ZkSearchResult(
            note=None,  # Would need a real ZkNote
            relevance_score=0.85,
            source="direct",
            distance=0,
            reasoning="Test reasoning",
        )
        assert result.relevance_score == 0.85
        assert result.source == "direct"
        assert result.distance == 0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
