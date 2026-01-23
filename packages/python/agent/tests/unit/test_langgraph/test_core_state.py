"""
test_core_state.py - Tests for State & Checkpoint System

Tests for:
- GraphState TypedDict
- StateCheckpointer persistence
- State utilities
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from omni.langgraph.state import (
    GraphState,
    StateCheckpoint,
    CheckpointMetadata,
    StateCheckpointer,
    get_checkpointer,
    create_initial_state,
    merge_state,
)


class TestGraphState:
    """Tests for GraphState TypedDict."""

    def test_create_graph_state(self):
        """Should create a valid GraphState."""
        state = GraphState(
            messages=[{"role": "user", "content": "Hello"}],
            context_ids=["ctx-1"],
            current_plan="Test plan",
            error_count=0,
            workflow_state={"key": "value"},
        )

        assert len(state["messages"]) == 1
        assert state["messages"][0]["content"] == "Hello"
        assert state["context_ids"] == ["ctx-1"]
        assert state["current_plan"] == "Test plan"
        assert state["error_count"] == 0
        assert state["workflow_state"]["key"] == "value"

    def test_graph_state_empty(self):
        """Should create empty GraphState."""
        state = GraphState(
            messages=[],
            context_ids=[],
            current_plan="",
            error_count=0,
            workflow_state={},
        )

        assert state["messages"] == []
        assert state["context_ids"] == []
        assert state["current_plan"] == ""
        assert state["error_count"] == 0
        assert state["workflow_state"] == {}


class TestStateCheckpoint:
    """Tests for StateCheckpoint model."""

    def test_create_checkpoint(self):
        """Should create a valid checkpoint."""
        checkpoint = StateCheckpoint(
            thread_id="test-thread",
            state={"messages": []},
        )

        assert checkpoint.thread_id == "test-thread"
        assert checkpoint.state == {"messages": []}
        assert checkpoint.checkpoint_id is not None
        assert checkpoint.timestamp is not None

    def test_checkpoint_serialization(self):
        """Should serialize and deserialize correctly."""
        checkpoint = StateCheckpoint(
            thread_id="test-thread",
            state={"key": "value"},
            metadata={"meta": True},
        )

        json_str = checkpoint.to_json()
        restored = StateCheckpoint.from_json(json_str)

        assert restored.thread_id == checkpoint.thread_id
        assert restored.state == checkpoint.state
        assert restored.metadata == checkpoint.metadata


class TestStateCheckpointer:
    """Tests for StateCheckpointer."""

    @pytest.fixture
    def temp_checkpointer(self):
        """Create a checkpointer with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_checkpoints.db"
            checkpointer = StateCheckpointer(db_path=db_path)
            yield checkpointer

    def test_put_and_get(self, temp_checkpointer):
        """Should save and retrieve state."""
        state = create_initial_state(
            messages=[{"role": "user", "content": "Test"}],
        )

        checkpoint_id = temp_checkpointer.put("thread-1", state)
        assert checkpoint_id is not None

        retrieved = temp_checkpointer.get("thread-1")
        assert retrieved is not None
        assert len(retrieved["messages"]) == 1
        assert retrieved["messages"][0]["content"] == "Test"

    def test_get_nonexistent(self, temp_checkpointer):
        """Should return None for nonexistent thread."""
        result = temp_checkpointer.get("nonexistent")
        assert result is None

    def test_delete_thread(self, temp_checkpointer):
        """Should delete all checkpoints for a thread."""
        state = create_initial_state()
        temp_checkpointer.put("thread-1", state)
        temp_checkpointer.put("thread-1", state)

        deleted = temp_checkpointer.delete_thread("thread-1")
        assert deleted == 2

        # Verify deletion
        assert temp_checkpointer.get("thread-1") is None

    def test_get_thread_ids(self, temp_checkpointer):
        """Should return all thread IDs."""
        state = create_initial_state()
        temp_checkpointer.put("thread-a", state)
        temp_checkpointer.put("thread-b", state)

        thread_ids = temp_checkpointer.get_thread_ids()
        assert "thread-a" in thread_ids
        assert "thread-b" in thread_ids

    def test_clear_all(self, temp_checkpointer):
        """Should clear all checkpoints."""
        state = create_initial_state()
        temp_checkpointer.put("thread-1", state)
        temp_checkpointer.put("thread-2", state)

        count = temp_checkpointer.clear()
        assert count == 2

        assert temp_checkpointer.get_thread_ids() == []


class TestStateUtilities:
    """Tests for state utility functions."""

    def test_create_initial_state(self):
        """Should create initial state with defaults."""
        state = create_initial_state()

        assert state["messages"] == []
        assert state["context_ids"] == []
        assert state["current_plan"] == ""
        assert state["error_count"] == 0
        assert state["workflow_state"] == {}

    def test_create_initial_state_with_messages(self):
        """Should create state with initial messages."""
        messages = [{"role": "user", "content": "Hello"}]
        state = create_initial_state(messages=messages)

        assert len(state["messages"]) == 1
        assert state["messages"][0]["content"] == "Hello"

    def test_merge_state(self):
        """Should merge updates into state."""
        existing = create_initial_state(
            messages=[{"role": "user", "content": "First"}],
        )

        updates = {
            "messages": [{"role": "assistant", "content": "Response"}],
            "current_plan": "New plan",
        }

        merged = merge_state(existing, updates)

        # Messages should be appended
        assert len(merged["messages"]) == 2
        assert merged["messages"][0]["content"] == "First"
        assert merged["messages"][1]["content"] == "Response"

        # Other fields should be updated
        assert merged["current_plan"] == "New plan"


class TestGetCheckpointer:
    """Tests for get_checkpointer singleton."""

    def test_get_checkpointer_returns_checkpointer(self):
        """Should return a StateCheckpointer instance."""
        checkpointer = get_checkpointer()
        assert isinstance(checkpointer, StateCheckpointer)

    def test_get_checkpointer_singleton(self):
        """Should return same instance on multiple calls."""
        cp1 = get_checkpointer()
        cp2 = get_checkpointer()
        assert cp1 is cp2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
