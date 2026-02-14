# tests/unit/services/test_vector.py
"""
Unit tests for vector store module.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.foundation.services.vector import (
    SearchResult,
    VectorStoreClient,
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

        # When bridge get_vector_store raises, store should be None
        with patch(
            "omni.foundation.bridge.rust_vector.get_vector_store",
            side_effect=ImportError("no rust"),
        ):
            store = vm.store
            assert store is None, "store should be None when bridge is unavailable"


class TestVectorStoreUsesBridge:
    """Store is obtained from bridge get_vector_store (single factory)."""

    def setup_method(self):
        VectorStoreClient._instance = None
        VectorStoreClient._store = None

    def test_store_comes_from_bridge_when_available(self):
        """vm.store returns the store from bridge get_vector_store when patch provides it."""
        mock_store = MagicMock()
        with patch("omni.foundation.bridge.rust_vector.get_vector_store", return_value=mock_store):
            vm = VectorStoreClient()
            assert vm.store is mock_store


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

    def test_is_table_not_found_helper(self):
        """Table-not-found classifier should be stable across variants."""
        assert VectorStoreClient._is_table_not_found(Exception("Table not found: knowledge"))
        assert VectorStoreClient._is_table_not_found(Exception("NOT FOUND"))
        assert not VectorStoreClient._is_table_not_found(Exception("permission denied"))

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection_returns_empty(self):
        """Searching a non-existent collection should return empty list, not raise error."""
        vm = VectorStoreClient()

        # Mock the store to raise "Table not found" error
        mock_store = MagicMock()
        mock_store.search_optimized.side_effect = Exception("Table not found: omni.hippocampus")
        vm._store = mock_store

        # This should NOT raise, should return empty list
        results = await vm.search(query="test query", n_results=5, collection="omni.hippocampus")
        assert results == [], f"Expected empty list, got {results}"

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection_case_insensitive(self):
        """Error handling should be case-insensitive."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.search_optimized.side_effect = Exception("TABLE NOT FOUND: some_collection")
        vm._store = mock_store

        results = await vm.search(query="test query", n_results=5, collection="some_collection")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_parses_vector_schema_v1_payload(self):
        """Vector search should parse canonical v1 payload."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = [
            '{"schema":"omni.vector.search.v1","id":"doc-1","content":"typed text","metadata":{"tag":"docs"},"distance":0.2,"score":0.8333}'
        ]
        vm._store = mock_store

        results = await vm.search(query="typed", n_results=3, collection="knowledge")
        assert len(results) == 1
        assert results[0].id == "doc-1"
        assert results[0].content == "typed text"
        assert results[0].metadata["tag"] == "docs"
        assert results[0].distance == 0.2
        assert results[0].score == pytest.approx(0.8333)

    @pytest.mark.asyncio
    async def test_search_rejects_unknown_vector_schema(self):
        """Vector search should reject unknown schema versions."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = [
            '{"schema":"omni.vector.search.v2","id":"doc-1","content":"typed text","metadata":{},"distance":0.2}'
        ]
        vm._store = mock_store

        results = await vm.search(query="typed", n_results=3, collection="knowledge")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_prefers_optimized_api_when_available(self):
        """search() should use search_optimized when binding supports it."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = [
            '{"schema":"omni.vector.search.v1","id":"doc-1","content":"typed text","metadata":{"tag":"docs"},"distance":0.2}'
        ]
        vm._store = mock_store

        results = await vm.search(query="typed", n_results=3, collection="knowledge")
        assert len(results) == 1
        mock_store.search_optimized.assert_called_once()
        mock_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_forwards_optimized_options_payload(self):
        """search() should serialize and pass scanner tuning options."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = []
        vm._store = mock_store

        await vm.search(
            query="typed",
            n_results=3,
            collection="knowledge",
            where_filter={"name": "tool.echo"},
            batch_size=512,
            fragment_readahead=2,
            batch_readahead=8,
            scan_limit=32,
        )

        args = mock_store.search_optimized.call_args[0]
        assert args[0] == "knowledge"
        assert args[2] == 3
        options = json.loads(args[3])
        assert options["where_filter"] == json.dumps({"name": "tool.echo"})
        assert options["batch_size"] == 512
        assert options["fragment_readahead"] == 2
        assert options["batch_readahead"] == 8
        assert options["scan_limit"] == 32

    @pytest.mark.asyncio
    async def test_search_optimized_omits_options_payload_when_defaults(self):
        """search() should pass None options_json when no scanner options are set."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = []
        vm._store = mock_store

        await vm.search(query="typed", n_results=3, collection="knowledge")

        args = mock_store.search_optimized.call_args[0]
        assert args[0] == "knowledge"
        assert args[2] == 3
        assert args[3] is None

    @pytest.mark.asyncio
    async def test_search_optimized_passes_string_where_filter_without_reencoding(self):
        """String where_filter should be forwarded directly to options_json."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = []
        vm._store = mock_store
        raw_filter = "name = 'tool.echo'"

        await vm.search(
            query="typed",
            n_results=3,
            collection="knowledge",
            where_filter=raw_filter,
            scan_limit=7,
        )

        args = mock_store.search_optimized.call_args[0]
        options = json.loads(args[3])
        assert options["where_filter"] == raw_filter
        assert options["scan_limit"] == 7

    @pytest.mark.asyncio
    async def test_search_optimized_binding_is_required(self):
        """search() should reject legacy search-only bindings."""

        class _LegacyStore:
            def search(self, *_args, **_kwargs):
                return []

        vm = VectorStoreClient()
        vm._store = _LegacyStore()

        results = await vm.search(query="typed", n_results=3, collection="knowledge")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_rejects_invalid_scanner_options(self):
        """Invalid scanner options should be rejected before Rust call."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_optimized.return_value = []
        vm._store = mock_store

        results = await vm.search(
            query="typed",
            n_results=3,
            collection="knowledge",
            batch_size=0,
        )

        assert results == []
        mock_store.search_optimized.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_rejects_invalid_n_results(self):
        """n_results must be within contract bounds."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        vm._store = mock_store

        too_small = await vm.search(query="typed", n_results=0, collection="knowledge")
        too_large = await vm.search(query="typed", n_results=1001, collection="knowledge")

        assert too_small == []
        assert too_large == []
        mock_store.search_optimized.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_logs_error_code_for_invalid_n_results(self):
        """Request validation failures should emit stable error_code."""
        vm = VectorStoreClient()
        with patch("omni.foundation.services.vector.logger.error") as mock_error:
            results = await vm.search(query="typed", n_results=0, collection="knowledge")
        assert results == []
        assert mock_error.called
        kwargs = mock_error.call_args.kwargs
        assert kwargs["error_code"] == "VECTOR_REQUEST_VALIDATION"
        assert kwargs["cause"] == "request_validation"

    @pytest.mark.asyncio
    async def test_search_logs_error_code_for_missing_binding_api(self):
        """Binding contract violations should emit stable error_code."""

        class _LegacyStore:
            def search(self, *_args, **_kwargs):
                return []

        vm = VectorStoreClient()
        vm._store = _LegacyStore()

        with patch("omni.foundation.services.vector.logger.error") as mock_error:
            results = await vm.search(query="typed", n_results=3, collection="knowledge")
        assert results == []
        assert mock_error.called
        kwargs = mock_error.call_args.kwargs
        assert kwargs["error_code"] == "VECTOR_BINDING_API_MISSING"
        assert kwargs["cause"] == "binding_contract"

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
        # Use add_documents which is what the actual code calls
        mock_store.add_documents.side_effect = Exception("Table not found: new_collection")
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
        mock_store.delete_by_ids.side_effect = Exception("Table not found: delete_collection")
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
        mock_store.search_optimized.side_effect = Exception("Table not found: omni.hippocampus")
        vm._store = mock_store

        # This should NOT raise an error
        results = await vm.search(
            query="recall experience about python", n_results=3, collection="omni.hippocampus"
        )

        # Should return empty list (no experiences found yet is valid)
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        assert results == [], f"Expected empty list for non-existent collection, got {results}"

    @pytest.mark.asyncio
    async def test_get_table_info_parses_json(self):
        """get_table_info should parse JSON response into dict."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.get_table_info.return_value = '{"version_id":7,"num_rows":3}'
        vm._store = mock_store

        info = await vm.get_table_info(collection="knowledge")
        assert info == {"version_id": 7, "num_rows": 3}

    @pytest.mark.asyncio
    async def test_list_versions_parses_json(self):
        """list_versions should parse JSON response into list."""
        vm = VectorStoreClient()

        mock_store = MagicMock()
        mock_store.list_versions.return_value = '[{"version_id":6},{"version_id":7}]'
        vm._store = mock_store

        versions = await vm.list_versions(collection="knowledge")
        assert versions == [{"version_id": 6}, {"version_id": 7}]

    @pytest.mark.asyncio
    async def test_schema_evolution_calls_use_payload_contract(self):
        """Schema evolution methods call store with collection and columns/alterations (bridge API)."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.add_columns = AsyncMock(return_value=True)
        mock_store.alter_columns = AsyncMock(return_value=True)
        mock_store.drop_columns = AsyncMock(return_value=True)
        vm._store = mock_store

        columns = [{"name": "custom_note", "data_type": "Utf8", "nullable": True}]
        alterations = [{"Rename": {"path": "custom_note", "new_name": "custom_label"}}]
        ok_add = await vm.add_columns(collection="knowledge", columns=columns)
        ok_alter = await vm.alter_columns(collection="knowledge", alterations=alterations)
        ok_drop = await vm.drop_columns(collection="knowledge", columns=["custom_label"])

        assert ok_add is True
        assert ok_alter is True
        assert ok_drop is True
        mock_store.add_columns.assert_awaited_once_with("knowledge", columns)
        mock_store.alter_columns.assert_awaited_once_with("knowledge", alterations)
        mock_store.drop_columns.assert_awaited_once_with("knowledge", ["custom_label"])

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

    @pytest.mark.asyncio
    async def test_search_hybrid_parses_rust_results(self):
        """Hybrid search should parse Rust hybrid payload to SearchResult."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = [
            '{"schema":"omni.vector.hybrid.v1","id":"git.commit","content":"Commit changes safely","metadata":{"domain":"git"},"score":0.91,"source":"hybrid"}'
        ]
        vm._store = mock_store

        results = await vm.search_hybrid(query="git commit", n_results=3, collection="skills")
        assert len(results) == 1
        assert results[0].id == "git.commit"
        assert "Commit changes" in results[0].content
        assert results[0].metadata["domain"] == "git"

    @pytest.mark.asyncio
    async def test_search_hybrid_rejects_noncanonical_payload(self):
        """Hybrid parser should reject legacy payload missing canonical fields."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = [
            '{"tool_name":"git.status","rrf_score":0.77,"vector_score":0.32,"keyword_score":1.8}'
        ]
        vm._store = mock_store

        results = await vm.search_hybrid(query="git status", n_results=3, collection="skills")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_hybrid_prefers_id_content_metadata_shape(self):
        """Hybrid parser should preserve normalized id/content/metadata payload."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = [
            '{"schema":"omni.vector.hybrid.v1","id":"doc-1","content":"Typed languages catch errors early.","metadata":{"tag":"docs"},"source":"hybrid","score":0.88}'
        ]
        vm._store = mock_store

        results = await vm.search_hybrid(
            query="typed language", n_results=2, collection="knowledge"
        )
        assert len(results) == 1
        assert results[0].id == "doc-1"
        assert "catch errors" in results[0].content
        assert results[0].metadata.get("tag") == "docs"

    @pytest.mark.asyncio
    async def test_search_hybrid_preserves_debug_scores_in_metadata(self):
        """Hybrid parser should keep optional engine debug scores under metadata.debug_scores."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = [
            '{"schema":"omni.vector.hybrid.v1","id":"doc-1","content":"Typed languages catch errors early.","metadata":{"tag":"docs"},"source":"hybrid","score":0.88,"vector_score":0.4,"keyword_score":0.6}'
        ]
        vm._store = mock_store

        results = await vm.search_hybrid(
            query="typed language", n_results=2, collection="knowledge"
        )
        assert len(results) == 1
        debug = results[0].metadata.get("debug_scores", {})
        assert debug.get("vector_score") == 0.4
        assert debug.get("keyword_score") == 0.6

    @pytest.mark.asyncio
    async def test_search_hybrid_passes_keywords_to_store(self):
        """Hybrid search should forward explicit keyword hints to Rust binding."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.return_value = []
        vm._store = mock_store

        await vm.search_hybrid(
            query="typed language",
            n_results=4,
            collection="knowledge",
            keywords=["type", "compile"],
        )
        mock_store.search_hybrid.assert_called_once()
        args = mock_store.search_hybrid.call_args[0]
        assert args[0] == "knowledge"
        assert args[2] == ["compile", "type"]
        assert args[3] == 4

    @pytest.mark.asyncio
    async def test_search_hybrid_nonexistent_collection_returns_empty(self):
        """Hybrid search should gracefully handle missing table errors."""
        vm = VectorStoreClient()
        mock_store = MagicMock()
        mock_store.search_hybrid.side_effect = Exception("Table not found: missing")
        vm._store = mock_store

        results = await vm.search_hybrid(
            query="typed language",
            n_results=5,
            collection="missing",
        )
        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
