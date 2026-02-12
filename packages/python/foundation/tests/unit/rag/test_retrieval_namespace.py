"""
test_retrieval_namespace.py - Unit tests for retrieval namespace backends.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from omni.rag import (
    RetrievalConfig,
    RetrievalResult,
    LanceRetrievalBackend,
    HybridRetrievalBackend,
    HybridRetrievalUnavailableError,
)


@dataclass
class _VectorRow:
    id: str
    content: str
    distance: float
    metadata: dict
    score: float | None = None


class _FakeVectorClient:
    def __init__(self):
        self.search_calls = []
        self.batch_calls = []

    async def search(self, query: str, n_results: int, collection: str, **kwargs):
        self.search_calls.append((query, n_results, collection, kwargs))
        return [
            _VectorRow(id="a", content="alpha", distance=0.10, metadata={"k": 1}),
            _VectorRow(id="b", content="beta", distance=1.00, metadata={"k": 2}),
        ]

    async def search_hybrid(self, query: str, n_results: int, collection: str, keywords=None):
        self.search_calls.append((f"hybrid:{query}", n_results, collection, {"keywords": keywords}))
        return [
            _VectorRow(
                id="h1",
                content="hybrid alpha",
                distance=0.05,
                metadata={"k": 10, "source": "hybrid"},
            ),
            _VectorRow(
                id="h2",
                content="hybrid beta",
                distance=0.40,
                metadata={"k": 20, "source": "hybrid"},
            ),
        ]

    async def add_batch(self, chunks, metadata, collection):
        self.batch_calls.append((chunks, metadata, collection))
        return len(chunks)

    async def count(self, collection):
        return 42

    def cache_stats(self):
        return {"hits": 1, "misses": 2}


@pytest.mark.asyncio
async def test_lance_backend_search_normalizes_and_filters():
    fake = _FakeVectorClient()
    backend = LanceRetrievalBackend(vector_client=fake)
    cfg = RetrievalConfig(collection="knowledge", top_k=5, score_threshold=0.60)
    results = await backend.search("q", cfg)

    assert len(results) == 1
    assert results[0].id == "a"
    assert results[0].source == "vector"
    assert results[0].score > 0.60
    assert fake.search_calls[0][3]["where_filter"] is None


@pytest.mark.asyncio
async def test_lance_backend_index_uses_add_batch():
    fake = _FakeVectorClient()
    backend = LanceRetrievalBackend(vector_client=fake)
    count = await backend.index(
        [
            {"content": "doc-1", "metadata": {"s": 1}},
            {"content": "doc-2", "metadata": {"s": 2}},
            {"content": "   ", "metadata": {"s": 3}},  # ignored empty
        ],
        collection="knowledge",
    )

    assert count == 2
    assert len(fake.batch_calls) == 1
    chunks, metadata, collection = fake.batch_calls[0]
    assert chunks == ["doc-1", "doc-2"]
    assert metadata == [{"s": 1}, {"s": 2}]
    assert collection == "knowledge"


@pytest.mark.asyncio
async def test_lance_backend_stats():
    backend = LanceRetrievalBackend(vector_client=_FakeVectorClient())
    stats = await backend.get_stats("knowledge")
    assert stats["backend"] == "lance"
    assert stats["count"] == 42
    assert "cache" in stats


@pytest.mark.asyncio
async def test_lance_backend_hybrid_search_uses_vector_client_hybrid():
    fake = _FakeVectorClient()
    backend = LanceRetrievalBackend(vector_client=fake)
    cfg = RetrievalConfig(collection="knowledge", top_k=5, score_threshold=0.30)
    results = await backend.search_hybrid("typed", cfg)

    assert len(results) == 2
    assert results[0].source == "hybrid"
    assert results[0].score >= results[1].score
    assert fake.search_calls[0][3]["keywords"] is None


@pytest.mark.asyncio
async def test_lance_backend_search_forwards_scanner_options():
    fake = _FakeVectorClient()
    backend = LanceRetrievalBackend(vector_client=fake)
    cfg = RetrievalConfig(
        collection="knowledge",
        top_k=3,
        where_filter='{"type":"tool"}',
        batch_size=256,
        fragment_readahead=2,
        batch_readahead=8,
        scan_limit=128,
    )
    await backend.search("q", cfg)

    forwarded = fake.search_calls[0][3]
    assert forwarded["where_filter"] == '{"type":"tool"}'
    assert forwarded["batch_size"] == 256
    assert forwarded["fragment_readahead"] == 2
    assert forwarded["batch_readahead"] == 8
    assert forwarded["scan_limit"] == 128


@pytest.mark.asyncio
async def test_lance_backend_hybrid_search_forwards_keywords():
    fake = _FakeVectorClient()
    backend = LanceRetrievalBackend(vector_client=fake)
    cfg = RetrievalConfig(collection="knowledge", top_k=5, keywords=["typed", "languages"])
    await backend.search_hybrid("typed languages", cfg)

    assert fake.search_calls[0][3]["keywords"] == ["typed", "languages"]


@pytest.mark.asyncio
async def test_lance_backend_hybrid_search_deduplicates_by_id():
    class _DupHybridClient(_FakeVectorClient):
        async def search_hybrid(self, query: str, n_results: int, collection: str, keywords=None):
            del query, n_results, collection, keywords
            return [
                _VectorRow(id="dup", content="first", distance=0.30, metadata={"source": "hybrid"}),
                _VectorRow(
                    id="dup", content="better", distance=0.05, metadata={"source": "hybrid"}
                ),
            ]

    backend = LanceRetrievalBackend(vector_client=_DupHybridClient())
    results = await backend.search_hybrid("typed", RetrievalConfig(top_k=5))

    assert len(results) == 1
    assert results[0].id == "dup"
    assert results[0].content == "better"


@pytest.mark.asyncio
async def test_lance_backend_hybrid_search_prefers_rust_score_when_available():
    class _ScoreHybridClient(_FakeVectorClient):
        async def search_hybrid(self, query: str, n_results: int, collection: str, keywords=None):
            del query, n_results, collection, keywords
            return [
                _VectorRow(
                    id="h1",
                    content="hybrid alpha",
                    distance=0.95,
                    metadata={"source": "hybrid"},
                    score=0.61,
                )
            ]

    backend = LanceRetrievalBackend(vector_client=_ScoreHybridClient())
    results = await backend.search_hybrid("typed", RetrievalConfig(top_k=5))

    assert len(results) == 1
    assert results[0].score == 0.61


class _StaticBackend:
    def __init__(self, results: list[RetrievalResult], name: str):
        self._results = results
        self._name = name

    async def search(self, query: str, config: RetrievalConfig):
        return self._results

    async def index(self, documents, collection: str):
        return len(documents)

    async def get_stats(self, collection: str):
        return {"backend": self._name, "count": len(self._results)}


@pytest.mark.asyncio
async def test_hybrid_backend_requires_native_hybrid_method():
    vector = _StaticBackend(
        [RetrievalResult(id="a", content="alpha", score=0.9, source="vector")],
        "vector",
    )
    backend = HybridRetrievalBackend(vector_backend=vector)
    with pytest.raises(HybridRetrievalUnavailableError):
        await backend.search("typed", RetrievalConfig(top_k=5))


@pytest.mark.asyncio
async def test_hybrid_backend_stats_include_children():
    class _NativeHybridBackend(_StaticBackend):
        async def search_hybrid(self, query: str, config: RetrievalConfig):
            return [RetrievalResult(id="a", content="alpha", score=0.9, source="hybrid")]

    vector = _NativeHybridBackend([RetrievalResult(id="a", content="alpha", score=0.9)], "vector")
    backend = HybridRetrievalBackend(vector)
    stats = await backend.get_stats("knowledge")
    assert stats["backend"] == "hybrid"
    assert stats["engine_owner"] == "rust"
    assert stats["vector"]["backend"] == "vector"


@pytest.mark.asyncio
async def test_hybrid_backend_applies_threshold_filter():
    class _NativeHybridBackend(_StaticBackend):
        async def search_hybrid(self, query: str, config: RetrievalConfig):
            return [
                RetrievalResult(id="a", content="top", score=0.9, source="hybrid"),
                RetrievalResult(id="b", content="low", score=0.2, source="hybrid"),
            ]

    vector = _NativeHybridBackend([], "vector")
    backend = HybridRetrievalBackend(vector)
    results = await backend.search("python type", RetrievalConfig(top_k=2, score_threshold=0.5))
    assert [r.id for r in results] == ["a"]


@pytest.mark.asyncio
async def test_hybrid_backend_prefers_native_hybrid_when_available():
    class _NativeHybridBackend(_StaticBackend):
        def __init__(self):
            super().__init__(results=[], name="vector")
            self.native_calls = 0

        async def search_hybrid(self, query: str, config: RetrievalConfig):
            self.native_calls += 1
            return [
                RetrievalResult(id="n1", content="native one", score=0.95, source="hybrid"),
                RetrievalResult(id="n2", content="native two", score=0.70, source="hybrid"),
            ]

    vector = _NativeHybridBackend()
    backend = HybridRetrievalBackend(vector_backend=vector)
    results = await backend.search("typed", RetrievalConfig(top_k=2))

    assert vector.native_calls == 1
    assert [r.id for r in results] == ["n1", "n2"]


@pytest.mark.asyncio
async def test_hybrid_backend_deduplicates_native_results():
    class _NativeHybridBackend(_StaticBackend):
        async def search_hybrid(self, query: str, config: RetrievalConfig):
            del query, config
            return [
                RetrievalResult(id="dup", content="older", score=0.60, source="hybrid"),
                RetrievalResult(id="dup", content="newer", score=0.95, source="hybrid"),
            ]

    vector = _NativeHybridBackend([], "vector")
    backend = HybridRetrievalBackend(vector_backend=vector)
    results = await backend.search("typed", RetrievalConfig(top_k=5))

    assert len(results) == 1
    assert results[0].id == "dup"
    assert results[0].content == "newer"
    assert results[0].score == 0.95
