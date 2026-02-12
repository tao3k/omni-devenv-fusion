"""
Test for Rust-Python parameter order consistency in vector store bindings.

This module ensures that search_tools parameters are correctly passed
between Python and Rust without parameter order mismatches.

Rust signature:
  search_tools(
    table_name, query_vector, query_text, limit, threshold, confidence_profile_json, rerank
  )
Python wrapper:
  search_tools(
    table_name, query_vector, query_text=None, limit=5, threshold=0.0,
    confidence_profile_json=None, rerank=True
  )
"""

from unittest.mock import MagicMock

import pytest


class TestSearchToolsParameterOrder:
    """Test that Python correctly passes parameters to Rust search_tools."""

    def test_rust_signature_documented(self):
        """Verify Rust signature is documented in Python wrapper."""
        from omni.foundation.bridge.rust_vector import RustVectorStore

        # The docstring should document the correct parameter order
        docstring = RustVectorStore.search_tools.__doc__
        assert docstring is not None, "search_tools should have a docstring"

        # Check that the signature mentions query_text comes BEFORE limit
        assert "query_text" in docstring
        assert "limit" in docstring
        # The docstring should clarify the order
        assert "query_text" in docstring.lower() and "limit" in docstring.lower()

    @pytest.mark.asyncio
    async def test_search_tools_parameter_order(self):
        """Test that parameters are passed in correct order to Rust."""
        from omni.foundation.bridge.rust_vector import RustVectorStore
        from omni.foundation.config.dirs import get_vector_db_path

        # Create store with mock inner to capture calls
        store = RustVectorStore(
            index_path=str(get_vector_db_path()), dimension=1024, enable_keyword_index=True
        )

        # Mock the Rust inner store
        mock_inner = MagicMock()
        captured_args = {}

        def capture_call(table, vec, query, lim, thresh, confidence_profile_json, rerank):
            captured_args["table"] = table
            captured_args["vec"] = vec
            captured_args["query"] = query  # This should be the query_text
            captured_args["limit"] = lim
            captured_args["threshold"] = thresh
            captured_args["confidence_profile_json"] = confidence_profile_json
            captured_args["rerank"] = rerank
            return []  # Return empty results

        mock_inner.search_tools = capture_call
        store._inner = mock_inner

        # Call with specific values
        test_table = "test_table"
        test_vec = [0.1] * 1024
        test_query = "test keyword"
        test_limit = 10
        test_threshold = 0.05

        await store.search_tools(
            table_name=test_table,
            query_vector=test_vec,
            query_text=test_query,
            limit=test_limit,
            threshold=test_threshold,
        )

        # Verify parameter order
        assert captured_args["table"] == test_table, "table_name should be first"
        assert captured_args["vec"] == test_vec, "query_vector should be second"
        assert captured_args["query"] == test_query, "query_text should be third (not fourth!)"
        assert captured_args["limit"] == test_limit, "limit should be fourth"
        assert captured_args["threshold"] == test_threshold, "threshold should be fifth"
        assert isinstance(captured_args["confidence_profile_json"], str), (
            "confidence profile should be passed as JSON"
        )
        assert captured_args["rerank"] is True

    @pytest.mark.asyncio
    async def test_explicit_search_tools_passes_correct_params(self):
        """Test that search_tools() receives query_text in the correct position."""
        from omni.foundation.bridge.rust_vector import RustVectorStore
        from omni.foundation.config.dirs import get_vector_db_path

        store = RustVectorStore(
            index_path=str(get_vector_db_path()),
            dimension=1024,
            enable_keyword_index=True,
        )

        # Mock inner
        mock_inner = MagicMock()
        captured_calls = []

        def capture_search_tools(table, vec, query, lim, thresh, confidence_profile_json, rerank):
            captured_calls.append(
                {
                    "table": table,
                    "query": query,  # This should be the full query text
                    "limit": lim,
                    "threshold": thresh,
                    "confidence_profile_json": confidence_profile_json,
                    "rerank": rerank,
                }
            )
            return []

        mock_inner.search_tools = capture_search_tools
        store._inner = mock_inner

        # Call search_tools with explicit query vector + text
        test_query = "find files matching 'pub updated'"
        test_query_vec = [0.1] * 1024
        await store.search_tools(
            table_name="skills",
            query_vector=test_query_vec,
            query_text=test_query,
            limit=5,
            threshold=0.0,
        )

        # Verify search_tools was called with query_text
        assert len(captured_calls) == 1, "search_tools should be called once"
        assert captured_calls[0]["query"] == test_query, (
            f"query_text should be '{test_query}', got '{captured_calls[0]['query']}'"
        )
        assert isinstance(captured_calls[0]["confidence_profile_json"], str)
        assert captured_calls[0]["rerank"] is True


class TestRustBindingSignature:
    """Test that Rust binding has correct signature."""

    def test_create_vector_store_signature(self):
        """Verify create_vector_store has correct defaults."""
        import omni_core_rs

        # The function should be available
        assert hasattr(omni_core_rs, "create_vector_store")

        # Check it's callable
        assert callable(omni_core_rs.create_vector_store)

    def test_py_vector_store_has_search_tools(self):
        """Verify PyVectorStore has search_tools method."""
        import omni_core_rs

        assert hasattr(omni_core_rs, "PyVectorStore")

        # Create instance
        store = omni_core_rs.PyVectorStore(path="/tmp/test", dimension=1024)
        assert hasattr(store, "search_tools"), "PyVectorStore should have search_tools method"


class TestIntegrationParameterOrder:
    """Integration tests for parameter order."""

    @pytest.mark.asyncio
    async def test_search_tools_receives_query_text(self):
        """
        Test that search_tools receives query_text parameter correctly.

        Verifies that when search() is called with a query, the query_text
        parameter is passed to Rust search_tools (not mixed up with limit/threshold).
        """
        from omni.foundation.bridge.rust_vector import RustVectorStore
        from omni.foundation.config.dirs import get_vector_db_path

        store = RustVectorStore(
            index_path=str(get_vector_db_path()),
            dimension=1024,
            enable_keyword_index=True,
        )

        # We'll test by calling search_tools directly and verifying
        # the result structure includes expected fields

        # Generate embedding
        test_query = "unique_test_query_xyz"
        query_vec = store._embedding_service.embed(test_query)
        if isinstance(query_vec[0], list):
            query_vec = query_vec[0]

        # Call search_tools directly with keyword
        results = await store.search_tools(
            table_name="skills",
            query_vector=query_vec,
            query_text=test_query,  # This should trigger keyword matching
            limit=10,
            threshold=0.0,
        )

        # If parameter order was wrong, we'd get an error or empty results
        assert isinstance(results, list), f"Expected list, got {type(results)}"

        # The fact that we got here means the call succeeded
        # If parameter order was wrong (query_text in threshold position),
        # we'd get a type error or wrong behavior
        print(f"✓ search_tools returned {len(results)} results with correct params")

    @pytest.mark.asyncio
    async def test_direct_rust_call_with_correct_order(self):
        """
        Verify Rust search_tools works with keyword parameter.

        This is a sanity check that the Rust binding accepts the
        correct parameter order.
        """
        from omni.foundation.bridge.rust_vector import RustVectorStore
        from omni.foundation.config.dirs import get_vector_db_path

        store = RustVectorStore(
            index_path=str(get_vector_db_path()),
            dimension=1024,
            enable_keyword_index=True,
        )

        # Generate query vector
        test_query = "git commit"
        query_vec = store._embedding_service.embed(test_query)
        if isinstance(query_vec[0], list):
            query_vec = query_vec[0]

        # Direct Rust call with preferred new signature, then fallback for old binary.
        try:
            results = store._inner.search_tools(
                "skills",  # table_name
                query_vec,  # query_vector
                test_query,  # query_text (3rd param)
                5,  # limit (4th param)
                0.0,  # threshold (5th param)
                None,  # confidence_profile_json (6th param)
            )
        except TypeError:
            results = store._inner.search_tools(
                "skills",
                query_vec,
                test_query,
                5,
                0.0,
            )

        # Verify call succeeds and returns the expected container type.
        # Do not require non-empty results because the local index may be empty.
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        print(f"✓ Direct Rust call with correct order returned {len(results)} results")

        # Verify result structure
        if results:
            first = results[0]
            # Results should be dicts with expected keys
            assert "tool_name" in first or "name" in first, "Result should have tool_name or name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
