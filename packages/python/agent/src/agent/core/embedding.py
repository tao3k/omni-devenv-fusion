"""
agent/core/embedding.py
 The Encoder - High-performance Text Embedding.

Provides semantic text embedding using FastEmbed (local) or OpenAI API.
Used by Memory Skill and other components for semantic search.

Philosophy:
- FastEmbed first (local, privacy-preserving, zero cost)
- OpenAI fallback (cloud, higher quality)
- Lazy loading to avoid slow startup
"""

from __future__ import annotations

import os
from typing import List, Union, Optional

import structlog

logger = structlog.get_logger(__name__)

# Lazy loading
_cached_fastembed: Optional[type] = None
_cached_openai: Optional[type] = None
_cached_service: Optional["EmbeddingService"] = None

# Model configurations
FASTEMBED_MODELS = {
    "bge-small": "BAAI/bge-small-en-v1.5",  # 384 dimensions
    "bge-base": "BAAI/bge-base-en-v1.5",  # 768 dimensions
    "multilingual-e5": "intfloat/multilingual-e5-large",  # 1024 dimensions
    "bge-m3": "BAAI/bge-m3",  # 1024 dimensions
}

# Default model
DEFAULT_MODEL = "bge-small"
DEFAULT_DIMENSION = 384  # BGE-small dimension


class EmbeddingService:
    """
    Unified interface for text embeddings.

    Priority:
    1. FastEmbed (local ONNX) - Zero cost, fast, privacy-preserving
    2. OpenAI API - Higher quality, cloud-based

    Usage:
        from agent.core.embedding import get_embedding_service

        service = get_embedding_service()
        vectors = service.embed(["hello world", "text to encode"])
    """

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[str] = None
    _provider: Optional[str] = None
    _dimension: Optional[int] = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._provider = self._detect_provider()
        self._model = self._load_model()
        self._initialized = True

        logger.info(
            "Embedding service initialized",
            provider=self._provider,
            model=self._model,
            dimension=self._dimension,
        )

    def _detect_provider(self) -> str:
        """Detect which embedding provider to use."""
        # Check environment variable override
        override = os.getenv("OMNI_EMBEDDING_PROVIDER", "").lower()
        if override in ("fastembed", "openai"):
            return override

        # Default to fastembed for local, privacy-preserving operation
        return "fastembed"

    def _load_model(self) -> str:
        """Load the embedding model and return model name."""
        model_name = os.getenv("OMNI_EMBEDDING_MODEL", DEFAULT_MODEL)

        if self._provider == "fastembed":
            return self._load_fastembed(model_name)
        elif self._provider == "openai":
            return model_name
        else:
            raise ValueError(f"Unknown provider: {self._provider}")

    def _load_fastembed(self, model_key: str) -> str:
        """Load FastEmbed model."""
        global _cached_fastembed

        if _cached_fastembed is None:
            try:
                from fastembed import TextEmbedding

                _cached_fastembed = TextEmbedding
            except ImportError:
                logger.error("fastembed not installed. Install with: pip install fastembed")
                raise ImportError(
                    "fastembed required for local embedding. Install via: pip install fastembed"
                )

        # Resolve model name from key or use directly
        model_name = FASTEMBED_MODELS.get(model_key, model_key)

        # Initialize the model
        try:
            model_instance = _cached_fastembed(model_name=model_name)
            # Get dimension from model - try new API first, then fallback
            try:
                # New FastEmbed API
                self._dimension = model_instance.model.get_default_dimensions()
            except AttributeError:
                # Fallback to known dimensions
                if "small" in model_name.lower():
                    self._dimension = 384
                elif "base" in model_name.lower():
                    self._dimension = 768
                else:
                    self._dimension = 1024  # Large models
            return model_name
        except Exception as e:
            logger.error(f"Failed to load FastEmbed model: {model_name}", error=str(e))
            raise

    def _load_openai(self) -> str:
        """Initialize OpenAI client."""
        global _cached_openai

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Set it in environment or .env file.")

        if _cached_openai is None:
            from openai import OpenAI

            _cached_openai = OpenAI(api_key=api_key)

        self._dimension = 1536  # OpenAI text-embedding-3-small/large
        return "text-embedding-3-small"

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for text(s).

        Args:
            texts: Single text or list of texts to embed

        Returns:
            List of embedding vectors (each vector is List[float])
        """
        if isinstance(texts, str):
            texts = [texts]

        if self._provider == "fastembed":
            return self._embed_fastembed(texts)
        elif self._provider == "openai":
            return self._embed_openai(texts)
        else:
            raise ValueError(f"Unknown provider: {self._provider}")

    def _embed_fastembed(self, texts: List[str]) -> List[List[float]]:
        """Embed using FastEmbed (local ONNX)."""
        global _cached_fastembed

        if _cached_fastembed is None:
            raise RuntimeError("FastEmbed not initialized")

        model = _cached_fastembed(model_name=self._model)

        # FastEmbed returns a generator
        embeddings = list(model.embed(texts))

        # Convert numpy arrays to float lists
        return [e.tolist() for e in embeddings]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Embed using OpenAI API."""
        global _cached_openai

        if _cached_openai is None:
            self._load_openai()

        client = _cached_openai

        response = client.embeddings.create(
            input=texts,
            model=self._model or "text-embedding-3-small",
        )

        return [data.embedding for data in response.data]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if self._dimension is None:
            return DEFAULT_DIMENSION
        return self._dimension

    @property
    def provider(self) -> str:
        """Get the current provider."""
        return self._provider or "unknown"


def get_embedding_service() -> EmbeddingService:
    """
    Get the global embedding service singleton.

    Returns:
        EmbeddingService instance (FastEmbed or OpenAI)
    """
    global _cached_service
    if _cached_service is None:
        _cached_service = EmbeddingService()
    return _cached_service


def embed_text(text: str) -> List[float]:
    """
    Convenience function to embed a single text.

    Args:
        text: Text to embed

    Returns:
        Embedding vector
    """
    service = get_embedding_service()
    return service.embed(text)[0]


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to embed multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    return get_embedding_service().embed(texts)


def get_dimension() -> int:
    """Get the current embedding dimension."""
    return get_embedding_service().dimension


# For backward compatibility with Dummy embedding
class DummyEmbedding:
    """Dummy embedding for testing when real embedding is unavailable."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Generate deterministic dummy vector from text hash."""
        import hashlib

        # Create deterministic seed from text
        hash_obj = hashlib.md5(text.encode(), usedforsecurity=False)
        seed = int(hash_obj.hexdigest()[:8], 16) % 1000

        # Generate consistent vector
        import random

        random.seed(seed)
        return [random.uniform(-1, 1) for _ in range(self.dimension)]


__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "embed_text",
    "embed_batch",
    "get_dimension",
    "DEFAULT_DIMENSION",
    "DummyEmbedding",
]
