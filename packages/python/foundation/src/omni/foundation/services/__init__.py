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

from .vector import VectorStoreClient
from .embedding import get_embedding_service, embed_text, embed_batch

__all__ = [
    "VectorStoreClient",
    "get_embedding_service",
    "embed_text",
    "embed_batch",
]
