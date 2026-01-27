"""
omni.foundation.embedding - Unified Embedding Service

Provides text embedding capabilities for the entire system.

Supports multiple backends:
1. FastEmbed (local, default) - BAAI/bge-small-en-v1.5
2. OpenAI (cloud) - text-embedding-3-small
3. Fallback (hash-based) - for testing/offline mode
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Singleton service for generating text embeddings.

    Supports multiple backends with automatic fallback:
    1. FastEmbed (local neural embeddings)
    2. OpenAI (cloud API)
    3. Hash-based (fallback for testing)
    """

    _instance: "EmbeddingService | None" = None
    _model: Any = None
    _dimension: int = 1536
    _backend: str = "fallback"

    # Common embedding dimensions
    DIM_OPENAI_ADA_2 = 1536
    DIM_OPENAI_3_SMALL = 1536
    DIM_OPENAI_3_LARGE = 3072
    DIM_BGE_SMALL = 384

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the embedding model with automatic backend selection."""
        # Try FastEmbed first (local, no API key needed)
        if self._try_init_fastembed():
            return

        # Try OpenAI if API key is available
        if self._try_init_openai():
            return

        # Fall back to hash-based embedding
        self._backend = "fallback"
        self._dimension = self.DIM_OPENAI_ADA_2
        logger.warning("No embedding model available, using hash-based fallback")

    def _try_init_fastembed(self) -> bool:
        """Try to initialize FastEmbed local model.

        Returns:
            True if successful, False otherwise.
        """
        try:
            from fastembed import TextEmbedding

            # Use BGE small model - good balance of speed and quality
            # Alternative: "BAAI/bge-large-en-v1.5" for higher quality
            model_name = "BAAI/bge-small-en-v1.5"
            self._model = TextEmbedding(model_name=model_name)
            self._dimension = self.DIM_BGE_SMALL
            self._backend = "fastembed"
            logger.info(f"FastEmbed initialized with {model_name}")
            return True
        except ImportError:
            logger.debug("FastEmbed not available")
            return False
        except Exception as e:
            logger.warning(f"FastEmbed initialization failed: {e}")
            return False

    def _try_init_openai(self) -> bool:
        """Try to initialize OpenAI embedding API.

        Returns:
            True if successful, False otherwise.
        """
        import os

        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.debug("OpenAI API key not set")
                return False

            client = OpenAI(api_key=api_key)
            # Test connection with a simple call
            client.embeddings.create(
                model="text-embedding-3-small",
                input="test",
            )
            self._model = client
            self._dimension = self.DIM_OPENAI_3_SMALL
            self._backend = "openai"
            logger.info("OpenAI embedding API initialized")
            return True
        except ImportError:
            logger.debug("OpenAI client not available")
            return False
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")
            return False

    @property
    def backend(self) -> str:
        """Return the current embedding backend."""
        return self._backend

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
        if self._backend == "fastembed":
            return self._embed_fastembed(text)
        elif self._backend == "openai":
            return self._embed_openai(text)
        else:
            return [self._simple_embed(text)]

    def _embed_fastembed(self, text: str) -> list[list[float]]:
        """Generate embedding using FastEmbed.

        Args:
            text: Input text to embed.

        Returns:
            List containing a single embedding vector.
        """
        try:
            # FastEmbed returns iterable of documents with embedding
            embeddings = list(self._model.embed([text]))
            return [embeddings[0].tolist()]
        except Exception as e:
            logger.error(f"FastEmbed embed failed: {e}")
            return [self._simple_embed(text)]

    def _embed_openai(self, text: str) -> list[list[float]]:
        """Generate embedding using OpenAI API.

        Args:
            text: Input text to embed.

        Returns:
            List containing a single embedding vector.
        """
        try:
            response = self._model.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return [d.embedding for d in response.data]
        except Exception as e:
            logger.error(f"OpenAI embed failed: {e}")
            return [self._simple_embed(text)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        if self._backend == "fastembed":
            return self._embed_batch_fastembed(texts)
        elif self._backend == "openai":
            return self._embed_batch_openai(texts)
        else:
            return [self._simple_embed(text) for text in texts]

    def _embed_batch_fastembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using FastEmbed.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        try:
            embeddings = list(self._model.embed(texts))
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"FastEmbed batch embed failed: {e}")
            return [self._simple_embed(text) for text in texts]

    def _embed_batch_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using OpenAI API.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        try:
            # OpenAI has a limit of 2048 texts per request
            BATCH_SIZE = 2048
            all_embeddings = []

            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i : i + BATCH_SIZE]
                response = self._model.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                )
                all_embeddings.extend([d.embedding for d in response.data])

            return all_embeddings
        except Exception as e:
            logger.error(f"OpenAI batch embed failed: {e}")
            return [self._simple_embed(text) for text in texts]

    def _simple_embed(self, text: str) -> list[float]:
        """Deterministic hash-based embedding for fallback/testing.

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
