# services
"""
AI & Storage Services Module

Provides high-performance services:
- vector.py: Vector storage and similarity search
- embedding.py: Text embedding generation

Usage:
    from omni.foundation.services.vector import VectorStoreClient
    from omni.foundation.services.embedding import get_embedding_service
"""

from .embedding import embed_batch, embed_text, get_embedding_service
from .vector import VectorStoreClient

__all__ = [
    "VectorStoreClient",
    "embed_batch",
    "embed_text",
    "get_embedding_service",
]
