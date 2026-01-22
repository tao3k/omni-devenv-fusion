"""
test_vector_store.py - Vector Store Tests

Tests for the Foundation VectorStoreClient and embedding services.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestEmbeddingService:
    """Tests for the EmbeddingService."""

    def test_singleton_pattern(self):
        """EmbeddingService should be a singleton."""
        from omni.foundation.services.embedding import EmbeddingService

        instance1 = EmbeddingService()
        instance2 = EmbeddingService()
        assert instance1 is instance2

    def test_dimension_default(self):
        """Should have default dimension of 1536."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.dimension == 1536

    def test_embed_returns_list(self):
        """embed() should return a list of vectors."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result = service.embed("test text")
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 1536

    def test_embed_batch(self):
        """embed_batch() should return list of vectors."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        texts = ["text1", "text2", "text3"]
        result = service.embed_batch(texts)
        assert isinstance(result, list)
        assert len(result) == 3
        for vec in result:
            assert len(vec) == 1536

    def test_deterministic_embedding(self):
        """Same text should produce same embedding."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result1 = service.embed("deterministic text")
        result2 = service.embed("deterministic text")
        assert result1 == result2

    def test_different_texts_different_embeddings(self):
        """Different texts should produce different embeddings."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result1 = service.embed("text one")
        result2 = service.embed("text two")
        assert result1 != result2

    def test_get_embedding_service(self):
        """get_embedding_service() should return singleton."""
        from omni.foundation.services.embedding import get_embedding_service

        service1 = get_embedding_service()
        service2 = get_embedding_service()
        assert service1 is service2


class TestVectorStoreClient:
    """Tests for the VectorStoreClient."""

    def test_singleton_pattern(self):
        """VectorStoreClient should be a singleton."""
        from omni.foundation.services.vector import VectorStoreClient

        instance1 = VectorStoreClient()
        instance2 = VectorStoreClient()
        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_store_unavailable(self):
        """search() should return empty list when store not initialized."""
        from omni.foundation.services.vector import VectorStoreClient

        client = VectorStoreClient()
        client._store = None  # Simulate unavailable store

        with patch("omni.foundation.services.vector._get_omni_vector", return_value=None):
            result = await client.search("test query")
            assert result == []

    @pytest.mark.asyncio
    async def test_add_returns_false_when_store_unavailable(self):
        """add() should return False when store not initialized."""
        from omni.foundation.services.vector import VectorStoreClient

        client = VectorStoreClient()
        client._store = None

        with patch("omni.foundation.services.vector._get_omni_vector", return_value=None):
            result = await client.add("test content")
            assert result is False

    @pytest.mark.asyncio
    async def test_count_returns_zero_when_store_unavailable(self):
        """count() should return 0 when store not initialized."""
        from omni.foundation.services.vector import VectorStoreClient

        client = VectorStoreClient()
        client._store = None

        with patch("omni.foundation.services.vector._get_omni_vector", return_value=None):
            result = await client.count()
            assert result == 0

    def test_path_property(self):
        """path property should return Path object."""
        from omni.foundation.services.vector import VectorStoreClient

        client = VectorStoreClient()
        from pathlib import Path

        assert isinstance(client.path, Path)


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_search_result_creation(self):
        """SearchResult should store all fields."""
        from omni.foundation.services.vector import SearchResult

        result = SearchResult(
            content="test content", metadata={"source": "test.md"}, distance=0.1, id="doc_12345"
        )
        assert result.content == "test content"
        assert result.metadata == {"source": "test.md"}
        assert result.distance == 0.1
        assert result.id == "doc_12345"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_search_knowledge(self):
        """search_knowledge() should search default collection."""
        from omni.foundation.services.vector import search_knowledge

        with patch("omni.foundation.services.vector.get_vector_store") as mock_get:
            mock_store = AsyncMock()
            mock_store.search = AsyncMock(return_value=[])
            mock_get.return_value = mock_store

            result = await search_knowledge("test query", n_results=5)
            mock_store.search.assert_called_once_with("test query", 5, collection="knowledge")

    @pytest.mark.asyncio
    async def test_add_knowledge(self):
        """add_knowledge() should add to default collection."""
        from omni.foundation.services.vector import add_knowledge

        with patch("omni.foundation.services.vector.get_vector_store") as mock_get:
            mock_store = AsyncMock()
            mock_store.add = AsyncMock(return_value=True)
            mock_get.return_value = mock_store

            result = await add_knowledge("test content", {"key": "value"})
            mock_store.add.assert_called_once_with(
                "test content", {"key": "value"}, collection="knowledge"
            )
