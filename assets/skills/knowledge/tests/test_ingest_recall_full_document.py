"""Tests for ingest with Rust chunker and full_document recall.

Phase 4.2 of UltraRAG-style ingest plan:
- py_chunk_text returns correct structure
- recall action=full_document with source returns correct count and order
- deduplication by chunk_index works

Uses conftest (SKILLS_DIR) for scripts path; no hardcoded paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Scripts path added by conftest via SKILLS_DIR


def _import_recall():
    import recall as recall_mod

    return recall_mod


def _unwrap_recall_output(out):
    """Unwrap @skill_command output: may be dict with content[].text or raw JSON string."""
    if isinstance(out, str):
        return json.loads(out)
    if isinstance(out, dict):
        content = out.get("content") or []
        first = content[0] if content else None
        if isinstance(first, dict):
            text = first.get("text", "")
            if isinstance(text, str) and text.strip():
                return json.loads(text)
    return out


def _import_graph():
    import graph as graph_mod

    return graph_mod


# -----------------------------------------------------------------------------
# py_chunk_text (Rust chunker) unit tests
# -----------------------------------------------------------------------------


def test_py_chunk_text_returns_correct_structure():
    """py_chunk_text returns list of (text, chunk_index) with contiguous indices."""
    omni_core_rs = pytest.importorskip("omni_core_rs")

    text = "First paragraph. Second paragraph. Third paragraph. Fourth paragraph. Fifth."
    out = omni_core_rs.py_chunk_text(text, chunk_size_tokens=20, overlap_tokens=2)
    assert isinstance(out, list)
    assert len(out) >= 1
    for i, item in enumerate(out):
        assert isinstance(item, (list, tuple)), f"item {i} should be (text, index)"
        assert len(item) == 2
        chunk_text_val, chunk_index = item
        assert isinstance(chunk_text_val, str)
        assert isinstance(chunk_index, int)
        assert chunk_index == i, "chunk_index should be contiguous 0..n-1"


def test_py_chunk_text_empty_returns_empty():
    """py_chunk_text on empty string returns empty list."""
    omni_core_rs = pytest.importorskip("omni_core_rs")

    out = omni_core_rs.py_chunk_text("", 512, 50)
    assert out == []


# -----------------------------------------------------------------------------
# recall full_document tests (with mock store)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_full_document_requires_source():
    """recall with action=full_document and empty source returns error."""
    recall_mod = _import_recall()

    out = await recall_mod.recall(
        query="",
        chunked=True,
        action="full_document",
        source="",
    )
    data = _unwrap_recall_output(out)
    assert data.get("action") == "full_document"
    assert data.get("status") == "error"
    assert "source" in (data.get("message") or "").lower()


@pytest.mark.asyncio
async def test_recall_full_document_dedup_and_order():
    """recall full_document deduplicates by chunk_index and sorts by chunk_index."""
    recall_mod = _import_recall()

    # Mock store: list_all_tools returns entries with duplicate chunk_index
    raw_entries = [
        {"id": "a1", "content": "chunk 0", "metadata": {"source": "doc.pdf", "chunk_index": 0}},
        {"id": "a2", "content": "chunk 1", "metadata": {"source": "doc.pdf", "chunk_index": 1}},
        {
            "id": "dup",
            "content": "duplicate of 1",
            "metadata": {"source": "doc.pdf", "chunk_index": 1},
        },
        {"id": "a3", "content": "chunk 2", "metadata": {"source": "doc.pdf", "chunk_index": 2}},
    ]
    list_json = json.dumps(raw_entries)

    mock_inner = MagicMock()
    mock_inner.list_all_tools = MagicMock(return_value=list_json)

    mock_store = MagicMock()
    mock_store._inner = mock_inner
    mock_store.list_all = AsyncMock(return_value=raw_entries)

    mock_client = MagicMock()
    mock_client.store = True  # Avoid early "Vector store not initialized" return
    mock_client.get_store_for_collection = MagicMock(return_value=mock_store)

    # Patch where recall looks up get_vector_store (in its module namespace)
    with patch.object(recall_mod, "get_vector_store", return_value=mock_client):
        out = await recall_mod.recall(
            query="",
            chunked=True,
            action="full_document",
            source="doc.pdf",
        )

    data = _unwrap_recall_output(out)
    assert data.get("status") == "success"
    assert data.get("action") == "full_document"
    results = data.get("results", [])
    # Should deduplicate: 3 unique chunk_indices (0, 1, 2), not 4
    assert len(results) == 3
    # Order by chunk_index
    indices = [r.get("chunk_index") for r in results]
    assert indices == [0, 1, 2]
    # First occurrence of chunk_index 1 kept
    assert results[1]["content"] == "chunk 1"


@pytest.mark.asyncio
async def test_recall_full_document_source_suffix_match():
    """recall full_document matches source by suffix (e.g. 2602.12108.pdf)."""
    recall_mod = _import_recall()

    raw_entries = [
        {
            "id": "x",
            "content": "content",
            "metadata": {"source": "/path/to/data/2602.12108.pdf", "chunk_index": 0},
        },
    ]
    mock_store = MagicMock()
    mock_store.list_all = AsyncMock(return_value=raw_entries)

    mock_client = MagicMock()
    mock_client.store = True
    mock_client.get_store_for_collection = MagicMock(return_value=mock_store)

    with patch.object(recall_mod, "get_vector_store", return_value=mock_client):
        out = await recall_mod.recall(
            query="",
            chunked=True,
            action="full_document",
            source="2602.12108.pdf",
        )

    data = _unwrap_recall_output(out)
    assert data.get("status") == "success"
    assert data.get("count") == 1
    assert data["results"][0]["content"] == "content"
