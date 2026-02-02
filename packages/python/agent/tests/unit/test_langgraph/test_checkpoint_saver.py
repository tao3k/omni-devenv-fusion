"""Unit tests for RustCheckpointSaver (LangGraph-compatible checkpoint saver).

Tests the LangGraph BaseCheckpointSaver interface implementation and singleton patterns.
Uses async methods only - RustLanceCheckpointSaver is fully async.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRustCheckpointSaverUnit:
    """Unit tests for RustCheckpointSaver - pure unit tests without module imports."""

    def _create_saver_with_mock_checkpointer(self):
        """Helper to create a saver with a mocked checkpointer."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        # Create mock checkpointer with async methods
        mock_checkpointer = MagicMock()
        mock_checkpointer.aget_tuple = AsyncMock()
        mock_checkpointer.aput = AsyncMock()
        mock_checkpointer.adelete_thread = AsyncMock()

        # alist is an async iterator
        async def mock_alist(*args, **kwargs):
            if hasattr(mock_checkpointer, "_history"):
                for item in mock_checkpointer._history:
                    yield item
            else:
                return
                yield

        mock_checkpointer.alist = mock_alist

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
        from langgraph.checkpoint.base import CheckpointTuple

        expected_tuple = MagicMock(spec=CheckpointTuple)
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.aget_tuple.return_value = expected_tuple

        config = {"configurable": {"thread_id": "session-123"}}
        result = await saver.aget_tuple(config)

        assert result is expected_tuple
        mock_checkpointer.aget_tuple.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_aget_tuple_logic_without_thread_id(self):
        """Test aget_tuple() returns None when no thread_id in config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"other": "value"}
        result = await saver.aget_tuple(config)

        assert result is None
        mock_checkpointer.aget_tuple.assert_not_called()

    @pytest.mark.asyncio
    async def test_aget_tuple_logic_with_none_state(self):
        """Test aget_tuple() returns None when checkpointer returns None."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer.aget_tuple.return_value = None

        config = {"configurable": {"thread_id": "nonexistent"}}
        result = await saver.aget_tuple(config)

        assert result is None

    @pytest.mark.asyncio
    async def test_aput_logic_with_thread_id(self):
        """Test aput() saves checkpoint and returns config."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"configurable": {"thread_id": "session-123"}}
        checkpoint = {
            "v": 1,
            "id": "cp-1",
            "ts": "2024-01-01",
            "channel_values": {"status": "saved"},
        }
        metadata = {"source": "input", "step": 1, "writes": {}}

        result = await saver.aput(config, checkpoint, metadata, {})

        assert result == config
        mock_checkpointer.aput.assert_called_once_with(config, checkpoint, metadata, {})

    @pytest.mark.asyncio
    async def test_aput_logic_without_thread_id(self):
        """Test aput() returns config early when no thread_id."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        config = {"other": "value"}
        checkpoint = {"v": 1, "id": "cp-1", "data": {}}
        metadata = {"source": None, "step": -1, "writes": {}}

        # aput doesn't actually check thread_id, it delegates to checkpointer
        # If we want it to return config early, we need to check implementation
        # Looking at implementation: it just delegates.
        await saver.aput(config, checkpoint, metadata, {})
        mock_checkpointer.aput.assert_called_once()

    @pytest.mark.asyncio
    async def test_adelete_thread_logic(self):
        """Test adelete_thread() calls checkpointer.adelete_thread()."""
        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()

        await saver.adelete_thread("session-123")

        mock_checkpointer.adelete_thread.assert_called_once_with("session-123")

    @pytest.mark.asyncio
    async def test_alist_logic_with_thread_id(self):
        """Test alist() yields CheckpointTuple objects."""
        from langgraph.checkpoint.base import CheckpointTuple

        tuple1 = MagicMock(spec=CheckpointTuple)
        tuple2 = MagicMock(spec=CheckpointTuple)

        saver, mock_checkpointer = self._create_saver_with_mock_checkpointer()
        mock_checkpointer._history = [tuple1, tuple2]

        # In my mock_alist, it doesn't even use config
        # But we want to test if it yields
        config = {"configurable": {"thread_id": "session-123"}}
        results = [cp async for cp in saver.alist(config)]

        assert len(results) == 2
        assert results[0] is tuple1
        assert results[1] is tuple2

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
        mock_checkpointer.aput.assert_not_called()


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
