"""
test_responses.py - Unit tests for unified response format

Tests for ToolResponse class and ResponseStatus enum.
"""

from datetime import UTC, datetime

import pytest

from omni.core.responses import ResponseStatus, ToolResponse


class TestResponseStatus:
    """Tests for ResponseStatus enum."""

    def test_status_values(self):
        """Test that status enum values are correct."""
        assert ResponseStatus.SUCCESS == "success"
        assert ResponseStatus.ERROR == "error"
        assert ResponseStatus.BLOCKED == "blocked"
        assert ResponseStatus.PARTIAL == "partial"

    def test_status_is_string_enum(self):
        """Test that ResponseStatus inherits from str."""
        assert isinstance(ResponseStatus.SUCCESS, str)


class TestToolResponse:
    """Tests for ToolResponse class."""

    def test_success_response(self):
        """Test creating a success response."""
        resp = ToolResponse.success(data={"key": "value"})
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.data == {"key": "value"}
        assert resp.error_message is None
        assert resp.error_code is None
        assert resp.is_success is True
        assert resp.is_error is False
        assert resp.is_blocked is False

    def test_success_response_with_metadata(self):
        """Test creating a success response with metadata."""
        metadata = {"tool": "git.commit", "version": "1.0"}
        resp = ToolResponse.success(data="result", metadata=metadata)
        assert resp.metadata == metadata

    def test_error_response(self):
        """Test creating an error response."""
        resp = ToolResponse.error(
            message="Not found",
            code=CoreErrorCode.TOOL_NOT_FOUND,
        )
        assert resp.status == ResponseStatus.ERROR
        assert resp.error_message == "Not found"
        assert resp.error_code == "3001"
        assert resp.is_error is True
        assert resp.is_success is False

    def test_error_response_with_metadata(self):
        """Test creating an error response with metadata."""
        metadata = {"tool": "git.commit", "attempts": 3}
        resp = ToolResponse.error(
            message="Tool failed",
            code=CoreErrorCode.TOOL_EXECUTION_FAILED,
            metadata=metadata,
        )
        assert resp.metadata == metadata

    def test_blocked_response(self):
        """Test creating a blocked response."""
        resp = ToolResponse.blocked(reason="Security check failed")
        assert resp.status == ResponseStatus.BLOCKED
        assert resp.error_message == "Security check failed"
        assert resp.error_code == "BLOCKED"
        assert resp.is_blocked is True
        assert resp.is_error is False

    def test_blocked_response_with_metadata(self):
        """Test creating a blocked response with metadata."""
        metadata = {"check_type": "mutation_safety"}
        resp = ToolResponse.blocked(reason="Dangerous command", metadata=metadata)
        assert resp.metadata == metadata

    def test_partial_response(self):
        """Test creating a partial response."""
        resp = ToolResponse.partial(
            data={"partial": "data"},
            message="Only partial results available",
        )
        assert resp.status == ResponseStatus.PARTIAL
        assert resp.data == {"partial": "data"}
        assert resp.error_message == "Only partial results available"

    def test_to_mcp_format(self):
        """Test converting response to MCP format."""
        resp = ToolResponse.success(data={"key": "value"})
        mcp = resp.to_mcp()
        assert isinstance(mcp, list)
        assert len(mcp) == 1
        assert mcp[0]["type"] == "text"
        # Verify JSON content
        import json

        content = json.loads(mcp[0]["text"])
        assert content["status"] == "success"
        assert content["data"] == {"key": "value"}

    def test_to_mcp_format_error(self):
        """Test converting error response to MCP format."""
        resp = ToolResponse.error(
            message="Not found",
            code=CoreErrorCode.TOOL_NOT_FOUND,
        )
        mcp = resp.to_mcp()
        import json

        content = json.loads(mcp[0]["text"])
        assert content["status"] == "error"
        assert content["error_message"] == "Not found"
        assert content["error_code"] == "3001"

    def test_error_message_field(self):
        """Test that error_message field is set correctly in error responses."""
        resp = ToolResponse.error(message="Test error")
        assert resp.error_message == "Test error"
        assert resp.data is None

    def test_timestamp_is_set(self):
        """Test that timestamp is automatically set."""
        before = datetime.now(UTC)
        resp = ToolResponse.success()
        after = datetime.now(UTC)
        assert before <= resp.timestamp <= after

    def test_timestamp_in_mcp_output(self):
        """Test that timestamp is included in MCP output."""
        resp = ToolResponse.success()
        mcp = resp.to_mcp()
        import json

        content = json.loads(mcp[0]["text"])
        assert "timestamp" in content

    def test_empty_metadata(self):
        """Test that metadata defaults to empty dict."""
        resp = ToolResponse.success()
        assert resp.metadata == {}

    def test_none_data(self):
        """Test that data can be None."""
        resp = ToolResponse.error(message="Failed")
        assert resp.data is None


class TestToolResponseModelBehavior:
    """Tests for Pydantic model behavior."""

    def test_model_dump(self):
        """Test that model_dump includes all fields."""
        resp = ToolResponse.success(data="test", metadata={"key": "value"})
        dump = resp.model_dump()
        assert dump["status"] == "success"
        assert dump["data"] == "test"
        assert dump["metadata"] == {"key": "value"}
        assert dump["error_message"] is None
        assert dump["error_code"] is None
        assert "timestamp" in dump

    def test_model_json(self):
        """Test that model_dump_json produces valid JSON."""
        resp = ToolResponse.success(data={"key": "value"})
        json_str = resp.model_dump_json()
        import json

        data = json.loads(json_str)
        assert data["status"] == "success"
        assert data["data"] == {"key": "value"}


# Need to import CoreErrorCode for tests
from omni.core.errors import CoreErrorCode
