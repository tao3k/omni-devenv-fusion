"""
Regression tests to prevent abnormal memory/CPU usage from vector stores.

Guards:
- Single factory: Foundation must not call omni_core_rs.create_vector_store directly.
- Bounded cache: All stores created via bridge must have non-None cache limits.
- Defaults cap: Runtime defaults for index cache and max tables stay within safe bounds.

See: docs/architecture/vector-store-memory-and-single-factory.md
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from omni.foundation.bridge.rust_vector import (
    RUST_AVAILABLE,
    _DEFAULT_INDEX_CACHE_BYTES,
    _DEFAULT_MAX_CACHED_TABLES,
    RustVectorStore,
    get_vector_store,
)
from omni.foundation.services.vector import VectorStoreClient


# Safe upper bounds for defaults (regression: do not exceed without explicit review)
MAX_ACCEPTABLE_INDEX_CACHE_BYTES = 512 * 1024 * 1024  # 512 MiB
MAX_ACCEPTABLE_MAX_CACHED_TABLES = 16
MAX_ACCEPTABLE_SEARCH_CACHE_ENTRIES = 500


class TestSingleFactoryGuard:
    """Ensure Foundation never creates stores directly (only via bridge)."""

    def setup_method(self) -> None:
        VectorStoreClient._instance = None
        VectorStoreClient._store = None
        VectorStoreClient._knowledge_store = None

    def test_foundation_does_not_import_create_vector_store(self) -> None:
        """Foundation vector module must not use omni_core_rs.create_vector_store."""
        import omni.foundation.services.vector as vector_module

        source = getattr(vector_module, "__file__", "") or ""
        # Module should not reference create_vector_store (single factory via bridge)
        with open(source, encoding="utf-8") as f:
            content = f.read()
        assert "create_vector_store" not in content, (
            "omni.foundation.services.vector must not call create_vector_store; "
            "use bridge get_vector_store() only (single factory)."
        )

    def test_vector_store_client_store_uses_bridge_only(self) -> None:
        """VectorStoreClient.store must call bridge get_vector_store, not create_vector_store."""
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get:
            with patch("omni_core_rs.create_vector_store") as mock_create:
                mock_get.return_value = None
                vm = VectorStoreClient()
                _ = vm.store
                mock_get.assert_called()
                mock_create.assert_not_called()

    def test_vector_store_client_knowledge_uses_bridge_only(self) -> None:
        """VectorStoreClient._get_store_for_collection('knowledge_chunks') must use bridge."""
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get:
            with patch("omni_core_rs.create_vector_store") as mock_create:
                mock_get.return_value = None
                vm = VectorStoreClient()
                _ = vm._get_store_for_collection("knowledge_chunks")
                mock_get.assert_called()
                mock_create.assert_not_called()


class TestBoundedCacheGuard:
    """Ensure all bridge-created stores have bounded cache params (no None)."""

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
    def test_rust_vector_store_always_has_bounded_cache_attrs(self) -> None:
        """RustVectorStore must have _index_cache_size_bytes and _max_cached_tables set (never None)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bounded.lance")
            store = RustVectorStore(
                index_path=path,
                dimension=8,
                enable_keyword_index=False,
            )
            assert store._index_cache_size_bytes is not None
            assert store._max_cached_tables is not None
            assert store._index_cache_size_bytes > 0
            assert store._max_cached_tables > 0

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
    def test_rust_vector_store_bounded_when_settings_null(self) -> None:
        """When settings return null for cache params, bridge must still apply bounded defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "defaults.lance")
            with patch(
                "omni.foundation.config.settings.get_setting",
                return_value=None,
            ):
                store = RustVectorStore(
                    index_path=path,
                    dimension=8,
                    enable_keyword_index=False,
                )
            assert store._index_cache_size_bytes == _DEFAULT_INDEX_CACHE_BYTES
            assert store._max_cached_tables == _DEFAULT_MAX_CACHED_TABLES

    def test_default_constants_within_safe_bounds(self) -> None:
        """Module defaults must not exceed safe upper bounds (regression for memory/CPU)."""
        assert _DEFAULT_INDEX_CACHE_BYTES <= MAX_ACCEPTABLE_INDEX_CACHE_BYTES, (
            f"Bridge default index_cache_size_bytes ({_DEFAULT_INDEX_CACHE_BYTES}) "
            f"exceeds safe max ({MAX_ACCEPTABLE_INDEX_CACHE_BYTES})."
        )
        assert _DEFAULT_MAX_CACHED_TABLES <= MAX_ACCEPTABLE_MAX_CACHED_TABLES, (
            f"Bridge default max_cached_tables ({_DEFAULT_MAX_CACHED_TABLES}) "
            f"exceeds safe max ({MAX_ACCEPTABLE_MAX_CACHED_TABLES})."
        )


class TestGetVectorStoreUsesBoundedParams:
    """Ensure get_vector_store (single factory) passes bounded params to Rust."""

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust bindings not installed")
    def test_get_vector_store_creates_store_with_bounded_params(self) -> None:
        """get_vector_store must create RustVectorStore with non-None cache params."""
        from omni.foundation.bridge import rust_vector as bridge_mod

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "factory.lance")
            old = bridge_mod._vector_stores.pop(path, None)
            try:
                store = get_vector_store(index_path=path, dimension=8, enable_keyword_index=False)
                assert store._index_cache_size_bytes is not None
                assert store._max_cached_tables is not None
                assert store._index_cache_size_bytes > 0
                assert store._max_cached_tables > 0
            finally:
                bridge_mod._vector_stores.pop(path, None)
                if old is not None:
                    bridge_mod._vector_stores[path] = old


class TestSearchCacheBounded:
    """Ensure in-process search caches stay bounded (no unbounded growth)."""

    def setup_method(self) -> None:
        VectorStoreClient._instance = None
        VectorStoreClient._store = None
        VectorStoreClient._knowledge_store = None

    def test_vector_store_client_search_cache_has_bounded_max_size(self) -> None:
        """VectorStoreClient's search cache max_size must not exceed safe limit."""
        vm = VectorStoreClient()
        assert vm._search_cache._max_size <= MAX_ACCEPTABLE_SEARCH_CACHE_ENTRIES, (
            f"Foundation search cache max_size ({vm._search_cache._max_size}) "
            f"exceeds safe max ({MAX_ACCEPTABLE_SEARCH_CACHE_ENTRIES}); "
            "prevents unbounded memory growth in long-lived MCP."
        )
