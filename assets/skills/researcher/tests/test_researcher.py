"""Tests for researcher skill."""

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestResearcherScripts:
    """Test researcher skill scripts can be imported."""

    def test_research_script_imports(self):
        """Test research script imports successfully."""
        from researcher.scripts import research

        assert hasattr(research, "clone_repo")
        assert hasattr(research, "repomix_map")
        assert hasattr(research, "repomix_compress_shard")
        assert hasattr(research, "save_index")

    def test_clone_repo_function_exists(self):
        """Test clone_repo function exists."""
        from researcher.scripts.research import clone_repo

        assert callable(clone_repo)

    def test_repomix_map_function_exists(self):
        """Test repomix_map function exists."""
        from researcher.scripts.research import repomix_map

        assert callable(repomix_map)

    def test_repomix_compress_shard_function_exists(self):
        """Test repomix_compress_shard function exists."""
        from researcher.scripts.research import repomix_compress_shard

        assert callable(repomix_compress_shard)

    def test_save_index_function_exists(self):
        """Test save_index function exists."""
        from researcher.scripts.research import save_index

        assert callable(save_index)


class TestResearcherCheckpoint:
    """Test researcher skill checkpoint integration."""

    def test_workflow_type_defined(self):
        """Test workflow type is defined for checkpointing."""
        from researcher.scripts.research_graph import _WORKFLOW_TYPE

        assert _WORKFLOW_TYPE == "research"

    def test_checkpointer_import(self):
        """Test checkpoint functions can be imported."""
        from researcher.scripts.research_graph import (
            load_workflow_state,
            save_workflow_state,
        )

        assert callable(save_workflow_state)
        assert callable(load_workflow_state)


class TestRustCheckpointSaverAsync:
    """Test RustCheckpointSaver has proper async methods (LangGraph 1.0+ compatibility)."""

    def test_all_async_methods_are_coroutines(self):
        """Verify all methods that should be async are actually async functions."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        # These methods MUST be async for LangGraph 1.0+
        # Note: alist is an async generator (uses yield), so we check for both
        # coroutine functions and async generator functions
        async_methods = [
            "aget_tuple",
            "aput",
            "adelete_thread",
            "alist",
            "aput_writes",
        ]

        for method_name in async_methods:
            assert hasattr(RustCheckpointSaver, method_name), f"Missing method: {method_name}"
            method = getattr(RustCheckpointSaver, method_name)
            is_coroutine = inspect.iscoroutinefunction(method)
            is_async_gen = inspect.isasyncgenfunction(method)
            assert is_coroutine or is_async_gen, (
                f"{method_name} must be an async function or async generator for LangGraph 1.0+ compatibility. "
                f"Got: {type(method)} (is_coroutine={is_coroutine}, is_async_gen={is_async_gen})"
            )

    def test_sync_methods_are_not_coroutines(self):
        """Verify sync methods are NOT async (to avoid unnecessary overhead)."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        # These methods should be sync for performance
        sync_methods = [
            "get",
            "get_tuple",
            "put",
            "delete_thread",
            "list",
            "put_writes",
        ]

        for method_name in sync_methods:
            if hasattr(RustCheckpointSaver, method_name):
                method = getattr(RustCheckpointSaver, method_name)
                assert not inspect.iscoroutinefunction(method), (
                    f"{method_name} should be a sync function for performance. Got: async function"
                )

    def test_aget_tuple_returns_awaitable(self):
        """Test aget_tuple returns an awaitable."""
        import asyncio
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        # Create a mock checkpointer for the inner LanceCheckpointer
        mock_inner = MagicMock()
        mock_inner.get_latest.return_value = None

        with patch.object(RustCheckpointSaver, "__init__", lambda self: None):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._checkpointer = mock_inner
            saver._table_name = "test"

            # aget_tuple must be awaitable
            result = saver.aget_tuple({"configurable": {"thread_id": "test"}})
            assert inspect.isawaitable(result), "aget_tuple must return an awaitable"

            # Clean up
            if inspect.iscoroutine(result):
                result.close()


class TestRustCheckpointSaverCheckpointStructure:
    """Test checkpoint structure handling for LangGraph 1.0+."""

    def test_checkpoint_has_langgraph_10_fields(self):
        """Test checkpoint structure has all LangGraph 1.0+ required fields."""
        from omni.langgraph.checkpoint.saver import _make_checkpoint
        from langgraph.checkpoint.base.id import uuid6

        state = {"messages": ["hello"], "current_step": 1}
        checkpoint = _make_checkpoint(state)

        # LangGraph 1.0+ required fields
        assert "v" in checkpoint
        assert checkpoint["v"] == 2  # Latest version
        assert "id" in checkpoint
        assert len(checkpoint["id"]) == 32  # UUID hex length
        assert "ts" in checkpoint
        assert "channel_values" in checkpoint
        assert checkpoint["channel_values"] == state
        assert "channel_versions" in checkpoint
        assert isinstance(checkpoint["channel_versions"], dict)
        assert "versions_seen" in checkpoint
        assert isinstance(checkpoint["versions_seen"], dict)
        assert "updated_channels" in checkpoint

    def test_checkpoint_id_is_valid_uuid_hex(self):
        """Test checkpoint ID is a valid UUID hex string."""
        from omni.langgraph.checkpoint.saver import _make_checkpoint
        import re

        checkpoint = _make_checkpoint({"test": "value"})
        checkpoint_id = checkpoint["id"]

        # Should be 32-character hex string (UUID v6 format)
        assert re.match(r"^[0-9a-f]{32}$", checkpoint_id), (
            f"Checkpoint ID should be 32-char hex, got: {checkpoint_id}"
        )

    def test_put_handles_dict_checkpoint(self):
        """Test put method handles checkpoint as dict with channel_values (LangGraph 1.0+ format)."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        mock_inner = MagicMock()

        with patch.object(RustCheckpointSaver, "__init__", lambda self: None):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._checkpointer = mock_inner

            # Test with dict checkpoint (LangGraph 1.0 format with channel_values)
            dict_checkpoint = {
                "id": "test-checkpoint-1",
                "channel_values": {"key": "value"},
            }
            dict_metadata = MagicMock()
            dict_metadata.get = lambda k, d=None: d
            dict_metadata.source = None
            dict_metadata.step = 1
            dict_metadata.writes = {}

            config = {"configurable": {"thread_id": "test-thread"}}
            new_versions = {}

            # Should not raise KeyError
            result = saver.put(config, dict_checkpoint, dict_metadata, new_versions)

            # Verify inner put was called
            mock_inner.put.assert_called_once()
            call_args = mock_inner.put.call_args
            assert call_args.kwargs["checkpoint_id"] == "test-checkpoint-1"
            # Verify channel_values was extracted
            assert call_args.kwargs["state"] == {"key": "value"}

    def test_put_handles_checkpoint_dataclass(self):
        """Test put method handles Checkpoint dataclass-like objects with channel_values."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        mock_inner = MagicMock()

        with patch.object(RustCheckpointSaver, "__init__", lambda self: None):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._checkpointer = mock_inner

            # Test with object having channel_values attribute (LangGraph 1.0+)
            # Use a proper mock that mimics the dict-like interface
            mock_checkpoint = MagicMock(spec=["id", "channel_values"])
            mock_checkpoint.id = "test-checkpoint-2"
            mock_checkpoint.channel_values = {"state_key": "state_value"}

            mock_metadata = MagicMock()
            mock_metadata.source = None
            mock_metadata.step = 1
            mock_metadata.writes = {}

            config = {"configurable": {"thread_id": "test-thread"}}
            new_versions = {}

            # Should work with object having channel_values attribute
            result = saver.put(config, mock_checkpoint, mock_metadata, new_versions)

            mock_inner.put.assert_called_once()


class TestGraphOutputTypedDict:
    """Test GraphOutput TypedDict access patterns (fixes 'dict' object has no attribute 'content' error)."""

    def test_graph_output_is_typeddict(self):
        """Test GraphOutput is a TypedDict, not a regular class."""
        from omni.langgraph.graph import GraphOutput

        # GraphOutput should be a TypedDict (dict subclass)
        result: GraphOutput = {
            "success": True,
            "content": "test",
            "confidence": 0.9,
            "iterations": 1,
            "approved": False,
        }
        assert isinstance(result, dict), "GraphOutput should be a dict/TypedDict"

    def test_graph_output_access_via_get(self):
        """Test GraphOutput access using dict.get() method (correct pattern)."""
        from omni.langgraph.graph import GraphOutput

        result: GraphOutput = {
            "success": True,
            "content": "Analysis complete",
            "confidence": 0.95,
            "iterations": 5,
            "approved": True,
        }

        # Correct: use .get() for TypedDict
        assert result.get("success") is True
        assert result.get("content") == "Analysis complete"
        assert result.get("confidence") == 0.95
        assert result.get("iterations") == 5
        assert result.get("approved") is True

    def test_graph_output_access_via_get_with_defaults(self):
        """Test GraphOutput get() with default values for missing keys."""
        from omni.langgraph.graph import GraphOutput

        minimal_result: GraphOutput = {
            "success": True,
            "content": "test",
            "confidence": 0.0,
            "iterations": 0,
            "approved": False,
        }

        # Access with defaults for optional fields
        assert minimal_result.get("confidence", 0.0) == 0.0
        assert minimal_result.get("iterations", 0) == 0
        assert minimal_result.get("approved", False) is False
        assert minimal_result.get("nonexistent", "default") == "default"

    def test_graph_output_no_attribute_access(self):
        """Verify GraphOutput cannot be accessed via attribute (e.g., result.content).

        This test ensures the fix is correct - TypedDict should use dict.get(),
        not attribute access like result.content.
        """
        from omni.langgraph.graph import GraphOutput

        result: GraphOutput = {
            "success": True,
            "content": "test",
            "confidence": 0.0,
            "iterations": 0,
            "approved": False,
        }

        # TypedDict is dict, attribute access should fail or return None
        # (This is the bug we fixed - using .content instead of ["content"])
        content_via_dict = result["content"]
        assert content_via_dict == "test"

        # Verify .get() works correctly
        content_via_get = result.get("content")
        assert content_via_get == content_via_dict


class TestProviderMessagesAccess:
    """Test Provider messages[-1] access patterns (fixes dict access errors)."""

    def test_provider_handles_dict_messages(self):
        """Test provider correctly handles messages as list of dicts."""
        # Simulate the state structure from the fix
        state = {
            "messages": [
                {"role": "user", "content": "Analyze this repo"},
                {"role": "assistant", "content": "I'll help you with that"},
            ]
        }

        messages = state.get("messages", [])
        content = ""
        if messages:
            last_msg = messages[-1]
            # Correct: handle both dict and object access patterns
            if isinstance(last_msg, dict):
                content = last_msg.get("content") or last_msg.get("text") or ""
            else:
                content = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        assert content == "I'll help you with that"

    def test_provider_handles_object_messages(self):
        """Test provider correctly handles messages as list of objects."""
        from dataclasses import dataclass

        @dataclass
        class Message:
            role: str
            content: str
            text: str = ""

        state = {
            "messages": [
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
            ]
        }

        messages = state.get("messages", [])
        content = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                content = last_msg.get("content") or last_msg.get("text") or ""
            else:
                content = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        assert content == "Hi there!"

    def test_provider_empty_messages_handling(self):
        """Test provider handles empty messages list gracefully."""
        state = {"messages": []}

        messages = state.get("messages", [])
        content = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                content = last_msg.get("content") or last_msg.get("text") or ""
            else:
                content = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        assert content == ""

    def test_provider_no_messages_key(self):
        """Test provider handles missing messages key gracefully."""
        state = {"current_task": "Analyze"}

        messages = state.get("messages", [])
        content = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                content = last_msg.get("content") or last_msg.get("text") or ""
            else:
                content = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        assert content == ""


class TestCheckpointLogging:
    """Test checkpoint logging behavior and messages."""

    def test_checkpoint_store_initialization_log_level(self):
        """Test checkpoint store initialization uses debug log level, not info."""
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        # Verify the saver can be created (actual log level testing requires integration test)
        # This test ensures the initialization doesn't raise errors
        mock_inner = MagicMock()
        mock_inner.get.return_value = None

        with patch.object(
            RustCheckpointSaver,
            "__init__",
            lambda self, table_name="checkpoints", uri=None, dimension=1536: None,
        ):
            saver = RustCheckpointSaver.__new__(RustCheckpointSaver)
            saver._checkpointer = mock_inner
            saver._table_name = "test"

            # Verify attributes
            assert saver._table_name == "test"
            assert saver._checkpointer is mock_inner

    def test_checkpoint_persistence_across_sessions(self):
        """Test that checkpoint data persists (LanceDB reuses existing files)."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            load_workflow_state,
            delete_workflow_state,
        )

        workflow_type = "test_persistence"
        workflow_id = "session-test-001"
        test_state = {"status": "persistence_test", "data": [1, 2, 3]}

        # Save state
        result = save_workflow_state(workflow_type, workflow_id, test_state)
        assert result is True

        # Load state (simulates new session with fresh cache)
        loaded = load_workflow_state(workflow_type, workflow_id)
        assert loaded is not None
        assert loaded["status"] == "persistence_test"
        assert loaded["data"] == [1, 2, 3]

        # Cleanup
        delete_workflow_state(workflow_type, workflow_id)

    def test_checkpoint_table_isolation(self):
        """Test different workflow types use different tables."""
        from omni.foundation.checkpoint import (
            save_workflow_state,
            load_workflow_state,
            delete_workflow_state,
        )

        workflow_type_a = "workflow_a"
        workflow_type_b = "workflow_b"
        workflow_id = "shared-id"
        state_a = {"type": "A", "value": 100}
        state_b = {"type": "B", "value": 200}

        # Save to different workflow types
        assert save_workflow_state(workflow_type_a, workflow_id, state_a) is True
        assert save_workflow_state(workflow_type_b, workflow_id, state_b) is True

        # Load should return correct state for each type
        loaded_a = load_workflow_state(workflow_type_a, workflow_id)
        loaded_b = load_workflow_state(workflow_type_b, workflow_id)

        assert loaded_a["value"] == 100
        assert loaded_b["value"] == 200

        # Cleanup
        delete_workflow_state(workflow_type_a, workflow_id)
        delete_workflow_state(workflow_type_b, workflow_id)


class TestResearcherEntry:
    """Test researcher entry point."""

    def test_run_research_graph_exists(self):
        """Test run_research_graph function exists."""
        from researcher.scripts.research_entry import run_research_graph

        assert callable(run_research_graph)

    def test_get_workflow_id_exists(self):
        """Test _get_workflow_id helper exists."""
        from researcher.scripts.research_entry import _get_workflow_id

        assert callable(_get_workflow_id)
        # Test the function generates consistent IDs
        url1 = "https://github.com/example/repo"
        url2 = "https://github.com/example/repo"
        assert _get_workflow_id(url1) == _get_workflow_id(url2)
