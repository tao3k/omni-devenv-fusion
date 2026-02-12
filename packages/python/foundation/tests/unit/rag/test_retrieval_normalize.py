"""Tests for retrieval normalization helpers."""

from __future__ import annotations

from omni.rag.retrieval.interface import RetrievalResult
from omni.rag.retrieval.normalize import normalize_ranked_results


def test_normalize_ranked_results_deduplicates_and_sorts() -> None:
    results = [
        RetrievalResult(id="a", content="alpha-1", score=0.50),
        RetrievalResult(id="a", content="alpha-2", score=0.80),
        RetrievalResult(id="b", content="beta", score=0.60),
    ]

    normalized = normalize_ranked_results(results)
    assert [item.id for item in normalized] == ["a", "b"]
    assert normalized[0].content == "alpha-2"
    assert normalized[0].score == 0.80


def test_normalize_ranked_results_uses_content_as_fallback_key() -> None:
    results = [
        RetrievalResult(id="", content="same-content", score=0.20),
        RetrievalResult(id="", content="same-content", score=0.90),
    ]
    normalized = normalize_ranked_results(results, score_threshold=0.1)

    assert len(normalized) == 1
    assert normalized[0].content == "same-content"
    assert normalized[0].score == 0.90


def test_normalize_ranked_results_stable_tie_breaks_by_id() -> None:
    results = [
        RetrievalResult(id="b", content="beta", score=0.70),
        RetrievalResult(id="a", content="alpha", score=0.70),
    ]
    normalized = normalize_ranked_results(results)
    assert [item.id for item in normalized] == ["a", "b"]
