"""Tests for retrieval LangGraph node factory."""

from __future__ import annotations

import pytest

from omni.rag import RetrievalConfig, RetrievalResult, create_retriever_node, create_hybrid_node


class _Backend:
    async def search(self, query: str, config: RetrievalConfig):
        assert query == "typed"
        assert config.collection == "knowledge"
        return [
            RetrievalResult(id="a", content="alpha", score=0.9, metadata={"k": 1}, source="vector")
        ]


@pytest.mark.asyncio
async def test_create_retriever_node_writes_results_to_state():
    node = create_retriever_node(
        _Backend(),
        query_key="query",
        output_key="retrieval_results",
        config=RetrievalConfig(collection="knowledge", top_k=5),
    )
    out = await node({"query": "typed"})
    assert out["retrieval_results"][0]["id"] == "a"
    assert out["retrieval_results"][0]["score"] == 0.9


@pytest.mark.asyncio
async def test_create_hybrid_node_alias():
    node = create_hybrid_node(
        _Backend(),
        query_key="query",
        output_key="hybrid_results",
        config=RetrievalConfig(collection="knowledge", top_k=5),
    )
    out = await node({"query": "typed"})
    assert out["hybrid_results"][0]["source"] == "vector"
