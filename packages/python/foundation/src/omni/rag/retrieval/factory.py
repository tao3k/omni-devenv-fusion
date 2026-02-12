"""Backend factory for retrieval namespace."""

from __future__ import annotations

from typing import Any

from .hybrid import HybridRetrievalBackend
from .interface import RetrievalBackend
from .lancedb import LanceRetrievalBackend


def create_retrieval_backend(
    kind: str,
    *,
    vector_client: Any | None = None,
) -> RetrievalBackend:
    """Create a retrieval backend by kind.

    Supported kinds: lance, hybrid
    """
    name = kind.strip().lower()
    if name == "lance":
        return LanceRetrievalBackend(vector_client=vector_client)
    if name == "hybrid":
        vector_backend = LanceRetrievalBackend(vector_client=vector_client)
        return HybridRetrievalBackend(vector_backend)
    raise ValueError(f"Unsupported retrieval backend kind: {kind}")


__all__ = [
    "create_retrieval_backend",
]
