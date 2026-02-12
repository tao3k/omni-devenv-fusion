"""
embedding/scripts/embed.py - Embedding generation commands

Wraps the unified embedding service for MCP skill access.
"""

import json
from typing import Any


def embed_texts(texts: list[str]) -> dict[str, Any]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of text strings to embed

    Returns:
        Dictionary with success status, vectors, count, and dimension
    """
    from omni.foundation.services.embedding import embed_batch, get_embedding_service

    try:
        embed_service = get_embedding_service()
        vectors = embed_batch(texts)

        return {
            "success": True,
            "vectors": vectors,
            "count": len(vectors),
            "dimension": embed_service.dimension,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "vectors": [],
            "count": 0,
        }


def embed_single(text: str) -> dict[str, Any]:
    """Generate embedding for a single text.

    Args:
        text: Text string to embed

    Returns:
        Dictionary with success status, vector, and dimension
    """
    from omni.foundation.services.embedding import embed_text, get_embedding_service

    try:
        embed_service = get_embedding_service()
        vector = embed_text(text)

        return {
            "success": True,
            "vector": vector,
            "dimension": embed_service.dimension,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "vector": [],
        }


def batch_embed_from_json(json_text: str) -> dict[str, Any]:
    """Generate embeddings from JSON array of texts.

    Args:
        json_text: JSON string containing array of texts

    Returns:
        Dictionary with success status and vectors
    """
    try:
        texts = json.loads(json_text)
        if not isinstance(texts, list):
            return {
                "success": False,
                "error": "Input must be a JSON array of strings",
            }

        result = embed_texts(texts)
        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON: {e}",
        }


def get_embedding_info() -> dict[str, Any]:
    """Get information about the embedding service.

    Returns:
        Dictionary with dimension, backend, and model info
    """
    from omni.foundation.services.embedding import get_embedding_service

    embed_service = get_embedding_service()
    return {
        "dimension": embed_service.dimension,
        "backend": embed_service.backend,
        "is_loaded": embed_service.is_loaded,
        "model": "Qwen/Qwen3-Embedding-4B",
    }
