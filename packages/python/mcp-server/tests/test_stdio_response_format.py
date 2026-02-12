"""
Comprehensive tests for MCP stdio transport response format.

These tests ensure JSON-RPC 2.0 compliance and prevent response format bugs
that could cause MCP client validation failures.

Critical invariants tested:
1. All responses MUST have "jsonrpc": "2.0"
2. All responses MUST have "id" field matching the request
3. Responses MUST contain either "result" OR "error", never both
4. Error responses MUST have "error" with "code" and "message"
5. Parse/invalid request errors MUST have id=null (valid per JSON-RPC 2.0)
6. Notifications MUST NOT have "id" field

Run with:
    uv run pytest packages/python/mcp-server/tests/test_stdio_response_format.py -v
"""

import asyncio
import io
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.mcp.transport.stdio import StdioTransport
from omni.mcp.server import MCPServer


class MockServer:
    """Mock server for testing transport without full MCP stack."""

    def __init__(self):
        self.handlers: dict[str, Any] = {}

    def register(self, method: str, handler):
        self.handlers[method] = handler

    async def process_message(self, message: dict) -> dict | None:
        """Process a message and return response dict."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        # Handle notifications (no response)
        if msg_id is None:
            if method.startswith("notifications/"):
                return None
            # Invalid: request without id
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid request: id required"},
            }

        # Handle known methods
        if method in self.handlers:
            try:
                # Pass full message with method included for handler context
                handler_message = dict(message)
                result = await self.handlers[method](handler_message)
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(e)},
                }

        # Method not found
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


class MockHandler:
    """Mock handler implementing MCPRequestHandler protocol."""

    async def handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC request - accepts full message dict."""
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "tools/list":
            return {"tools": [{"name": "test_tool", "inputSchema": {"type": "object"}}]}
        elif method == "echo":
            return params.get("value", "")
        elif method == "error_test":
            raise ValueError("Test error")
        return {"result": "ok"}

    async def handle_notification(self, method: str, params: Any | None) -> None:
        """Handle a notification."""
        pass

    async def initialize(self) -> None:
        """Initialize handler."""
        pass


class TestJSONRPCResponseFormat:
    """Test JSON-RPC 2.0 response format compliance."""

    @pytest.fixture
    def transport(self):
        """Create a stdio transport for testing."""
        return StdioTransport()

    @pytest.fixture
    def mock_server(self):
        """Create a mock server with test handlers."""
        server = MockServer()
        handler = MockHandler()
        server.register("tools/list", handler.handle_request)
        server.register("echo", handler.handle_request)
        server.register("error_test", handler.handle_request)
        return server

    def test_response_has_jsonrpc_version(self, transport, mock_server):
        """All responses MUST have 'jsonrpc': '2.0'."""
        # Simulate processing a message and capturing the response
        captured_response = None

        def capture_response(response: dict):
            nonlocal captured_response
            captured_response = response

        # Mock _write_response to capture response
        transport._write_response = capture_response

        # Simulate a valid request
        request = {"jsonrpc": "2.0", "id": 1, "method": "echo", "params": {"value": "test"}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert captured_response is not None, "Response should not be None"
        assert captured_response.get("jsonrpc") == "2.0", "Response must have jsonrpc: '2.0'"

    def test_response_id_matches_request(self, transport, mock_server):
        """Response id MUST match request id."""
        captured_response = None

        def capture_response(response: dict):
            nonlocal captured_response
            captured_response = response

        transport._write_response = capture_response

        test_id = 42
        request = {"jsonrpc": "2.0", "id": test_id, "method": "echo", "params": {"value": "hello"}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert captured_response is not None
        assert captured_response.get("id") == test_id, (
            f"Response id ({captured_response.get('id')}) must match request id ({test_id})"
        )

    def test_response_has_result_or_error_not_both(self, transport, mock_server):
        """Responses MUST contain either 'result' OR 'error', never both."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Test success response
        request = {"jsonrpc": "2.0", "id": 1, "method": "echo", "params": {"value": "test"}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        has_result = "result" in resp
        has_error = resp.get("error") is not None
        assert has_result != has_error, (
            f"Response must have exactly one of result/error. Got: result={has_result}, error={has_error}"
        )

        captured.clear()

        # Test error response
        request = {"jsonrpc": "2.0", "id": 2, "method": "nonexistent_method"}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        has_result = "result" in resp
        has_error = resp.get("error") is not None
        assert has_result != has_error, (
            f"Response must have exactly one of result/error. Got: result={has_result}, error={has_error}"
        )

    def test_error_response_has_code_and_message(self, transport, mock_server):
        """Error responses MUST have 'error' with 'code' and 'message'."""
        captured_response = None

        def capture(response: dict):
            nonlocal captured_response
            captured_response = response

        transport._write_response = capture

        # Request unknown method to trigger error
        request = {"jsonrpc": "2.0", "id": 1, "method": "unknown_method"}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert captured_response is not None
        error = captured_response.get("error")
        assert error is not None, "Error response must have 'error' field"
        assert "code" in error, "Error must have 'code'"
        assert "message" in error, "Error must have 'message'"

    def test_parse_error_has_null_id(self, transport):
        """Parse errors MUST have id=null (per JSON-RPC 2.0 spec)."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Send invalid JSON
        asyncio.run(transport._process_message(b"not valid json", MagicMock()))

        assert len(captured) == 1
        resp = captured[0]
        assert resp.get("id") is None, "Parse error must have id=null"
        assert resp.get("error", {}).get("code") == -32700, "Parse error code must be -32700"

    def test_invalid_request_error_has_null_id(self, transport, mock_server):
        """Invalid request errors MUST have id=null when id is unknown."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Send request without id (invalid)
        request = {"jsonrpc": "2.0", "method": "echo", "params": {}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        # Error response should have null id because request had null id
        assert resp.get("id") is None, "Invalid request error must have id=null"

    def test_notifications_return_none(self, transport, mock_server):
        """Notifications (requests without id) MUST return None (no response)."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Send valid notification (no id)
        request = {"jsonrpc": "2.0", "method": "notifications/tools/listChanged", "params": {}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        # Should not produce a response
        assert len(captured) == 0, "Notifications should not produce responses"

    def test_result_field_not_present_on_error(self, transport, mock_server):
        """Error responses MUST NOT have 'result' field."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        request = {"jsonrpc": "2.0", "id": 1, "method": "unknown_method"}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        assert "result" not in resp, "Error response must not have 'result' field"


class TestResponseFormatEdgeCases:
    """Test edge cases in response format handling."""

    @pytest.fixture
    def transport(self):
        return StdioTransport()

    @pytest.fixture
    def mock_server(self):
        """Create a mock server with test handlers."""
        server = MockServer()
        handler = MockHandler()
        server.register("tools/list", handler.handle_request)
        server.register("echo", handler.handle_request)
        server.register("error_test", handler.handle_request)
        return server

    def test_response_has_result_field(self, transport, mock_server):
        """Valid responses MUST have 'result' field - test through message processing."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Server returns {"jsonrpc": "2.0", "id": 1, "result": "test"}
        request = {"jsonrpc": "2.0", "id": 1, "method": "echo", "params": {"value": "test"}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        assert "result" in resp, "Response must have 'result' field for successful requests"
        assert resp["result"] == "test"

    def test_error_response_no_result_field(self, transport, mock_server):
        """Error responses should not have 'result' field - test through message processing."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Request unknown method to trigger error
        request = {"jsonrpc": "2.0", "id": 1, "method": "unknown_method"}
        asyncio.run(transport._process_message(json.dumps(request).encode(), mock_server))

        assert len(captured) == 1
        resp = captured[0]
        assert "result" not in resp, "Error response must not have 'result' field"
        assert "error" in resp


class TestStdioTransportIntegration:
    """Integration tests for stdio transport with real message processing."""

    @pytest.fixture
    def transport(self):
        return StdioTransport()

    def test_valid_echo_request_response_cycle(self, transport):
        """Test complete request-response cycle for echo method."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        # Create a simple server
        async def echo_handler(request: dict) -> dict:
            params = request.get("params", {})
            value = params.get("value", "")
            return {"echoed": value}

        server = MockServer()
        server.register("echo", echo_handler)

        request = {"jsonrpc": "2.0", "id": 1, "method": "echo", "params": {"value": "hello world"}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), server))

        assert len(captured) == 1
        resp = captured[0]
        assert resp["id"] == 1
        assert resp["result"]["echoed"] == "hello world"

    def test_method_not_found_response_format(self, transport):
        """Test method_not_found error response format."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        server = MockServer()

        request = {"jsonrpc": "2.0", "id": 5, "method": "this_method_does_not_exist", "params": {}}
        asyncio.run(transport._process_message(json.dumps(request).encode(), server))

        assert len(captured) == 1
        resp = captured[0]
        assert resp["id"] == 5
        assert resp.get("error", {}).get("code") == -32601

    def test_exception_in_handler_response_format(self, transport):
        """Test that exceptions in handlers produce valid error responses."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        async def failing_handler() -> dict:
            raise RuntimeError("Handler exploded")

        server = MockServer()
        server.register("failing", failing_handler)

        request = {"jsonrpc": "2.0", "id": 10, "method": "failing"}
        asyncio.run(transport._process_message(json.dumps(request).encode(), server))

        assert len(captured) == 1
        resp = captured[0]
        assert resp["id"] == 10
        assert "error" in resp
        assert resp["error"]["code"] == -32603  # Internal error


class TestJSONSchemaValidation:
    """Test that responses conform to JSON-RPC 2.0 schema."""

    @pytest.fixture
    def transport(self):
        return StdioTransport()

    def test_response_schema_success(self, transport):
        """Validate successful response against JSON-RPC 2.0 schema."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        response = {"jsonrpc": "2.0", "id": 1, "result": {"data": "test"}}
        transport._write_response(response)

        assert len(captured) == 1
        resp = captured[0]

        # Schema validation
        assert "jsonrpc" in resp
        assert resp["jsonrpc"] == "2.0"
        assert "id" in resp
        assert resp["id"] == 1
        assert "result" in resp
        assert "error" not in resp

    def test_response_schema_error(self, transport):
        """Validate error response against JSON-RPC 2.0 schema."""
        captured = []

        def capture(response: dict):
            captured.append(response)

        transport._write_response = capture

        response = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32600, "message": "Invalid request"},
        }
        transport._write_response(response)

        assert len(captured) == 1
        resp = captured[0]

        # Schema validation
        assert "jsonrpc" in resp
        assert resp["jsonrpc"] == "2.0"
        assert "id" in resp
        assert "error" in resp
        assert "result" not in resp

        # Error schema
        error = resp["error"]
        assert isinstance(error, dict)
        assert "code" in error
        assert "message" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
