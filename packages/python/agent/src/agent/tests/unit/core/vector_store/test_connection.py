# tests/unit/core/vector_store/test_connection.py
"""
Unit tests for vector store connection module.
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.core.vector_store.connection import (
    VectorMemory,
    SearchResult,
    get_vector_memory,
    _get_omni_vector,
    _get_logger,
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


class TestVectorMemorySingleton:
    """Tests for VectorMemory singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_singleton_returns_same_instance(self):
        """Multiple calls should return same instance."""
        vm1 = VectorMemory()
        vm2 = VectorMemory()
        assert vm1 is vm2

    def test_singleton_via_get_vector_memory(self):
        """get_vector_memory should return singleton."""
        vm1 = get_vector_memory()
        vm2 = get_vector_memory()
        assert vm1 is vm2

    def test_default_dimension(self):
        """VectorMemory should have correct default dimension."""
        vm = VectorMemory()
        assert vm.DEFAULT_DIMENSION == 1536

    def test_default_table_name(self):
        """VectorMemory should have correct default table."""
        vm = VectorMemory()
        assert vm._default_table == "project_knowledge"


class TestVectorMemoryTableName:
    """Tests for table name handling."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_get_table_name_with_collection(self):
        """_get_table_name should return provided collection name."""
        vm = VectorMemory()
        result = vm._get_table_name("custom_table")
        assert result == "custom_table"

    def test_get_table_name_without_collection(self):
        """_get_table_name should return default table when None."""
        vm = VectorMemory()
        result = vm._get_table_name(None)
        assert result == "project_knowledge"


class TestVectorMemoryJsonMetadata:
    """Tests for JSON metadata handling."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_json_to_metadata_valid_json(self):
        """_json_to_metadata should parse valid JSON."""
        vm = VectorMemory()
        result = vm._json_to_metadata('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_to_metadata_empty_string(self):
        """_json_to_metadata should return empty dict for empty string."""
        vm = VectorMemory()
        result = vm._json_to_metadata("")
        assert result == {}

    def test_json_to_metadata_invalid_json(self):
        """_json_to_metadata should return empty dict for invalid JSON."""
        vm = VectorMemory()
        result = vm._json_to_metadata("invalid json")
        assert result == {}


class TestVectorMemoryStore:
    """Tests for store property."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_store_property_returns_store(self):
        """store property should return the underlying store."""
        vm = VectorMemory()
        # store is lazy-loaded, so accessing it should work
        with patch("agent.core.vector_store.connection._get_omni_vector", return_value=None):
            store = vm.store
            assert store is None

    def test_store_cached_after_first_access(self):
        """Store should be cached after first access."""
        vm = VectorMemory()
        with patch("agent.core.vector_store.connection._get_omni_vector") as mock:
            mock.return_value = MagicMock()
            _ = vm.store
            _ = vm.store
            # Should only be called once due to caching
            assert mock.call_count == 1


class TestVectorMemoryAPI:
    """Tests to prevent regression of incorrect VectorMemory API usage.

    These tests ensure the correct API is used:
    - Use 'store' property to access the underlying vector store
    - Do NOT use 'client' attribute (does not exist)
    """

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_vector_memory_has_store_property(self):
        """VectorMemory should have 'store' property for accessing the underlying store."""
        vm = VectorMemory()
        assert hasattr(vm, "store"), "VectorMemory should have 'store' property"

    def test_vector_memory_has_no_client_attribute(self):
        """VectorMemory should NOT have 'client' attribute.

        Regression test: Prevents code from using incorrect 'client' attribute.
        The correct way to access the underlying store is via 'store' property.
        """
        vm = VectorMemory()
        assert not hasattr(vm, "client"), (
            "VectorMemory should NOT have 'client' attribute. "
            "Use 'store' property instead to access the underlying vector store."
        )

    def test_vector_memory_has_ensure_store_method(self):
        """VectorMemory should have '_ensure_store' method for lazy initialization."""
        vm = VectorMemory()
        assert hasattr(vm, "_ensure_store"), "VectorMemory should have '_ensure_store' method"
        assert callable(vm._ensure_store), "_ensure_store should be callable"


class TestVectorMemoryAvailabilityCheck:
    """Tests for correct way to check if vector memory is available."""

    def setup_method(self):
        """Reset singleton before each test."""
        VectorMemory._instance = None
        VectorMemory._store = None
        VectorMemory._initialized = False

    def test_check_store_availability_with_store_property(self):
        """Correct pattern: Check 'vm.store' for availability."""
        vm = VectorMemory()

        # Without omni-vector available, store should be None
        with patch("agent.core.vector_store.connection._get_omni_vector", return_value=None):
            store = vm.store
            assert store is None, "store should be None when omni-vector is not available"

    def test_client_attribute_does_not_exist_pattern(self):
        """Demonstrate that using 'client' would fail.

        This test verifies the incorrect pattern would raise AttributeError.
        """
        vm = VectorMemory()

        # Attempting to access 'client' should raise AttributeError
        with pytest.raises(AttributeError, match="'VectorMemory' object has no attribute 'client'"):
            _ = vm.client  # noqa: F841


class TestLazyImports:
    """Tests for lazy import functions."""

    def test_get_omni_vector_caches_result(self):
        """_get_omni_vector should cache the result."""
        with patch("agent.core.vector_store.connection._cached_omni_vector", None):
            # First call should initialize
            result1 = _get_omni_vector()
            # Second call should return cached
            result2 = _get_omni_vector()
            assert result1 is result2

    def test_get_logger_caches_result(self):
        """_get_logger should cache the result."""
        with patch("agent.core.vector_store.connection._cached_logger", None):
            import structlog

            result1 = _get_logger()
            result2 = _get_logger()
            assert result1 is result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
