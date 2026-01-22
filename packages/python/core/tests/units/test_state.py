"""Tests for omni.core.skills.state module."""

from __future__ import annotations

import pytest
from omni.core.skills.state import GraphState, WorkflowState


class TestGraphState:
    """Test GraphState dataclass."""

    def test_default_initialization(self):
        """Test default values."""
        state = GraphState()
        assert state.project_root == "."
        assert state.workflow_id == ""
        assert state.staged_files == []
        assert state.status == "pending"
        assert state.error == ""
        assert state.approved is False

    def test_custom_initialization(self):
        """Test custom values."""
        state = GraphState(
            project_root="/test/repo",
            workflow_id="wf-123",
            staged_files=["file1.py", "file2.py"],
            status="prepared",
        )
        assert state.project_root == "/test/repo"
        assert state.workflow_id == "wf-123"
        assert len(state.staged_files) == 2
        assert state.status == "prepared"

    def test_dict_like_access(self):
        """Test dict-like interface."""
        state = GraphState(workflow_id="test-wf")
        assert state["workflow_id"] == "test-wf"
        assert state.get("status", "default") == "pending"
        assert state.get("nonexistent", "fallback") == "fallback"

    def test_dict_like_assignment(self):
        """Test dict-like assignment."""
        state = GraphState()
        state["status"] = "completed"
        assert state.status == "completed"

    def test_contains(self):
        """Test 'in' operator."""
        state = GraphState(workflow_id="test")
        assert "workflow_id" in state
        assert "nonexistent" not in state

    def test_iteration(self):
        """Test iteration over keys."""
        state = GraphState(workflow_id="test", status="pending")
        keys = list(state.keys())
        assert "workflow_id" in keys
        assert "status" in keys

    def test_to_dict(self):
        """Test conversion to dict."""
        state = GraphState(workflow_id="test", status="done")
        d = state.to_dict()
        assert isinstance(d, dict)
        assert d["workflow_id"] == "test"
        assert d["status"] == "done"


class TestWorkflowState:
    """Test WorkflowState dataclass."""

    def test_default_initialization(self):
        """Test default values."""
        state = WorkflowState()
        assert state.workflow_id == ""
        assert state.status == "pending"
        assert state.data == {}

    def test_custom_initialization(self):
        """Test custom values."""
        state = WorkflowState(
            workflow_id="wf-456",
            status="running",
            data={"key": "value"},
        )
        assert state.workflow_id == "wf-456"
        assert state.status == "running"
        assert state.data["key"] == "value"

    def test_get_set(self):
        """Test get/set methods."""
        state = WorkflowState()
        state.set("custom_key", "custom_value")
        assert state.get("custom_key") == "custom_value"
        assert state.get("missing", "default") == "default"
