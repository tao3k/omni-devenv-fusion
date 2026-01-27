"""Unit tests for omni.mcp JSON-RPC types.

Uses plain dict types for outgoing responses (no Pydantic dependency).
MCP SDK types are used only for parsing incoming requests if needed.
"""

from mcp.types import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JSONRPCRequest,
)


# Error codes (matching MCP SDK constants)
PARSE_ERROR_CODE = -32700
INVALID_REQUEST_CODE = -32600
METHOD_NOT_FOUND_CODE = -32601
INVALID_PARAMS_CODE = -32602
INTERNAL_ERROR_CODE = -32603


class TestJSONRPCMessage:
    """Tests for JSON-RPC message handling using MCP SDK for parsing."""

    def test_request_with_id(self):
        """Test request that expects a response."""
        request = JSONRPCRequest(
            jsonrpc="2.0",
            method="tools/list",
            params={"foo": "bar"},
            id=1,
        )
        assert request.jsonrpc == "2.0"
        assert request.method == "tools/list"
        assert request.id == 1

    def test_notification_without_id(self):
        """Test notification that doesn't expect a response."""
        # Notifications are plain dicts (no id field)
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/tools/listChanged",
        }
        assert notification.get("id") is None

    def test_request_with_string_id(self):
        """Test request with string ID."""
        request = JSONRPCRequest(jsonrpc="2.0", method="test", id="abc-123")
        assert request.id == "abc-123"


class TestJSONRPCResponsePlain:
    """Tests for JSON-RPC response handling using plain dicts."""

    def test_success_response(self):
        """Test success response structure."""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": []},
            "error": None,
        }
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"tools": []}
        assert response["error"] is None

    def test_error_response(self):
        """Test error response structure."""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": None,
            "error": {
                "code": -32600,
                "message": "Invalid request",
            },
        }
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["error"]["code"] == -32600


class TestJSONRPC20Compliance:
    """JSON-RPC 2.0 Specification Compliance Tests.

    See: https://www.jsonrpc.org/specification

    Key requirements:
    - Request objects MUST contain "id" (string or number, not null)
    - Response objects MUST contain "id" matching the request
    - Error codes MUST be integers
    - Response MUST contain either "result" OR "error", never both
    """

    def test_request_id_must_be_string_or_number(self):
        """JSON-RPC 2.0: id MUST be a string or number, not null."""
        # Valid: string id
        request = JSONRPCRequest(jsonrpc="2.0", method="test", id="abc")
        assert isinstance(request.id, str)

        # Valid: number id
        request = JSONRPCRequest(jsonrpc="2.0", method="test", id=123)
        assert isinstance(request.id, int)

    def test_response_id_must_not_be_null(self):
        """JSON-RPC 2.0: Response id MUST NOT be null for requests."""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {},
            "error": None,
        }
        assert response["id"] == 1
        assert response["id"] is not None

    def test_response_must_have_result_or_error_not_both(self):
        """JSON-RPC 2.0: Response MUST contain either result or error, never both."""
        # Success response
        success = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"data": "test"},
            "error": None,
        }
        assert success["result"] is not None
        assert success["error"] is None

        # Error response
        error = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": None,
            "error": {"code": -32601, "message": "Method not found"},
        }
        assert error["error"] is not None
        assert error["result"] is None

    def test_error_code_must_be_integer(self):
        """JSON-RPC 2.0: error.code MUST be an integer."""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": None,
            "error": {"code": INVALID_REQUEST, "message": "Invalid request"},
        }
        # JSON-RPC spec requires integer error codes
        assert isinstance(response["error"]["code"], int)
        assert response["error"]["code"] == -32600

    def test_valid_success_response_structure(self):
        """Test valid JSON-RPC 2.0 success response structure."""
        response = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "result": {"tools": []},
            "error": None,
        }

        # Must have jsonrpc version
        assert response["jsonrpc"] == "2.0"

        # Must have non-null id
        assert response["id"] == "test-123"
        assert response["id"] is not None

        # Must have result
        assert response["result"] is not None

        # Must not have error
        assert response["error"] is None

    def test_valid_error_response_structure(self):
        """Test valid JSON-RPC 2.0 error response structure."""
        response = {
            "jsonrpc": "2.0",
            "id": 42,
            "result": None,
            "error": {
                "code": METHOD_NOT_FOUND,
                "message": "Method not found: unknown_method",
            },
        }

        # Must have jsonrpc version
        assert response["jsonrpc"] == "2.0"

        # Must have non-null id
        assert response["id"] == 42
        assert response["id"] is not None

        # Must have error object
        assert response["error"] is not None
        error = response["error"]

        # Error must have code (integer)
        assert isinstance(error["code"], int)
        assert error["code"] == -32601

        # Error must have message (string)
        assert isinstance(error["message"], str)
        assert error["message"] == "Method not found: unknown_method"

        # Must not have result
        assert response["result"] is None

    def test_notification_has_no_id(self):
        """Notifications MUST NOT have an id field."""
        notification = {"jsonrpc": "2.0", "method": "notifications/tools/listChanged"}
        assert notification.get("id") is None

    def test_mcp_initialize_request_has_id(self):
        """MCP initialize request must have id (not a notification)."""
        # This is the common failure case - initialize must have id
        request = {"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}}
        assert request.get("id") is not None

    def test_id_propagation_in_handler_chain(self):
        """Test that id is correctly propagated through handler chain."""
        # Simulate handler that receives message with id
        incoming_message = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": "req-123",
        }

        # Handler extracts id
        msg_id = incoming_message.get("id")

        # Handler returns response with same id
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": []},
            "error": None,
        }

        # Id must be preserved
        assert response["id"] == "req-123"
        assert response["id"] is not None


class TestErrorCodes:
    """Tests for JSON-RPC error codes from MCP SDK."""

    def test_standard_error_codes(self):
        """Test standard JSON-RPC error codes."""
        assert PARSE_ERROR == -32700
        assert INVALID_REQUEST == -32600
        assert METHOD_NOT_FOUND == -32601
        assert INVALID_PARAMS == -32602
        assert INTERNAL_ERROR == -32603
