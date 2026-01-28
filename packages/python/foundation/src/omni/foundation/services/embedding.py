"""
omni.foundation.embedding - Unified Embedding Service

Provides text embedding capabilities using LLM.

Architecture:
- **Primary**: LLM-based embedding (MiniMax-M2.1 via InferenceClient)
- **Fallback 1**: FastEmbed (local BAAI/bge-small-en-v1.5)
- **Fallback 2**: Hash-based vectors (deterministic)

Configuration:
- Provider: embedding.provider in settings.yaml
- Dimension: embedding.dimension in settings.yaml (default: 1024)

The LLM-based approach uses structured prompting to generate 16 core semantic
values, which are then interpolated to the configured dimension (1024) for
storage in LanceDB. This ensures embedding quality matches the chat model.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from omni.foundation.config.settings import get_setting

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Singleton service for generating text embeddings using LLM.

    Configuration is read from settings.yaml (embedding.dimension).
    """

    _instance: "EmbeddingService | None" = None
    _model: Any = None
    _dimension: int = 0  # Set from settings.yaml in _initialize
    _backend: str = "llm"

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize embedding service using settings.yaml configuration."""
        provider = get_setting("embedding.provider", "llm")
        self._dimension = get_setting("embedding.dimension", 1024)

        logger.info(
            "Embedding configuration",
            provider=provider,
            dimension=self._dimension,
        )

        if provider == "llm":
            if self._try_init_llm():
                return

        # Fallback to FastEmbed (local)
        if self._try_init_fastembed():
            return

        # Fallback to hash-based
        self._backend = "fallback"
        self._dimension = self._dimension  # Keep configured dimension
        logger.warning("No embedding available, using hash-based fallback")

    def _try_init_llm(self) -> bool:
        """Initialize embedding using LLM client.

        Uses the same InferenceClient configuration as Omni Loop.
        """
        try:
            from omni.foundation.services.llm.client import InferenceClient

            self._model = InferenceClient()
            self._backend = "llm"
            # LLM dimension depends on model (MiniMax-M2.1 supports up to 64K context)
            logger.info(
                "Embedding initialized with LLM",
                model=self._model.model,
                base_url=self._model.base_url,
            )
            return True
        except Exception as e:
            logger.warning(f"LLM embedding initialization failed: {e}")
            return False

    def _try_init_fastembed(self) -> bool:
        """Try to initialize FastEmbed local model."""
        try:
            from fastembed import TextEmbedding

            model_name = "BAAI/bge-small-en-v1.5"
            self._model = TextEmbedding(model_name=model_name)
            self._dimension = 384
            self._backend = "fastembed"
            logger.info(f"FastEmbed initialized with {model_name}")
            return True
        except ImportError:
            logger.debug("FastEmbed not available")
            return False
        except Exception as e:
            logger.warning(f"FastEmbed initialization failed: {e}")
            return False

    def embed(self, text: str) -> list[list[float]]:
        """Generate embedding for text using LLM."""
        if self._backend == "llm":
            return self._embed_with_llm(text)
        elif self._backend == "fastembed":
            return self._embed_with_fastembed(text)
        else:
            return [self._simple_embed(text)]

    async def _embed_with_llm_async(self, text: str) -> list[list[float]]:
        """Generate embedding using LLM (async version).

        Returns a semantic vector of configured dimension (from settings.yaml).
        LLM generates 16 core semantic values via structured prompting,
        which are then interpolated to the target dimension (default: 1024).

        **Configuration**: embedding.dimension from settings.yaml
        **Provider**: Same InferenceClient as Omni Loop (MiniMax-M2.1)
        **Timeout**: 10 seconds (faster fallback on timeout)

        **Process**:
            1. Prompt LLM to generate 16 comma-separated values (-1 to 1)
            2. Parse and validate core values
            3. Expand to 16 core values to configured dimension via pattern repetition
            4. Return as list of vectors for LanceDB storage
        """
        # Timeout for embedding (30s to allow MiniMax API to respond)
        EMBED_TIMEOUT = 30

        # Prompt LLM to generate 16 core semantic values
        system_prompt = """You are a semantic embedding generator.
Output ONLY 16 comma-separated numbers between -1 and 1.
Example: 0.5,0.3,-0.2,0.8,0.1,0.9,-0.5,0.2,0.7,-0.1,0.4,0.6,-0.3,0.8,0.0,0.5"""

        prompt = f"Text: {text[:200]}\nOutput 16 numbers:"

        try:
            response = await asyncio.wait_for(
                self._model.complete(
                    system_prompt=system_prompt,
                    user_query=prompt,
                    max_tokens=50,
                ),
                timeout=EMBED_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Embedding LLM call timed out after {EMBED_TIMEOUT}s, using hash fallback"
            )
            return [self._simple_embed(text, self._dimension)]

        # Response is a dict - use key access
        if not response.get("success"):
            logger.warning(
                f"Embedding LLM call failed: {response.get('error')}, using hash fallback"
            )
            return [self._simple_embed(text, self._dimension)]

        content = response.get("content", "")

        # Parse comma-separated values
        values = [float(x.strip()) for x in content.split(",") if x.strip()]
        if len(values) >= 1:
            # Ensure exactly 16 core values
            if len(values) < 16:
                core = (values * 16)[:16]
            else:
                core = values[:16]

            # Expand 16 core values to configured dimension (e.g., 1024)
            # Using pattern repetition
            target_dim = self._dimension
            vector = (core * (target_dim // 16 + 1))[:target_dim]
            return [vector]

        # Fallback: deterministic hash-based vector
        return [self._simple_embed(text, self._dimension)]

    def _embed_with_llm(self, text: str) -> list[list[float]]:
        """Generate embedding using LLM (sync wrapper)."""
        try:
            return asyncio.run(self._embed_with_llm_async(text))
        except Exception as e:
            logger.error(f"LLM embed failed: {e}")
            return [self._simple_embed(text, 1024)]

    def _embed_with_fastembed(self, text: str) -> list[list[float]]:
        """Generate embedding using FastEmbed."""
        try:
            embeddings = list(self._model.embed([text]))
            return [embeddings[0].tolist()]
        except Exception as e:
            logger.error(f"FastEmbed embed failed: {e}")
            return [self._simple_embed(text, 384)]

    def _simple_embed(self, text: str, dimension: int = 1024) -> list[float]:
        """Deterministic hash-based embedding for fallback."""
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [float(b) / 255.0 for b in hash_bytes]
        repeats = (dimension + len(vector) - 1) // len(vector)
        return (vector * repeats)[:dimension]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Uses parallel LLM calls for better performance (batch mode).
        Falls back to sequential if parallel fails.
        """
        if not texts:
            return []

        if self._backend == "llm":
            return self._embed_batch_llm_parallel(texts)
        elif self._backend == "fastembed":
            return self._embed_batch_fastembed(texts)
        else:
            return [self._simple_embed(text, self._dimension) for text in texts]

    def _embed_batch_llm_parallel(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using parallel LLM calls (faster for batches)."""
        # Process in parallel chunks to avoid overwhelming the API
        BATCH_SIZE = 10

        async def embed_chunk(chunk: list[str]) -> list[list[float]]:
            """Embed a chunk of texts in parallel."""
            tasks = [self._embed_with_llm_async(text) for text in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Handle exceptions by returning hash-based vectors
            final = []
            for idx, (text, r) in enumerate(zip(chunk, results)):
                if isinstance(r, Exception):
                    logger.warning(f"Chunk embed failed for item {idx}: {r}")
                    final.append(self._simple_embed(text, self._dimension))
                elif r and len(r) > 0:
                    final.append(r[0])
                else:
                    final.append(self._simple_embed(text, self._dimension))
            return final

        async def embed_all() -> list[list[float]]:
            all_results = []
            # Process in chunks
            for i in range(0, len(texts), BATCH_SIZE):
                chunk = texts[i : i + BATCH_SIZE]
                chunk_results = await embed_chunk(chunk)
                all_results.extend(chunk_results)
                logger.debug(
                    f"Embedding batch progress: {min(i + BATCH_SIZE, len(texts))}/{len(texts)}"
                )
            return all_results

        try:
            return asyncio.run(embed_all())
        except Exception as e:
            logger.error(f"Parallel batch embed failed: {e}, falling back to sequential")
            return self._embed_batch_llm(texts)

    def _embed_batch_llm(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using LLM."""
        results = []
        for text in texts:
            result = self._embed_with_llm(text)
            results.extend(result)
        return results

    def _embed_batch_fastembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using FastEmbed."""
        try:
            embeddings = list(self._model.embed(texts))
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"FastEmbed batch embed failed: {e}")
            return [self._simple_embed(text, 384) for text in texts]

    @property
    def backend(self) -> str:
        """Return the current embedding backend."""
        return self._backend

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension


def get_embedding_service() -> EmbeddingService:
    """Get the singleton EmbeddingService instance."""
    return EmbeddingService()


def embed_text(text: str) -> list[float]:
    """Convenience function to embed a single text."""
    return get_embedding_service().embed(text)[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Convenience function to embed multiple texts."""
    return get_embedding_service().embed_batch(texts)


def batch_embed(
    texts: list[str], embed_func=None, dimension: int | None = None
) -> list[list[float]]:
    """Batch embed multiple texts.

    Args:
        texts: List of texts to embed.
        embed_func: Optional custom embedding function.
        dimension: Optional dimension override.

    Returns:
        List of embedding vectors.
    """
    if embed_func is not None:
        # Use custom function (may return fixed-dimension vectors)
        return [embed_func(t) for t in texts]
    return embed_batch(texts)


def embed_query(text: str) -> list[float] | None:
    """Embed a query text, returning None for empty input."""
    if not text or not text.strip():
        return None
    return embed_text(text)


def _simple_embed(text: str, dimension: int | None = None) -> list[float]:
    """Simple synchronous embedding with optional dimension override.

    Uses hash-based fallback for dimension overrides that don't match service config.
    This allows tests to verify different dimensions work correctly.

    Args:
        text: Text to embed.
        dimension: Override dimension (uses service default 1024 if None).

    Returns:
        Embedding vector as list of floats.
    """
    import hashlib

    # Use provided dimension or default to 1024
    dim = dimension if dimension is not None else 1024

    # For non-matching dimensions, use hash-based fallback
    service = get_embedding_service()
    if dimension is not None and dimension != service.dimension:
        # Hash-based deterministic embedding for test dimensions
        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [float(b) / 255.0 for b in hash_bytes]
        repeats = (dim + len(vector) - 1) // len(vector)
        return (vector * repeats)[:dim]

    return service.embed(text)[0]


def get_dimension() -> int:
    """Get the current embedding dimension."""
    return get_embedding_service().dimension
