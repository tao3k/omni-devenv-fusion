"""Tests for omni.rag.retrieval.postprocess helpers."""

from __future__ import annotations

import pytest

from omni.rag.retrieval import apply_recall_postprocess, filter_recall_rows


def test_filter_recall_rows_respects_min_score_and_limit() -> None:
    rows = [
        {"content": "high", "score": 0.9, "source": "a"},
        {"content": "mid", "score": 0.6, "source": "b"},
        {"content": "low", "score": 0.2, "source": "c"},
    ]
    out = filter_recall_rows(rows, limit=2, min_score=0.5)
    assert out == [
        {"content": "high", "score": 0.9, "source": "a"},
        {"content": "mid", "score": 0.6, "source": "b"},
    ]


@pytest.mark.asyncio
async def test_apply_recall_postprocess_runs_boost_only_when_non_preview() -> None:
    calls: list[str] = []

    async def _boost(rows: list[dict], query: str) -> list[dict]:
        calls.append(query)
        return [{**row, "score": float(row.get("score", 0.0)) + 0.1} for row in rows]

    rows = [{"content": "a", "score": 0.5, "source": "s"}]
    non_preview = await apply_recall_postprocess(
        rows,
        query="q1",
        limit=1,
        min_score=0.0,
        preview=False,
        snippet_chars=10,
        boost_rows=_boost,
    )
    preview = await apply_recall_postprocess(
        rows,
        query="q2",
        limit=1,
        min_score=0.0,
        preview=True,
        snippet_chars=10,
        boost_rows=_boost,
    )
    assert calls == ["q1"]
    assert non_preview[0]["score"] == 0.6
    assert preview[0]["score"] == 0.5


@pytest.mark.asyncio
async def test_apply_recall_postprocess_preview_truncates_and_marks_preview() -> None:
    rows = [{"content": "abcdef", "score": 0.5, "source": "s"}]
    out = await apply_recall_postprocess(
        rows,
        query="q",
        limit=1,
        min_score=0.99,
        preview=True,
        snippet_chars=3,
        boost_rows=None,
    )
    assert out[0]["content"] == "abc…"
    assert out[0]["preview"] is True


@pytest.mark.asyncio
async def test_apply_recall_postprocess_falls_back_to_head_when_filtered_empty() -> None:
    rows = [
        {"content": "a", "score": 0.1, "source": "s1"},
        {"content": "b", "score": 0.2, "source": "s2"},
    ]
    out = await apply_recall_postprocess(
        rows,
        query="q",
        limit=1,
        min_score=0.95,
        preview=False,
        snippet_chars=10,
        boost_rows=None,
    )
    assert out == [{"content": "a", "score": 0.1, "source": "s1"}]
