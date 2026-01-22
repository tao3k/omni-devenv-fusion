# tests/unit/services/test_embed.py
"""
Unit tests for embedding module.
"""

import pytest

from omni.foundation.services.embedding import (
    _simple_embed,
    batch_embed,
    embed_query,
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
        emb = _simple_embed("test", dimension=1536)
        assert len(emb) == 1536

    def test_embedding_values_in_range(self):
        """Embedding values should be in 0-1 range."""
        emb = _simple_embed("test query")
        assert all(0.0 <= v <= 1.0 for v in emb)

    def test_empty_text(self):
        """Empty text should produce embedding."""
        emb = _simple_embed("")
        assert len(emb) == 1536

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
        result = embed_query("test query")
        assert result is not None
        assert len(result) == 1536


class TestBatchEmbed:
    """Tests for batch_embed function."""

    def test_batch_embed_empty_list(self):
        """batch_embed should return empty list for empty input."""
        result = batch_embed([])
        assert result == []

    def test_batch_embed_single_text(self):
        """batch_embed should handle single text."""
        result = batch_embed(["test"])
        assert len(result) == 1
        assert len(result[0]) == 1536

    def test_batch_embed_multiple_texts(self):
        """batch_embed should handle multiple texts."""
        texts = ["test 1", "test 2", "test 3"]
        result = batch_embed(texts)
        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1536

    def test_batch_embed_same_texts_produce_same_embeddings(self):
        """Same texts should produce identical embeddings."""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
