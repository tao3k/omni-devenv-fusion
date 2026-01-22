# tests/unit/services/test_vector.py
"""
Unit tests for vector store module.
"""

from unittest.mock import MagicMock, patch

import pytest

from omni.foundation.services.vector import (
    SearchResult,
    VectorStoreClient,
    _get_omni_vector,
    get_vector_store,
)


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self):
        """SearchResult should be created with correct values."""
        result = SearchResult(
            content="test content", metadata={"key": "value"}, distance=0.5, id="test-id"
        )
        assert result.content == "test content"
        assert result.metadata == {"key": "value"}
        assert result.distance == 0.5
        assert result.id == "test-id"

    def test_search_result_default_values(self):
        """SearchResult should have default empty values."""
        result = SearchResult(content="", metadata={}, distance=0.0, id="")
        assert result.content == ""
        assert result.metadata == {}


class TestVectorStoreClientSingleton:
    """Tests for VectorStoreClient singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    def test_singleton_returns_same_instance(self):
        """Multiple calls should return same instance."""
        vm1 = VectorStoreClient()
        vm2 = VectorStoreClient()
        assert vm1 is vm2

    def test_singleton_via_get_vector_store(self):
        """get_vector_store should return singleton."""
        vm1 = get_vector_store()
        vm2 = get_vector_store()
        assert vm1 is vm2


class TestVectorStoreClientPath:
    """Tests for path property."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    def test_path_property(self):
        """VectorStoreClient should have path property."""
        vm = VectorStoreClient()
        assert hasattr(vm, "path")


class TestVectorStoreClientAPI:
    """Tests for VectorStoreClient API correctness."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    def test_vector_store_client_has_store_property(self):
        """VectorStoreClient should have 'store' property."""
        vm = VectorStoreClient()
        assert hasattr(vm, "store"), "VectorStoreClient should have 'store' property"

    def test_vector_store_client_has_no_client_attribute(self):
        """VectorStoreClient should NOT have 'client' attribute."""
        vm = VectorStoreClient()
        assert not hasattr(vm, "client"), (
            "VectorStoreClient should NOT have 'client' attribute. Use 'store' property instead."
        )

    def test_vector_store_client_has_path_property(self):
        """VectorStoreClient should have 'path' property."""
        vm = VectorStoreClient()
        assert hasattr(vm, "path"), "VectorStoreClient should have 'path' property"


class TestVectorStoreClientAvailability:
    """Tests for checking vector store availability."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    def test_check_store_availability_with_store_property(self):
        """Check 'vm.store' for availability."""
        vm = VectorStoreClient()

        # Without omni-vector available, store should be None
        with patch("omni.foundation.services.vector._get_omni_vector", return_value=None):
            store = vm.store
            assert store is None, "store should be None when omni-vector is not available"


class TestLazyImports:
    """Tests for lazy import functions."""

    def test_get_omni_vector_caches_result(self):
        """_get_omni_vector should cache the result."""
        with patch("omni.foundation.services.vector._cached_omni_vector", None):
            # First call should initialize
            result1 = _get_omni_vector()
            # Second call should return cached
            result2 = _get_omni_vector()
            assert result1 is result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
