# tests/unit/services/test_embed.py
"""
Unit tests for embedding module.

Note: Tests use mocking to avoid depending on actual embedding backends
(FastEmbed, OpenAI) which may have different dimensions.
"""

import pytest
from unittest.mock import patch, MagicMock

from omni.foundation.services.embedding import (
    _simple_embed,
    batch_embed,
    embed_query,
    get_embedding_service,
)


class TestSimpleEmbed:
    """Tests for _simple_embed function."""

    def test_same_text_produces_same_embedding(self):
        """Same text should produce identical embeddings."""
        text = "test query"
        emb1 = _simple_embed(text)
        emb2 = _simple_embed(text)
        assert emb1 == emb2

    def test_different_text_produces_different_embedding(self):
        """Different texts should produce different embeddings."""
        emb1 = _simple_embed("test query 1")
        emb2 = _simple_embed("test query 2")
        assert emb1 != emb2

    def test_embedding_dimension(self):
        """Embedding should have correct dimension."""
        from omni.foundation.config.settings import get_setting

        expected_dim = get_setting("embedding.dimension", 1024)
        emb = _simple_embed("test", dimension=expected_dim)
        assert len(emb) == expected_dim

    def test_embedding_values_in_range(self):
        """Embedding values should be in 0-1 range."""
        emb = _simple_embed("test query")
        assert all(0.0 <= v <= 1.0 for v in emb)

    def test_empty_text(self):
        """Empty text should produce embedding."""
        emb = _simple_embed("")
        # Uses default dimension from settings.yaml
        from omni.foundation.config.settings import get_setting

        expected_dim = get_setting("embedding.dimension", 1024)
        assert len(emb) == expected_dim

    def test_custom_dimension(self):
        """Custom dimension should be respected."""
        emb = _simple_embed("test", dimension=768)
        assert len(emb) == 768


class TestEmbedQuery:
    """Tests for embed_query function."""

    def test_embed_query_returns_list(self):
        """embed_query should return a list."""
        result = embed_query("test query")
        assert isinstance(result, list)

    def test_embed_query_returns_none_for_empty(self):
        """embed_query should return None for empty query."""
        result = embed_query("")
        assert result is None

    def test_embed_query_with_text(self):
        """embed_query should return embedding for non-empty text."""
        # Mock the embedding service to avoid backend dependencies
        mock_service = MagicMock()
        mock_service.embed.return_value = [[0.1] * 384]
        mock_service._dimension = 384

        with patch(
            "omni.foundation.services.embedding.get_embedding_service", return_value=mock_service
        ):
            result = embed_query("test query")
            assert result is not None
            assert len(result) == 384  # Mock dimension


class TestBatchEmbed:
    """Tests for batch_embed function."""

    def test_batch_embed_empty_list(self):
        """batch_embed should return empty list for empty input."""
        result = batch_embed([])
        assert result == []

    def test_batch_embed_single_text(self):
        """batch_embed should handle single text."""
        # Mock the embedding service
        mock_service = MagicMock()
        mock_service.embed_batch.return_value = [[0.1] * 384]
        mock_service._dimension = 384

        with patch(
            "omni.foundation.services.embedding.get_embedding_service", return_value=mock_service
        ):
            result = batch_embed(["test"])
            assert len(result) == 1
            assert len(result[0]) == 384  # Mock dimension

    def test_batch_embed_multiple_texts(self):
        """batch_embed should handle multiple texts."""
        # Mock the embedding service
        mock_service = MagicMock()
        mock_service.embed_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        mock_service._dimension = 384

        with patch(
            "omni.foundation.services.embedding.get_embedding_service", return_value=mock_service
        ):
            texts = ["test 1", "test 2", "test 3"]
            result = batch_embed(texts)
            assert len(result) == 3
            for emb in result:
                assert len(emb) == 384  # Mock dimension

    def test_batch_embed_same_texts_produce_same_embeddings(self):
        """Same texts should produce identical embeddings when using mocked service."""
        # Mock the embedding service to return consistent results
        mock_service = MagicMock()
        mock_service.embed_batch.return_value = [[0.1] * 384, [0.1] * 384]
        mock_service._dimension = 384

        with patch(
            "omni.foundation.services.embedding.get_embedding_service", return_value=mock_service
        ):
            texts = ["test", "test"]
            result = batch_embed(texts)
            assert result[0] == result[1]

    def test_batch_embed_different_texts_produce_different_embeddings(self):
        """Different texts should produce different embeddings."""
        texts = ["text 1", "text 2"]
        result = batch_embed(texts)
        assert result[0] != result[1]

    def test_batch_embed_with_custom_embed_func(self):
        """batch_embed should use custom embed function if provided."""
        custom_calls = []

        def custom_embed(text):
            custom_calls.append(text)
            return [1.0] * 768

        texts = ["a", "b", "c"]
        result = batch_embed(texts, embed_func=custom_embed, dimension=768)

        assert len(result) == 3
        # ThreadPoolExecutor may not preserve order, so check all texts were called
        assert set(custom_calls) == set(texts)
        for emb in result:
            assert emb == [1.0] * 768


class TestEmbeddingServiceDimension:
    """Tests for embedding service dimension handling."""

    def test_dimension_reflects_backend(self):
        """Service dimension should match the initialized backend."""
        service = get_embedding_service()
        from omni.foundation.config.settings import get_setting

        expected_dim = get_setting("embedding.dimension", 1024)
        # Dimension should match settings.yaml or be a valid fallback
        valid_dimensions = [384, expected_dim, 1536, 3072]  # FastEmbed, LLM, OpenAI variants
        assert service.dimension in valid_dimensions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
