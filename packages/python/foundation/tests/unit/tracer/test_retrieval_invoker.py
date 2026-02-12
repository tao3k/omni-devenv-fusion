"""
test_retrieval_invoker.py - Unit tests for RetrievalToolInvoker.
"""

from __future__ import annotations

import pytest

from omni.rag import RetrievalResult
from omni.tracer import RetrievalToolInvoker


class _StaticBackend:
    def __init__(self, results: list[RetrievalResult] | None = None, stored: int = 0):
        self.results = results or []
        self.stored = stored
        self.search_calls = []
        self.index_calls = []

    async def search(self, query, config):
        self.search_calls.append((query, config.collection, config.top_k, config.score_threshold))
        return self.results

    async def index(self, documents, collection):
        self.index_calls.append((documents, collection))
        return self.stored

    async def get_stats(self, collection):
        return {"collection": collection}


@pytest.mark.asyncio
async def test_retrieval_invoker_search():
    vector = _StaticBackend(
        results=[RetrievalResult(id="a", content="alpha", score=0.9, source="vector")]
    )
    invoker = RetrievalToolInvoker(vector_backend=vector, hybrid_backend=_StaticBackend())
    out = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed", "collection": "knowledge", "top_k": 5},
        state={},
    )
    assert out["count"] == 1
    assert out["results"][0]["id"] == "a"
    assert vector.search_calls[0][0] == "typed"


@pytest.mark.asyncio
async def test_retrieval_invoker_hybrid_search_uses_hybrid_backend():
    hybrid = _StaticBackend(
        results=[RetrievalResult(id="h1", content="hybrid", score=0.5, source="hybrid")]
    )
    invoker = RetrievalToolInvoker(vector_backend=_StaticBackend(), hybrid_backend=hybrid)
    out = await invoker.invoke(
        server="retriever",
        tool="hybrid_search",
        payload={"query": "typed"},
        state={},
    )
    assert out["results"][0]["id"] == "h1"
    assert len(hybrid.search_calls) == 1


@pytest.mark.asyncio
async def test_retrieval_invoker_search_can_override_backend_to_hybrid():
    hybrid = _StaticBackend(
        results=[RetrievalResult(id="h1", content="hybrid", score=0.4, source="hybrid")]
    )
    invoker = RetrievalToolInvoker(
        vector_backend=_StaticBackend(),
        hybrid_backend=hybrid,
    )
    out = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed", "backend": "hybrid"},
        state={},
    )
    assert out["results"][0]["id"] == "h1"
    assert len(hybrid.search_calls) == 1


@pytest.mark.asyncio
async def test_retrieval_invoker_uses_default_backend_when_not_overridden():
    hybrid = _StaticBackend(
        results=[RetrievalResult(id="h2", content="hybrid", score=0.6, source="hybrid")]
    )
    invoker = RetrievalToolInvoker(
        vector_backend=_StaticBackend(),
        hybrid_backend=hybrid,
        default_backend="hybrid",
    )
    out = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed"},
        state={},
    )
    assert out["results"][0]["id"] == "h2"
    assert len(hybrid.search_calls) == 1


@pytest.mark.asyncio
async def test_retrieval_invoker_index():
    vector = _StaticBackend(stored=3)
    invoker = RetrievalToolInvoker(vector_backend=vector, hybrid_backend=_StaticBackend())
    out = await invoker.invoke(
        server="retriever",
        tool="index",
        payload={"documents": [{"content": "a"}, {"content": "b"}], "collection": "knowledge"},
        state={},
    )
    assert out["stored"] == 3
    assert len(vector.index_calls) == 1


@pytest.mark.asyncio
async def test_retrieval_invoker_get_stats():
    vector = _StaticBackend(stored=0)
    invoker = RetrievalToolInvoker(vector_backend=vector, hybrid_backend=_StaticBackend())
    out = await invoker.invoke(
        server="retriever",
        tool="get_stats",
        payload={"collection": "knowledge"},
        state={},
    )
    assert out["stats"]["collection"] == "knowledge"


@pytest.mark.asyncio
async def test_retrieval_invoker_get_stats_can_override_backend():
    hybrid = _StaticBackend(stored=0)
    invoker = RetrievalToolInvoker(
        vector_backend=_StaticBackend(),
        hybrid_backend=hybrid,
    )
    out = await invoker.invoke(
        server="retriever",
        tool="get_stats",
        payload={"collection": "knowledge", "backend": "hybrid"},
        state={},
    )
    assert out["stats"]["collection"] == "knowledge"


@pytest.mark.asyncio
async def test_retrieval_invoker_rejects_unsupported_backend_selection():
    invoker = RetrievalToolInvoker(vector_backend=_StaticBackend(), hybrid_backend=_StaticBackend())
    with pytest.raises(ValueError, match="Unsupported retrieval backend selection"):
        await invoker.invoke(
            server="retriever",
            tool="search",
            payload={"query": "typed", "backend": "qdrant"},
            state={},
        )


@pytest.mark.asyncio
async def test_retrieval_invoker_rejects_legacy_backend_aliases():
    invoker = RetrievalToolInvoker(vector_backend=_StaticBackend(), hybrid_backend=_StaticBackend())
    with pytest.raises(ValueError, match="Unsupported retrieval backend selection"):
        await invoker.invoke(
            server="retriever",
            tool="search",
            payload={"query": "typed", "backend": "lancedb"},
            state={},
        )


def test_retrieval_invoker_rejects_invalid_default_backend():
    with pytest.raises(ValueError, match="Unsupported retrieval default backend"):
        RetrievalToolInvoker(default_backend="vector")


@pytest.mark.asyncio
async def test_retrieval_invoker_non_retriever_returns_not_implemented():
    invoker = RetrievalToolInvoker(vector_backend=_StaticBackend(), hybrid_backend=_StaticBackend())
    out = await invoker.invoke(server="generator", tool="analyze", payload={}, state={})
    assert out["status"] == "not_implemented"
