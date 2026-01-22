"""
omni.foundation.embedding - Unified Embedding Service

Provides text embedding capabilities for the entire system.
"""

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Singleton service for generating text embeddings."""

    _instance = None
    _model = None
    _dimension = 1536  # Default fallback

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    def embed(self, text: str) -> list[list[float]]:
        """Generate embedding for text.

        Args:
            text: Input text to embed.

        Returns:
            List containing a single embedding vector.
        """
        # TODO: Integrate with actual model (OpenAI/FastEmbed)
        # For now, migrating the simple deterministic fallback to ensure system stability
        return [self._simple_embed(text)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        return [self.embed(text)[0] for text in texts]

    def _simple_embed(self, text: str) -> list[float]:
        """Deterministic dummy embedding for testing/fallback.

        Creates a consistent embedding based on the SHA256 hash of the text.
        This is useful for testing and as a fallback when no model is available.

        Args:
            text: Input text.

        Returns:
            A fixed-dimension embedding vector.
        """
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [float(b) / 255.0 for b in hash_bytes]
        repeats = (self._dimension + len(vector) - 1) // len(vector)
        return (vector * repeats)[: self._dimension]


def get_embedding_service() -> EmbeddingService:
    """Get the singleton EmbeddingService instance.

    Returns:
        The global EmbeddingService singleton.
    """
    return EmbeddingService()


def embed_text(text: str) -> list[float]:
    """Convenience function to embed a single text.

    Args:
        text: Input text.

    Returns:
        Embedding vector.
    """
    return get_embedding_service().embed(text)[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Convenience function to embed multiple texts.

    Args:
        texts: List of input texts.

    Returns:
        List of embedding vectors.
    """
    return get_embedding_service().embed_batch(texts)


def get_dimension() -> int:
    """Get the current embedding dimension.

    Returns:
        The embedding dimension.
    """
    return get_embedding_service().dimension


# Standalone convenience functions for tests and simple usage
def _simple_embed(text: str, dimension: int = 1536) -> list[float]:
    """Deterministic dummy embedding for testing/fallback.

    Creates a consistent embedding based on the SHA256 hash of the text.

    Args:
        text: Input text.
        dimension: Embedding dimension (default 1536).

    Returns:
        A fixed-dimension embedding vector.
    """
    import hashlib

    hash_bytes = hashlib.sha256(text.encode()).digest()
    vector = [float(b) / 255.0 for b in hash_bytes]
    repeats = (dimension + len(vector) - 1) // len(vector)
    return (vector * repeats)[:dimension]


def embed_query(text: str) -> list[float] | None:
    """Embed a query string.

    Args:
        text: Query text.

    Returns:
        Embedding vector, or None if text is empty.
    """
    if not text:
        return None
    return embed_text(text)


def batch_embed(texts: list[str], embed_func=None, dimension: int = 1536) -> list[list[float]]:
    """Embed multiple texts in batch.

    Args:
        texts: List of input texts.
        embed_func: Optional custom embed function.
        dimension: Embedding dimension.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []

    if embed_func is not None:
        return [embed_func(text) for text in texts]

    service = get_embedding_service()
    original_dim = service._dimension
    service._dimension = dimension
    try:
        return service.embed_batch(texts)
    finally:
        service._dimension = original_dim
