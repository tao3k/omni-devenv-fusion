"""Tests for search result cache integration (Python → Rust search_optimized).

Verifies that repeated search_optimized calls return consistent results.
The Rust-side cache is transparent; this test ensures the Python→Rust path works.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("omni_core_rs")

from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
@pytest.mark.asyncio
async def test_search_optimized_repeated_calls_return_same_results() -> None:
    """Repeated search_optimized with same params returns identical results (Rust cache path)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "search_cache.lance")
        store = RustVectorStore(
            index_path=path,
            dimension=8,
            enable_keyword_index=False,
        )
        table_name = "knowledge"
        ids = ["doc.1", "doc.2", "doc.3"]
        vectors = [[0.1] * 8, [0.2] * 8, [0.15] * 8]
        contents = ["First", "Second", "Third"]
        metadatas = [json.dumps({})] * 3
        await store.add_documents(table_name, ids, vectors, contents, metadatas)
        await store.create_index(table_name, 8)

        query_vector = [0.12] * 8
        limit = 2

        r1 = store.search_optimized(table_name, query_vector, limit, None)
        r2 = store.search_optimized(table_name, query_vector, limit, None)

        assert isinstance(r1, list)
        assert isinstance(r2, list)
        assert len(r1) == len(r2)
        assert r1 == r2, "Repeated search_optimized must return identical results (cache hit)"
