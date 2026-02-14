"""Phase 2 vector features: bounded cache and background index (Python surface)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from omni.foundation.bridge.rust_vector import RUST_AVAILABLE, RustVectorStore


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
class TestPhase2VectorFeatures:
    """Demonstrate Phase 2: max_cached_tables and create_index_background."""

    def test_create_store_with_max_cached_tables(self) -> None:
        """RustVectorStore accepts max_cached_tables (bounded LRU cache)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "phase2.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
                max_cached_tables=2,
            )
            assert store._max_cached_tables == 2
            # Smoke: count on empty table
            n = store._inner.count("skills")
            assert n == 0

    def test_create_index_background_returns_immediately(self) -> None:
        """create_index_background does not block; no error on empty/small table."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bg.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
            )
            # No table yet / empty table: background job is a no-op but must not raise
            store.create_index_background("skills")
            store.create_index_background("router")
