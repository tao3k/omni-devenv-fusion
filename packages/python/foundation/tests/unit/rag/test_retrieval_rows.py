"""Tests for omni.rag.retrieval.rows helpers."""

from __future__ import annotations

from types import SimpleNamespace

from omni.rag.retrieval import (
    build_recall_row,
    recall_rows_from_hybrid_json,
    recall_rows_from_vector_results,
)


def test_build_recall_row_rounds_score_and_shapes_payload() -> None:
    row = build_recall_row(
        content="hello",
        source="docs/a.md",
        score=0.123456,
        title="A",
        section="intro",
    )
    assert row == {
        "content": "hello",
        "source": "docs/a.md",
        "score": 0.1235,
        "title": "A",
        "section": "intro",
    }


def test_recall_rows_from_vector_results_converts_objects() -> None:
    rows = recall_rows_from_vector_results(
        [
            SimpleNamespace(
                id="id-1",
                content="c1",
                distance=0.2,
                metadata={"source": "docs/1.md", "title": "T1", "section": "S1"},
            ),
            SimpleNamespace(
                id="id-2",
                content="c2",
                distance=1.2,
                metadata="bad-metadata",
            ),
        ]
    )
    assert rows[0] == {
        "content": "c1",
        "source": "docs/1.md",
        "score": 0.8,
        "title": "T1",
        "section": "S1",
    }
    assert rows[1] == {
        "content": "c2",
        "source": "id-2",
        "score": 0.0,
        "title": "",
        "section": "",
    }


def test_recall_rows_from_hybrid_json_parses_and_skips_invalid() -> None:
    errors: list[str] = []
    rows = recall_rows_from_hybrid_json(
        [
            '{"id":"x","content":"raw","distance":0.25,"metadata":{"source":"docs/x.md","title":"X"}}',
            "not-json",
            '{"id":"y","content":"fallback","distance":0.1,"metadata":"bad"}',
        ],
        on_parse_error=lambda exc: errors.append(type(exc).__name__),
    )
    assert len(rows) == 2
    assert rows[0] == {
        "content": "raw",
        "source": "docs/x.md",
        "score": 0.75,
        "title": "X",
        "section": "",
    }
    assert rows[1] == {
        "content": "fallback",
        "source": "y",
        "score": 0.9,
        "title": "",
        "section": "",
    }
    assert errors == ["JSONDecodeError"]
