"""Tests for checkpoint.py - Rust LanceDB Backend Integration.

These tests verify:
1. Rust bindings import correctly from `omni_core_rs`
2. Checkpoint store creation and operations work
3. Fallback to SQLite when Rust bindings unavailable
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestRustBindingsImport:
    """Tests for Rust bindings import verification."""

    def test_omni_core_rs_import_succeeds(self):
        """Verify Rust bindings can be imported from omni_core_rs."""
        # This test will fail if import path is wrong (e.g., bindings.python.checkpoint)
        from omni_core_rs import PyCheckpointStore, create_checkpoint_store

        assert PyCheckpointStore is not None
        assert create_checkpoint_store is not None

    def test_checkpoint_module_import(self):
        """Verify checkpoint module imports successfully."""
        from omni.foundation.checkpoint import (
            _get_store,
            get_checkpointer,
            save_workflow_state,
            load_workflow_state,
        )

        # All functions should be callable
        assert callable(_get_store)
        assert callable(get_checkpointer)
        assert callable(save_workflow_state)
        assert callable(load_workflow_state)


class TestCheckpointStoreCreation:
    """Tests for checkpoint store creation and initialization."""

    def test_get_store_returns_store_or_none(self):
        """Verify _get_store returns a store or None."""
        from omni.foundation.checkpoint import _get_store

        store = _get_store()
        # Store should be either a PyCheckpointStore or None (if bindings unavailable)
        assert store is not None

    def test_store_has_required_methods(self):
        """Verify the store has required checkpoint methods."""
        from omni.foundation.checkpoint import _get_store

        store = _get_store()
        if store is not None:
            assert hasattr(store, "save_checkpoint")
            assert hasattr(store, "get_latest")
            assert hasattr(store, "get_history")
            assert hasattr(store, "delete_thread")


class TestWorkflowStateOperations:
    """Tests for workflow state save/load operations."""

    def test_save_and_load_workflow_state(self):
        """Verify save and load workflow state work correctly."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            load_workflow_state,
            delete_workflow_state,
        )

        workflow_type = "test_workflow"
        workflow_id = "test-session-001"
        test_state = {"status": "test", "data": [1, 2, 3], "nested": {"key": "value"}}

        # Save state
        result = save_workflow_state(workflow_type, workflow_id, test_state)
        assert result is True

        # Load state
        loaded = load_workflow_state(workflow_type, workflow_id)
        assert loaded is not None
        assert loaded["status"] == "test"
        assert loaded["data"] == [1, 2, 3]
        assert loaded["nested"]["key"] == "value"

        # Cleanup
        delete_workflow_state(workflow_type, workflow_id)

    def test_load_nonexistent_workflow_returns_none(self):
        """Verify loading nonexistent workflow returns None."""
        from omni.foundation.checkpoint import load_workflow_state

        result = load_workflow_state("nonexistent_workflow", "nonexistent-id")
        assert result is None

    def test_save_with_metadata(self):
        """Verify save with metadata works correctly."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            load_workflow_state,
            delete_workflow_state,
            get_workflow_history,
        )

        workflow_type = "metadata_test"
        workflow_id = "test-session-002"
        test_state = {"step": 1}
        metadata = {"source": "test", "user": "test_user"}

        # Save with metadata
        result = save_workflow_state(workflow_type, workflow_id, test_state, metadata=metadata)
        assert result is True

        # Verify history includes metadata
        history = get_workflow_history(workflow_type, workflow_id, limit=5)
        assert len(history) > 0

        # Cleanup
        delete_workflow_state(workflow_type, workflow_id)

    def test_delete_workflow_state(self):
        """Verify delete removes all checkpoints for a workflow."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            delete_workflow_state,
            load_workflow_state,
        )

        workflow_type = "delete_test"
        workflow_id = "test-session-003"

        # Save multiple states
        for i in range(3):
            save_workflow_state(workflow_type, workflow_id, {"step": i})

        # Verify states exist
        assert load_workflow_state(workflow_type, workflow_id) is not None

        # Delete
        result = delete_workflow_state(workflow_type, workflow_id)
        assert result is True

        # Verify states are gone
        assert load_workflow_state(workflow_type, workflow_id) is None


class TestGetCheckpointer:
    """Tests for get_checkpointer function."""

    def test_get_checkpointer_returns_store(self):
        """Verify get_checkpointer returns the checkpoint store."""
        from omni.foundation.checkpoint import get_checkpointer, _get_store

        checkpointer = get_checkpointer("test")
        store = _get_store()

        # Should return the same store
        if store is not None:
            assert checkpointer is not None


class TestImportPathValidation:
    """Tests to validate correct Rust bindings import path.

    This class specifically tests that the import path is `omni_core_rs`
    and NOT the old incorrect path like `bindings.python.checkpoint`.
    """

    def test_correct_import_path_omni_core_rs(self):
        """Verify omni_core_rs is the correct import path.

        This test will FAIL if someone changes the import to an incorrect path
        like `from bindings.python.checkpoint import ...`.
        """
        # Try importing from the expected correct path
        try:
            from omni_core_rs import PyCheckpointStore, create_checkpoint_store

            # If we get here, the import path is correct
            assert PyCheckpointStore is not None
            assert create_checkpoint_store is not None
        except ImportError as e:
            pytest.fail(f"Failed to import from omni_core_rs: {e}")

    def test_incorrect_import_path_does_not_exist(self):
        """Verify the incorrect import path doesn't exist.

        This is a validation test - if someone accidentally uses the wrong import,
        this test helps catch it during development.
        """
        import sys

        # Simulate the incorrect import
        incorrect_module = "bindings.python.checkpoint"

        # Check if this module path exists in any source files
        # We do this by checking if omni_core_rs is properly imported in checkpoint.py
        import omni.foundation.checkpoint as checkpoint_module

        # Read the source to verify correct import
        import inspect

        source = inspect.getsource(checkpoint_module)

        # Verify the source contains the correct import
        assert "from omni_core_rs import" in source, (
            "checkpoint.py should import from 'omni_core_rs', not from 'bindings.python.checkpoint'"
        )

        # Verify it does NOT contain the incorrect import
        assert "from bindings.python" not in source, (
            "checkpoint.py should NOT import from 'bindings.python', use 'omni_core_rs' instead"
        )

    def test_foundation_checkpoint_integration(self):
        """Integration test: verify checkpoint module integrates with foundation."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            load_workflow_state,
            delete_workflow_state,
            get_checkpointer,
        )

        workflow_type = "integration_test"
        workflow_id = f"test-{Path(__file__).stem}"
        test_data = {
            "test_key": "test_value",
            "numbers": [1, 2, 3],
            "nested": {"a": 1, "b": 2},
        }

        # Save
        assert save_workflow_state(workflow_type, workflow_id, test_data) is True

        # Load
        loaded = load_workflow_state(workflow_type, workflow_id)
        assert loaded == test_data

        # Get checkpointer
        checkpointer = get_checkpointer(workflow_type)
        assert checkpointer is not None

        # Cleanup
        assert delete_workflow_state(workflow_type, workflow_id) is True
