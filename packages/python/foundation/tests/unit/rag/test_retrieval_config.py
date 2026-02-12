"""Tests for retrieval configuration contract helpers."""

from __future__ import annotations

from omni.rag.retrieval.interface import RetrievalConfig


def test_retrieval_config_to_vector_search_kwargs_shape() -> None:
    cfg = RetrievalConfig(
        where_filter={"type": "tool"},
        batch_size=256,
        fragment_readahead=2,
        batch_readahead=8,
        scan_limit=128,
    )

    kwargs = cfg.to_vector_search_kwargs()
    assert kwargs == {
        "where_filter": {"type": "tool"},
        "batch_size": 256,
        "fragment_readahead": 2,
        "batch_readahead": 8,
        "scan_limit": 128,
    }
