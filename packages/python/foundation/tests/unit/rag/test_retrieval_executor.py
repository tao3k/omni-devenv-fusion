"""Tests for omni.rag.retrieval.executor helpers."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

import omni.rag.retrieval.executor as retrieval_executor
from omni.foundation.services.embedding import EmbeddingUnavailableError
from omni.rag.retrieval import (
    run_recall_hybrid_rows,
    run_recall_query_rows,
    run_recall_semantic_rows,
)


@pytest.mark.asyncio
async def test_run_recall_semantic_rows_converts_results() -> None:
    class _VectorStore:
        async def search(self, query: str, n_results: int, collection: str, use_cache: bool):
            del use_cache
            assert query == "architecture"
            assert n_results == 2
            assert collection == "knowledge_chunks"
            return [
                SimpleNamespace(
                    id="id-1",
                    content="c1",
                    distance=0.2,
                    metadata={"source": "docs/1.md", "title": "T1", "section": "S1"},
                ),
                SimpleNamespace(
                    id="id-2",
                    content="c2",
                    distance=0.9,
                    metadata={},
                ),
            ]

    rows = await run_recall_semantic_rows(
        vector_store=_VectorStore(),
        query="architecture",
        collection="knowledge_chunks",
        fetch_limit=2,
    )
    assert rows == [
        {
            "content": "c1",
            "source": "docs/1.md",
            "score": 0.8,
            "title": "T1",
            "section": "S1",
        },
        {
            "content": "c2",
            "source": "id-2",
            "score": 0.1,
            "title": "",
            "section": "",
        },
    ]


@pytest.mark.asyncio
async def test_run_recall_semantic_rows_caps_rows_when_backend_overfetches() -> None:
    class _VectorStore:
        async def search(self, query: str, n_results: int, collection: str, use_cache: bool):
            del use_cache
            assert query == "architecture"
            assert n_results == 2
            assert collection == "knowledge_chunks"
            return [
                SimpleNamespace(id="id-1", content="c1", distance=0.2, metadata={}),
                SimpleNamespace(id="id-2", content="c2", distance=0.3, metadata={}),
                SimpleNamespace(id="id-3", content="c3", distance=0.4, metadata={}),
            ]

    rows = await run_recall_semantic_rows(
        vector_store=_VectorStore(),
        query="architecture",
        collection="knowledge_chunks",
        fetch_limit=2,
    )
    assert [r["content"] for r in rows] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_run_recall_hybrid_rows_embeds_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmbeddingService:
        def embed(self, query: str):
            assert query == "architecture"
            return [[0.1, 0.2, 0.3]]

    class _Store:
        def __init__(self) -> None:
            self.calls: list[tuple[str, list[float], list[str], int]] = []

        def search_hybrid(
            self,
            collection: str,
            vector: list[float],
            keywords: list[str],
            n_results: int,
        ) -> list[str]:
            self.calls.append((collection, vector, keywords, n_results))
            return [
                json.dumps(
                    {
                        "id": "x",
                        "content": "raw",
                        "distance": 0.2,
                        "metadata": {"source": "docs/x.md", "title": "X", "section": "intro"},
                    }
                ),
                "not-json",
            ]

    class _VectorStore:
        def __init__(self, store: _Store) -> None:
            self._store = store

        def get_store_for_collection(self, collection: str):
            assert collection == "knowledge_chunks"
            return self._store

    store = _Store()
    vector_store = _VectorStore(store)
    errors: list[str] = []

    import omni.foundation.services.embedding as embedding_module
    import omni.foundation.services.vector as vector_module

    monkeypatch.setattr(embedding_module, "get_embedding_service", lambda: _EmbeddingService())
    monkeypatch.setattr(vector_module, "_search_embed_timeout", lambda: 1.0)

    rows = await run_recall_hybrid_rows(
        vector_store=vector_store,
        query="architecture",
        keywords=["graph"],
        collection="knowledge_chunks",
        fetch_limit=5,
        on_parse_error=lambda exc: errors.append(type(exc).__name__),
    )
    assert rows == [
        {
            "content": "raw",
            "source": "docs/x.md",
            "score": 0.8,
            "title": "X",
            "section": "intro",
        }
    ]
    assert store.calls and store.calls[0][2] == ["graph"]
    assert errors == ["JSONDecodeError"]


@pytest.mark.asyncio
async def test_run_recall_hybrid_rows_caps_rows_when_backend_overfetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmbeddingService:
        def embed(self, query: str):
            assert query == "architecture"
            return [[0.1, 0.2, 0.3]]

    class _Store:
        def search_hybrid(
            self,
            collection: str,
            vector: list[float],
            keywords: list[str],
            n_results: int,
        ) -> list[str]:
            assert collection == "knowledge_chunks"
            assert vector == [0.1, 0.2, 0.3]
            assert keywords == ["graph"]
            assert n_results == 2
            return [
                json.dumps(
                    {
                        "id": "x",
                        "content": "raw-1",
                        "distance": 0.2,
                        "metadata": {"source": "docs/x.md"},
                    }
                ),
                json.dumps(
                    {
                        "id": "y",
                        "content": "raw-2",
                        "distance": 0.3,
                        "metadata": {"source": "docs/y.md"},
                    }
                ),
                json.dumps(
                    {
                        "id": "z",
                        "content": "raw-3",
                        "distance": 0.4,
                        "metadata": {"source": "docs/z.md"},
                    }
                ),
            ]

    class _VectorStore:
        def __init__(self, store: _Store) -> None:
            self._store = store

        def get_store_for_collection(self, collection: str):
            assert collection == "knowledge_chunks"
            return self._store

    import omni.foundation.services.embedding as embedding_module
    import omni.foundation.services.vector as vector_module

    monkeypatch.setattr(embedding_module, "get_embedding_service", lambda: _EmbeddingService())
    monkeypatch.setattr(vector_module, "_search_embed_timeout", lambda: 1.0)

    rows = await run_recall_hybrid_rows(
        vector_store=_VectorStore(_Store()),
        query="architecture",
        keywords=["graph"],
        collection="knowledge_chunks",
        fetch_limit=2,
    )
    assert [r["content"] for r in rows] == ["raw-1", "raw-2"]


@pytest.mark.asyncio
async def test_run_recall_hybrid_rows_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SlowEmbeddingService:
        def embed(self, _query: str):
            time.sleep(0.05)
            return [[0.1]]

    class _VectorStore:
        def get_store_for_collection(self, _collection: str):
            return None

    import omni.foundation.services.embedding as embedding_module
    import omni.foundation.services.vector as vector_module

    monkeypatch.setattr(embedding_module, "get_embedding_service", lambda: _SlowEmbeddingService())
    monkeypatch.setattr(vector_module, "_search_embed_timeout", lambda: 0.001)

    with pytest.raises(EmbeddingUnavailableError, match=r"timed out.*for recall"):
        await run_recall_hybrid_rows(
            vector_store=_VectorStore(),
            query="architecture",
            keywords=["graph"],
            collection="knowledge_chunks",
            fetch_limit=5,
        )


@pytest.mark.asyncio
async def test_run_recall_query_rows_dispatches_by_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake_hybrid(**_kwargs):
        calls.append("hybrid")
        return [{"content": "hybrid"}]

    async def _fake_semantic(**_kwargs):
        calls.append("semantic")
        return [{"content": "semantic"}]

    monkeypatch.setattr(retrieval_executor, "run_recall_hybrid_rows", _fake_hybrid)
    monkeypatch.setattr(retrieval_executor, "run_recall_semantic_rows", _fake_semantic)

    hybrid_rows = await run_recall_query_rows(
        vector_store=object(),
        query="q",
        keywords=["k"],
        collection="knowledge_chunks",
        fetch_limit=1,
    )
    semantic_rows = await run_recall_query_rows(
        vector_store=object(),
        query="q",
        keywords=[],
        collection="knowledge_chunks",
        fetch_limit=1,
    )

    assert hybrid_rows == [{"content": "hybrid"}]
    assert semantic_rows == [{"content": "semantic"}]
    assert calls == ["hybrid", "semantic"]


@pytest.mark.asyncio
async def test_run_recall_query_rows_caps_dispatched_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_hybrid(**_kwargs):
        return [
            {"content": "hybrid-1"},
            {"content": "hybrid-2"},
            {"content": "hybrid-3"},
        ]

    async def _fake_semantic(**_kwargs):
        return [
            {"content": "semantic-1"},
            {"content": "semantic-2"},
        ]

    monkeypatch.setattr(retrieval_executor, "run_recall_hybrid_rows", _fake_hybrid)
    monkeypatch.setattr(retrieval_executor, "run_recall_semantic_rows", _fake_semantic)

    hybrid_rows = await run_recall_query_rows(
        vector_store=object(),
        query="q",
        keywords=["k"],
        collection="knowledge_chunks",
        fetch_limit=2,
    )
    semantic_rows = await run_recall_query_rows(
        vector_store=object(),
        query="q",
        keywords=[],
        collection="knowledge_chunks",
        fetch_limit=1,
    )

    assert [row["content"] for row in hybrid_rows] == ["hybrid-1", "hybrid-2"]
    assert [row["content"] for row in semantic_rows] == ["semantic-1"]


@pytest.mark.asyncio
async def test_run_recall_query_rows_records_query_phase_with_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_semantic(**_kwargs):
        return [{"content": "semantic-1"}]

    recorded: list[tuple[str, float, float | None, float | None, dict[str, object]]] = []

    monkeypatch.setattr(retrieval_executor, "run_recall_semantic_rows", _fake_semantic)
    monkeypatch.setattr(retrieval_executor, "start_phase_sample", lambda: (1.0, 100.0, 120.0))

    def _capture(
        phase: str,
        started_at: float,
        rss_before: float | None,
        rss_peak_before: float | None,
        **extra: object,
    ) -> None:
        recorded.append((phase, started_at, rss_before, rss_peak_before, dict(extra)))

    monkeypatch.setattr(retrieval_executor, "record_phase_with_memory", _capture)

    rows = await run_recall_query_rows(
        vector_store=object(),
        query="q",
        keywords=[],
        collection="knowledge_chunks",
        fetch_limit=1,
    )

    assert rows == [{"content": "semantic-1"}]
    assert len(recorded) == 1
    phase, started_at, rss_before, rss_peak_before, extra = recorded[0]
    assert phase == "retrieval.rows.query"
    assert started_at == 1.0
    assert rss_before == 100.0
    assert rss_peak_before == 120.0
    assert extra["mode"] == "semantic"
    assert extra["collection"] == "knowledge_chunks"
    assert extra["fetch_limit"] == 1
    assert extra["rows_input"] == 1
    assert extra["rows_returned"] == 1
    assert extra["rows_capped"] == 0
