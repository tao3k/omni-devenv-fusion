"""Unit tests for recall TOC filtering and min_score (no vector store)."""

import pytest

# conftest adds skill scripts to path
import recall


def test_is_toc_or_index_chunk_empty_or_short():
    """Short or empty content is not TOC."""
    assert recall._is_toc_or_index_chunk("") is False
    assert recall._is_toc_or_index_chunk("short") is False
    assert recall._is_toc_or_index_chunk("x" * 50) is False


def test_is_toc_or_index_chunk_doc_description_table():
    """Table with | Document | and | Description | and 3+ rows is TOC."""
    toc = """
| Document | Description |
| -------- | ----------- |
| [A](./a.md) | First doc |
| [B](./b.md) | Second doc |
"""
    assert recall._is_toc_or_index_chunk(toc) is True


def test_is_toc_or_index_chunk_many_table_rows_with_links():
    """Many table rows (>=8) with markdown links is TOC-like."""
    lines = ["| [Link](./x.md) |"] * 10
    content = "\n".join(lines)
    assert len(content) >= 80
    assert recall._is_toc_or_index_chunk(content) is True


def test_is_toc_or_index_chunk_substantive_section():
    """Substantive section content is not TOC."""
    section = """
## Git commit format

Use Conventional Commits. Scope examples: feat(router), fix(omni-vector).
Run `lefthook run pre-commit` before committing.
"""
    assert recall._is_toc_or_index_chunk(section) is False


def test_filter_and_rank_recall_respects_min_score():
    """Results below min_score are dropped."""
    results = [
        {"content": "high", "score": 0.9, "source": "a"},
        {"content": "low", "score": 0.2, "source": "b"},
        {"content": "mid", "score": 0.6, "source": "c"},
    ]
    out = recall._filter_and_rank_recall(results, limit=5, min_score=0.5)
    assert len(out) == 2
    assert out[0]["score"] == 0.9
    assert out[1]["score"] == 0.6


def test_filter_and_rank_recall_demotes_toc_then_fills():
    """TOC-like chunks are demoted; substantive chunks fill limit first."""
    toc_chunk = (
        "| Document | Description |\n| -------- | ----------- |\n| [A](./a.md) | Desc |\n" * 2
    )
    results = [
        {"content": "real section about git commits", "score": 0.7, "source": "doc"},
        {"content": toc_chunk, "score": 0.8, "source": "index"},
        {"content": "another real section", "score": 0.65, "source": "ref"},
    ]
    out = recall._filter_and_rank_recall(results, limit=3, min_score=0.0)
    assert len(out) == 3
    assert out[0]["content"].startswith("real section")
    assert out[1]["content"].startswith("another real")
    assert out[2]["source"] == "index"


def test_filter_and_rank_recall_limit():
    """Return at most `limit` results."""
    results = [
        {"content": f"chunk {i}", "score": 0.9 - i * 0.1, "source": f"s{i}"} for i in range(5)
    ]
    out = recall._filter_and_rank_recall(results, limit=2, min_score=0.0)
    assert len(out) == 2
