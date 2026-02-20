"""Tests for checkpoint.py - Rust LanceDB Backend Integration.

These tests verify:
1. Rust bindings import correctly from `omni_core_rs`
2. Checkpoint store creation and operations work
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_checkpoint_store(tmp_path, monkeypatch):
    """Isolate checkpoint DB path per test to avoid cross-test schema conflicts."""
    checkpoint_db = tmp_path / "checkpoints.lance"

    # Force checkpoint path to an isolated temp location.
    monkeypatch.setattr(
        "omni.foundation.config.database.get_checkpoint_db_path",
        lambda: checkpoint_db,
    )

    # Reset per-process checkpoint store cache before and after each test.
    import omni.foundation.checkpoint as checkpoint_module

    checkpoint_module._checkpoint_store_cache.clear()
    yield
    checkpoint_module._checkpoint_store_cache.clear()


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
            load_workflow_state,
            save_workflow_state,
        )

        # All functions should be callable
        assert callable(_get_store)
        assert callable(get_checkpointer)
        assert callable(save_workflow_state)
        assert callable(load_workflow_state)


class TestCheckpointStoreCreation:
    """Tests for checkpoint store creation and initialization."""

    def test_get_store_returns_store(self):
        """Verify _get_store always returns a Rust-backed store."""
        from omni.foundation.checkpoint import _get_store

        store = _get_store()
        assert store is not None

    def test_store_has_required_methods(self):
        """Verify the store has required checkpoint methods."""
        from omni.foundation.checkpoint import _get_store

        store = _get_store()
        assert hasattr(store, "save_checkpoint")
        assert hasattr(store, "get_latest")
        assert hasattr(store, "get_history")
        assert hasattr(store, "delete_thread")

    def test_get_store_fails_fast_when_rust_bindings_missing(self, monkeypatch) -> None:
        """Rust-only contract: missing omni_core_rs must raise RuntimeError."""
        import omni.foundation.checkpoint as checkpoint_module

        checkpoint_module._checkpoint_store_cache.clear()
        monkeypatch.setitem(sys.modules, "omni_core_rs", types.ModuleType("omni_core_rs"))

        with pytest.raises(RuntimeError, match="omni_core_rs"):
            checkpoint_module._get_store()


class TestWorkflowStateOperations:
    """Tests for workflow state save/load operations."""

    def test_save_and_load_workflow_state(self):
        """Verify save and load workflow state work correctly."""
        from omni.foundation.checkpoint import (
            delete_workflow_state,
            load_workflow_state,
            save_workflow_state,
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
            delete_workflow_state,
            get_workflow_history,
            save_workflow_state,
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
            delete_workflow_state,
            load_workflow_state,
            save_workflow_state,
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

    def test_load_workflow_state_auto_repair_retries_once(self, monkeypatch: pytest.MonkeyPatch):
        """On load failure, auto-repair should run and retry once."""
        import omni.foundation.checkpoint as checkpoint_module

        class _FakeStore:
            def __init__(self):
                self.calls = 0
                self.cleaned = 0

            def get_latest(self, _table_name: str, _thread_id: str):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("broken checkpoint chain")
                return json.dumps({"status": "recovered"})

            def cleanup_orphan_checkpoints(self, _table_name: str, _dry_run: bool):
                self.cleaned += 1
                return 3

        fake = _FakeStore()
        monkeypatch.setattr(checkpoint_module, "_get_store", lambda: fake)
        monkeypatch.setattr(checkpoint_module, "get_setting", lambda _k, default=None: default)

        out = checkpoint_module.load_workflow_state("repair_test", "wf-1")
        assert out is not None
        assert out["status"] == "recovered"
        assert fake.calls == 2
        assert fake.cleaned == 1

    def test_get_checkpoint_schema_id_prefers_store_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import omni.foundation.checkpoint as checkpoint_module

        class _FakeStore:
            @staticmethod
            def checkpoint_schema_id() -> str:
                return "https://schemas.omni.dev/omni.checkpoint.record.v1.schema.json"

        monkeypatch.setattr(checkpoint_module, "_get_store", lambda: _FakeStore())
        out = checkpoint_module.get_checkpoint_schema_id()
        assert out.endswith("/omni.checkpoint.record.v1.schema.json")

    def test_repair_workflow_state_runs_cleanup_and_force(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import omni.foundation.checkpoint as checkpoint_module

        class _FakeStore:
            def __init__(self) -> None:
                self.force_calls = 0

            @staticmethod
            def checkpoint_schema_id() -> str:
                return "https://schemas.omni.dev/omni.checkpoint.record.v1.schema.json"

            @staticmethod
            def cleanup_orphan_checkpoints(_table_name: str, _dry_run: bool) -> int:
                return 5

            def force_recover_table(self, _table_name: str) -> None:
                self.force_calls += 1

        fake = _FakeStore()
        monkeypatch.setattr(checkpoint_module, "_get_store", lambda: fake)

        result = checkpoint_module.repair_workflow_state(
            "repair_workflow",
            dry_run=False,
            force_recover=True,
        )

        assert result["status"] == "success"
        assert result["removed_orphans"] == 5
        assert str(result["schema_id"]).endswith("/omni.checkpoint.record.v1.schema.json")
        assert fake.force_calls == 1


class TestGetCheckpointer:
    """Tests for get_checkpointer function."""

    def test_get_checkpointer_returns_store(self):
        """Verify get_checkpointer returns the checkpoint store."""
        from omni.foundation.checkpoint import _get_store, get_checkpointer

        checkpointer = get_checkpointer("test")
        store = _get_store()

        # Should return the same store
        assert checkpointer is store


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

        # Check if this module path exists in any source files
        # We do this by checking if omni_core_rs is properly imported in checkpoint.py
        # Read the source to verify correct import
        import inspect

        import omni.foundation.checkpoint as checkpoint_module

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
            delete_workflow_state,
            get_checkpointer,
            load_workflow_state,
            save_workflow_state,
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
