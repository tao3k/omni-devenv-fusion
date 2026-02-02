# tests/unit/services/test_vector.py
"""
Unit tests for vector store module.
"""

from unittest.mock import patch, MagicMock

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


class TestVectorStoreGracefulDegradation:
    """Tests for graceful handling of missing collections (table not found errors).

    These tests ensure that operations on non-existent collections return
    empty results rather than propagating errors. This prevents failures
    when accessing collections like 'omni.hippocampus' that haven't been
    created yet.
    """

    def setup_method(self):
        """Reset singleton before each test."""
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection_returns_empty(self):
        """Searching a non-existent collection should return empty list, not raise error."""
        vm = VectorStoreClient()

        # Mock the store to raise "Table not found" error
        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("Table not found: omni.hippocampus")
        vm._store = mock_store

        # This should NOT raise, should return empty list
        results = await vm.search(query="test query", n_results=5, collection="omni.hippocampus")
        assert results == [], f"Expected empty list, got {results}"

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection_case_insensitive(self):
        """Error handling should be case-insensitive."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("TABLE NOT FOUND: some_collection")
        vm._store = mock_store

        results = await vm.search(query="test query", n_results=5, collection="some_collection")
        assert results == []

    @pytest.mark.asyncio
    async def test_count_nonexistent_collection_returns_zero(self):
        """Counting a non-existent collection should return 0, not raise error."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.count.side_effect = Exception("Table not found: test_collection")
        vm._store = mock_store

        count = await vm.count(collection="test_collection")
        assert count == 0, f"Expected 0, got {count}"

    @pytest.mark.asyncio
    async def test_add_nonexistent_collection_fails_silently(self):
        """Adding to a non-existent collection should return False, not raise error."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.add.side_effect = Exception("Table not found: new_collection")
        vm._store = mock_store

        result = await vm.add(
            content="test content", metadata={"key": "value"}, collection="new_collection"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_collection_fails_silently(self):
        """Deleting from a non-existent collection should return False, not raise error."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.delete.side_effect = Exception("Table not found: delete_collection")
        vm._store = mock_store

        result = await vm.delete(id="some-id", collection="delete_collection")
        assert result is False

    @pytest.mark.asyncio
    async def test_hippocampus_collection_search_graceful_handling(self):
        """Hippocampus collection search should handle missing table gracefully.

        This is the specific scenario that was failing:
        Search for 'omni.hippocampus' collection should not crash.
        """
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("Table not found: omni.hippocampus")
        vm._store = mock_store

        # This should NOT raise an error
        results = await vm.search(
            query="recall experience about python", n_results=3, collection="omni.hippocampus"
        )

        # Should return empty list (no experiences found yet is valid)
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        assert results == [], f"Expected empty list for non-existent collection, got {results}"

    @pytest.mark.asyncio
    async def test_hippocampus_count_graceful_handling(self):
        """Hippocampus collection count should handle missing table gracefully."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.count.side_effect = Exception("Table not found: omni.hippocampus")
        vm._store = mock_store

        count = await vm.count(collection="omni.hippocampus")

        # Should return 0, not raise error
        assert count == 0, f"Expected 0 for non-existent collection, got {count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
