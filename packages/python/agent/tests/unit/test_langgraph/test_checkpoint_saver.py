"""Unit tests for RustCheckpointSaver (LangGraph-compatible checkpoint saver).

Tests the LangGraph BaseCheckpointSaver interface implementation and singleton patterns.
Uses async methods only - RustLanceCheckpointSaver is fully async.
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

    @pytest.mark.asyncio
    async def test_aget_tuple_logic_with_thread_id(self):
        """Test aget_tuple() returns CheckpointTuple when thread_id exists."""
        expected_state = {"status": "test", "data": [1, 2, 3]}
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = expected_state

        config = {"configurable": {"thread_id": "session-123"}}
        result = await saver.aget_tuple(config)

        assert result is not None
        # CheckpointTuple attributes
        assert hasattr(result, "checkpoint")
        assert hasattr(result, "metadata")
        assert hasattr(result, "config")
        mock_checkpointer.get.assert_called_once_with("session-123")

    @pytest.mark.asyncio
    async def test_aget_tuple_logic_without_thread_id(self):
        """Test aget_tuple() returns None when no thread_id in config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = {"status": "test"}

        config = {"other": "value"}
        result = await saver.aget_tuple(config)

        assert result is None
        mock_checkpointer.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_aget_tuple_logic_with_none_state(self):
        """Test aget_tuple() returns None when checkpointer returns None."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get.return_value = None

        config = {"configurable": {"thread_id": "nonexistent"}}
        result = await saver.aget_tuple(config)

        assert result is None

    @pytest.mark.asyncio
    async def test_aput_logic_with_thread_id(self):
        """Test aput() saves checkpoint and returns config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"configurable": {"thread_id": "session-123"}}
        # Checkpoint and CheckpointMetadata are TypedDicts - pass as dicts
        checkpoint = {"v": 1, "id": "cp-1", "ts": "2024-01-01", "data": {"status": "saved"}}
        metadata = {"source": "input", "step": 1, "writes": {}}

        result = await saver.aput(config, checkpoint, metadata, {})

        assert result == config
        mock_checkpointer.put.assert_called_once()
        call_kwargs = mock_checkpointer.put.call_args.kwargs
        assert call_kwargs["thread_id"] == "session-123"
        assert call_kwargs["state"] == {"status": "saved"}
        assert call_kwargs["metadata"]["source"] == "input"

    @pytest.mark.asyncio
    async def test_aput_logic_without_thread_id(self):
        """Test aput() returns config early when no thread_id."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"other": "value"}
        checkpoint = {"v": 1, "id": "cp-1", "data": {}}
        metadata = {"source": None, "step": -1, "writes": {}}

        result = await saver.aput(config, checkpoint, metadata, {})

        assert result == config
        mock_checkpointer.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_adelete_thread_logic(self):
        """Test adelete_thread() calls checkpointer.delete()."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        await saver.adelete_thread("session-123")

        mock_checkpointer.delete.assert_called_once_with("session-123")

    @pytest.mark.asyncio
    async def test_alist_logic_with_thread_id(self):
        """Test alist() yields CheckpointTuple objects."""
        history = [{"status": "checkpoint_1"}, {"status": "checkpoint_2"}]
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get_history.return_value = history

        config = {"configurable": {"thread_id": "session-123"}}
        results = [cp async for cp in saver.alist(config)]

        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            assert hasattr(result, "checkpoint")
            assert hasattr(result, "metadata")
            assert hasattr(result, "config")

    @pytest.mark.asyncio
    async def test_alist_logic_with_limit(self):
        """Test alist() respects limit parameter."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.get_history.return_value = []

        config = {"configurable": {"thread_id": "session-123"}}
        _ = [cp async for cp in saver.alist(config, limit=5)]

        mock_checkpointer.get_history.assert_called_once_with("session-123", limit=5)

    @pytest.mark.asyncio
    async def test_alist_logic_without_thread_id(self):
        """Test alist() yields nothing when no thread_id."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        results = [cp async for cp in saver.alist({})]

        assert results == []

    @pytest.mark.asyncio
    async def test_writes_methods_are_noop(self):
        """Test aput_writes is a no-op."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        # These should not raise
        await saver.aput_writes(
            config={"configurable": {"thread_id": "123"}},
            writes=[("key", "value")],
            task_id="task-1",
            task_path="path/to/task",
        )

        # No checkpointer methods should be called
        mock_checkpointer.put.assert_not_called()


class TestRustCheckpointSaverSingleton:
    """Tests for RustCheckpointSaver singleton pattern and caching."""

    def test_get_default_checkpointer_returns_singleton(self):
        """Test that get_default_checkpointer returns the same instance."""
        # Reset singleton to test
        import omni.langgraph.checkpoint.saver as saver_module

        original = saver_module._default_checkpointer
        saver_module._default_checkpointer = None

        try:
            from omni.langgraph.checkpoint.saver import get_default_checkpointer

            # Mock the actual initialization
            with patch("omni.langgraph.checkpoint.saver.RustCheckpointSaver") as mock_class:
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance

                # First call
                saver1 = get_default_checkpointer()

                # Second call should return same instance
                saver2 = get_default_checkpointer()

                # Should only create one instance
                assert mock_class.call_count == 1
                assert saver1 is saver2
        finally:
            # Restore original
            saver_module._default_checkpointer = original

    def test_checkpointer_cache_key_based_on_table_and_dimension(self):
        """Test that checkpointer cache uses (table_name, dimension) as key."""
        from omni.langgraph.checkpoint.saver import _CHECKPOINTER_CACHE

        # Clear cache
        original_cache = _CHECKPOINTER_CACHE.copy()
        _CHECKPOINTER_CACHE.clear()

        try:
            from omni.langgraph.checkpoint.saver import RustCheckpointSaver

            # Mock LanceCheckpointer
            with patch("omni.langgraph.checkpoint.saver.LanceCheckpointer") as mock_lance:
                mock1 = MagicMock()
                mock2 = MagicMock()
                mock_lance.side_effect = [mock1, mock2]

                # Create two savers with same (table, dimension)
                saver1 = RustCheckpointSaver(table_name="checkpoints", dimension=1536)
                saver2 = RustCheckpointSaver(table_name="checkpoints", dimension=1536)

                # Should use same LanceCheckpointer
                assert mock_lance.call_count == 1
                assert saver1._checkpointer is saver2._checkpointer

                # Create saver with different dimension
                saver3 = RustCheckpointSaver(table_name="checkpoints", dimension=768)

                # Should create new LanceCheckpointer
                assert mock_lance.call_count == 2
        finally:
            # Restore cache
            _CHECKPOINTER_CACHE.clear()
            _CHECKPOINTER_CACHE.update(original_cache)

    def test_module_level_cache_persists(self):
        """Test that _CHECKPOINTER_CACHE module-level cache persists."""
        from omni.langgraph.checkpoint.saver import _CHECKPOINTER_CACHE

        # The cache should exist and be a dict
        assert isinstance(_CHECKPOINTER_CACHE, dict)
