"""LangGraph retrieval node factory."""

from __future__ import annotations

from typing import Any

from .interface import RetrievalBackend, RetrievalConfig


def create_retriever_node(
    backend: RetrievalBackend,
    *,
    query_key: str = "query",
    output_key: str = "retrieval_results",
    config: RetrievalConfig | None = None,
):
    """Create a LangGraph-compatible retriever node function."""

    async def node(state: dict[str, Any]) -> dict[str, Any]:
        cfg = config or RetrievalConfig()
        query = str(state.get(query_key, "")).strip()
        results = await backend.search(query, cfg)
        new_state = dict(state)
        new_state[output_key] = [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
                "source": r.source,
            }
            for r in results
        ]
        return new_state

    return node


def create_hybrid_node(
    backend: RetrievalBackend,
    *,
    query_key: str = "query",
    output_key: str = "hybrid_results",
    config: RetrievalConfig | None = None,
):
    """Alias factory for semantically explicit hybrid retrieval nodes."""
    return create_retriever_node(
        backend,
        query_key=query_key,
        output_key=output_key,
        config=config,
    )


__all__ = [
    "create_retriever_node",
    "create_hybrid_node",
]
