"""Unit tests for omni.mcp.types."""

from omni.mcp.types import (
    ErrorCode,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPErrorCode,
    make_error_response,
    make_mcp_error_response,
    make_success_response,
)


class TestJSONRPCRequest:
    """Tests for JSONRPCRequest Pydantic model."""

    def test_request_with_id(self):
        """Test request that expects a response."""
        request = JSONRPCRequest(
            method="tools/list",
            params={"foo": "bar"},
            id=1,
        )
        assert request.jsonrpc == "2.0"
        assert request.method == "tools/list"
        assert request.params == {"foo": "bar"}
        assert request.id == 1
        assert request.is_notification is False
        assert request.message_type.value == "request"

    def test_notification_without_id(self):
        """Test notification that doesn't expect a response."""
        notification = JSONRPCRequest(
            method="notifications/tools/listChanged",
            params=None,
        )
        assert notification.id is None
        assert notification.is_notification is True
        assert notification.message_type.value == "notification"

    def test_request_with_string_id(self):
        """Test request with string ID."""
        request = JSONRPCRequest(method="test", id="abc-123")
        assert request.id == "abc-123"
        assert request.is_notification is False


class TestJSONRPCResponse:
    """Tests for JSONRPCResponse Pydantic model."""

    def test_success_response(self):
        """Test successful response."""
        response = JSONRPCResponse(id=1, result={"tools": []})
        assert response.jsonrpc == "2.0"
        assert response.id == 1
        assert response.result == {"tools": []}
        assert response.is_error is False

    def test_error_response(self):
        """Test error response."""
        error_response = JSONRPCResponse(
            id=1,
            error={"code": -32601, "message": "Method not found"},
        )
        assert error_response.is_error is True
        assert error_response.error["code"] == -32601


class TestJSONRPCError:
    """Tests for JSONRPCError Pydantic model."""

    def test_error_to_dict(self):
        """Test error serialization to dict."""
        error = JSONRPCError(code=-32601, message="Method not found", data={"hint": "check name"})
        result = error.to_dict()
        assert result == {
            "code": -32601,
            "message": "Method not found",
            "data": {"hint": "check name"},
        }

    def test_error_parse(self):
        """Test error parsing from dict."""
        error_dict = {"code": -32001, "message": "Tool not found", "data": {"tool": "test"}}
        error = JSONRPCError.parse(error_dict)
        assert error.code == -32001
        assert error.message == "Tool not found"
        assert error.data == {"tool": "test"}


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_make_success_response(self):
        """Test success response factory."""
        response = make_success_response(id=1, result={"count": 5})
        assert response.id == 1
        assert response.result == {"count": 5}
        assert response.is_error is False

    def test_make_error_response(self):
        """Test error response factory."""
        response = make_error_response(id=1, code=-32601, message="Method not found")
        assert response.id == 1
        assert response.error["code"] == -32601
        assert response.error["message"] == "Method not found"

    def test_make_error_response_with_data(self):
        """Test error response with extra data."""
        response = make_error_response(
            id=1,
            code=-32601,
            message="Invalid params",
            data={"param": "name"},
        )
        assert response.error["data"] == {"param": "name"}

    def test_make_mcp_error_response(self):
        """Test MCP-specific error response factory."""
        response = make_mcp_error_response(
            id=1,
            code=MCPErrorCode.TOOL_NOT_FOUND,
            message="Tool 'test' not found",
            data={"tool": "test"},
        )
        assert response.error["code"] == -32001
        assert response.error["message"] == "Tool 'test' not found"


class TestErrorCodes:
    """Tests for error code constants."""

    def test_standard_error_codes(self):
        """Test standard JSON-RPC error codes."""
        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.INVALID_REQUEST == -32600
        assert ErrorCode.METHOD_NOT_FOUND == -32601
        assert ErrorCode.INVALID_PARAMS == -32602
        assert ErrorCode.INTERNAL_ERROR == -32603
        assert ErrorCode.SERVER_ERROR == -32000

    def test_mcp_tool_error_codes(self):
        """Test MCP tool-related error codes."""
        assert MCPErrorCode.TOOL_NOT_FOUND == -32001
        assert MCPErrorCode.TOOL_EXECUTION_ERROR == -32002
        assert MCPErrorCode.TOOL_PARAM_INVALID == -32003

    def test_mcp_resource_error_codes(self):
        """Test MCP resource-related error codes."""
        assert MCPErrorCode.RESOURCE_NOT_FOUND == -32100
        assert MCPErrorCode.RESOURCE_INVALID == -32101
        assert MCPErrorCode.RESOURCE_READ_ERROR == -32102

    def test_mcp_prompt_error_codes(self):
        """Test MCP prompt-related error codes."""
        assert MCPErrorCode.PROMPT_NOT_FOUND == -32200
        assert MCPErrorCode.PROMPT_INVALID == -32201

    def test_mcp_session_error_codes(self):
        """Test MCP session-related error codes."""
        assert MCPErrorCode.SESSION_NOT_INITIALIZED == -32300
        assert MCPErrorCode.SESSION_LIMIT_EXCEEDED == -32301
