"""Unit tests for RustCheckpointSaver (LangGraph-compatible checkpoint saver).

Tests the LangGraph BaseCheckpointSaver interface implementation.
Uses a simpler approach without complex module patching.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestRustCheckpointSaverUnit:
    """Unit tests for RustCheckpointSaver - pure unit tests without module imports."""

    def _create_saver_with_mock_checkpointer(self):
        """Helper to create a saver with a mocked checkpointer."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        mock_checkpointer = MagicMock()
        # Patch at the class level where it's used
        with patch.object(
            RustCheckpointSaver,
            "__init__",
            lambda self, table_name="checkpoints", uri=None, dimension=1536: None,
        ):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._table_name = "checkpoints"
            saver._checkpointer = mock_checkpointer
        return saver, mock_checkpointer

    def test_class_instantiation(self):
        """Test RustCheckpointSaver can be instantiated with custom params."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        mock_checkpointer = MagicMock()
        with patch.object(
            RustCheckpointSaver,
            "__init__",
            lambda self, table_name="checkpoints", uri=None, dimension=1536: None,
        ):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._table_name = "checkpoints"
            saver._checkpointer = mock_checkpointer

        assert saver._table_name == "checkpoints"
        assert saver._checkpointer is mock_checkpointer

    def test_config_specs_property(self):
        """Test config_specs returns empty list."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        assert saver.config_specs == []

    def test_get_logic_with_thread_id(self):
        """Test get() returns checkpoint data when thread_id exists."""
        expected_state = {"status": "test", "data": [1, 2, 3]}
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = expected_state

        config = {"configurable": {"thread_id": "session-123"}}
        result = saver.get(config)

        assert result is not None
        # LATEST_VERSION is 2 in saver.py
        assert result["v"] == 2
        # _make_checkpoint puts state in channel_values
        assert result["channel_values"] == expected_state
        mock_checkpointer.get.assert_called_once_with("session-123")

    def test_get_logic_without_thread_id(self):
        """Test get() returns None when no thread_id in config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = {"status": "test"}

        config = {"other": "value"}
        result = saver.get(config)

        assert result is None
        mock_checkpointer.get.assert_not_called()

    def test_get_logic_with_none_state(self):
        """Test get() returns None when checkpointer returns None."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = None

        config = {"configurable": {"thread_id": "nonexistent"}}
        result = saver.get(config)

        assert result is None

    def test_get_tuple_logic(self):
        """Test get_tuple() returns CheckpointTuple when state exists."""
        state = {"status": "checkpoint_1"}
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = state

        config = {"configurable": {"thread_id": "session-123"}}
        result = saver.get_tuple(config)

        assert result is not None
        # CheckpointTuple is a Pydantic model - use model_dump() or access attributes
        assert hasattr(result, "checkpoint")
        assert hasattr(result, "metadata")
        assert hasattr(result, "config")
        mock_checkpointer.get.assert_called_once_with("session-123")

    def test_get_tuple_logic_empty_history(self):
        """Test get_tuple() returns None when state is empty."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = None

        config = {"configurable": {"thread_id": "empty"}}
        result = saver.get_tuple(config)

        assert result is None
        mock_checkpointer.get.assert_called_once_with("empty")

    def test_put_logic_with_thread_id(self):
        """Test put() saves checkpoint and returns config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"configurable": {"thread_id": "session-123"}}
        # Checkpoint and CheckpointMetadata are TypedDicts - pass as dicts
        checkpoint = {"v": 1, "id": "cp-1", "ts": "2024-01-01", "data": {"status": "saved"}}
        metadata = {"source": "input", "step": 1, "writes": {}}

        result = saver.put(config, checkpoint, metadata, {})

        assert result == config
        mock_checkpointer.put.assert_called_once()
        call_kwargs = mock_checkpointer.put.call_args.kwargs
        assert call_kwargs["thread_id"] == "session-123"
        assert call_kwargs["state"] == {"status": "saved"}
        assert call_kwargs["metadata"]["source"] == "input"

    def test_put_logic_without_thread_id(self):
        """Test put() returns config early when no thread_id."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"other": "value"}
        checkpoint = {"v": 1, "id": "cp-1", "data": {}}
        metadata = {"source": None, "step": -1, "writes": {}}

        result = saver.put(config, checkpoint, metadata, {})

        assert result == config
        mock_checkpointer.put.assert_not_called()

    def test_delete_thread_logic(self):
        """Test delete_thread() calls checkpointer.delete()."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        saver.delete_thread("session-123")

        mock_checkpointer.delete.assert_called_once_with("session-123")

    def test_list_logic_with_thread_id(self):
        """Test list() returns list of CheckpointTuple objects."""
        history = [{"status": "checkpoint_1"}, {"status": "checkpoint_2"}]
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get_history.return_value = history

        config = {"configurable": {"thread_id": "session-123"}}
        results = saver.list(config)

        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            # CheckpointTuple is a Pydantic model - use hasattr
            assert hasattr(result, "checkpoint")
            assert hasattr(result, "metadata")
            assert hasattr(result, "config")

    def test_list_logic_with_limit(self):
        """Test list() respects limit parameter."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get_history.return_value = []

        config = {"configurable": {"thread_id": "session-123"}}
        saver.list(config, limit=5)

        mock_checkpointer.get_history.assert_called_once_with("session-123", limit=5)

    def test_list_logic_without_thread_id(self):
        """Test list() returns empty list when no thread_id."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        results = saver.list({})

        assert results == []

    def test_async_methods_delegate_to_sync(self):
        """Test async methods delegate to sync counterparts."""
        import asyncio

        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        # Test aget_tuple delegates to get (they should return same type)
        config = {"configurable": {"thread_id": "session-123"}}
        mock_checkpointer.get.return_value = {"status": "test"}

        sync_result = saver.get(config)
        async_result = asyncio.run(saver.aget(config))

        # Both should return dict (not None)
        assert sync_result is not None
        assert async_result is not None

        # Test aput delegates to put - Checkpoint is TypedDict, pass as dict
        checkpoint = {"v": 1, "id": "cp-1", "ts": "", "data": {}}
        metadata = {"source": None, "step": -1, "writes": {}}
        sync_put_result = saver.put(config, checkpoint, metadata, {})
        async_put_result = asyncio.run(saver.aput(config, checkpoint, metadata, {}))

        # Both should return config
        assert sync_put_result == config
        assert async_put_result == config

        # Test adelete_thread delegates to delete_thread
        asyncio.run(saver.adelete_thread("session-123"))
        mock_checkpointer.delete.assert_called_with("session-123")

    def test_writes_methods_are_noop(self):
        """Test put_writes and aput_writes are no-ops."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        # These should not raise
        saver.put_writes(
            config={"configurable": {"thread_id": "123"}},
            writes=[("key", "value")],
            task_id="task-1",
            task_path="path/to/task",
        )

        saver.aput_writes(
            config={"configurable": {"thread_id": "123"}},
            writes=[("key", "value")],
            task_id="task-1",
            task_path="path/to/task",
        )

        # No checkpointer methods should be called
        mock_checkpointer.put.assert_not_called()
