"""Integration tests for SSE transport with real HTTP server.

Note: SSE streaming tests are skipped as they require complex connection management.
Use the SSE server directly in manual tests for streaming functionality.
"""

import asyncio
import socket

import pytest
import httpx

from omni.mcp.transport.sse import SSEServer
from omni.mcp.types import (
    JSONRPCRequest,
    make_success_response,
)


def get_unused_port() -> int:
    """Get an available port for testing."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MockRequestHandler:
    """Mock request handler for integration tests."""

    def __init__(self):
        self.notifications: list[tuple[str, dict]] = []
        self.request_count = 0

    async def handle_request(self, request: JSONRPCRequest):
        """Handle incoming requests."""
        self.request_count += 1

        if request.method == "tools/list":
            return make_success_response(
                id=request.id,
                result={"tools": [{"name": "test_tool"}]},
            )
        elif request.method == "ping":
            return make_success_response(id=request.id, result={"pong": True})
        else:
            return make_success_response(id=request.id, result={"method": request.method})

    async def handle_notification(self, method: str, params):
        """Handle incoming notifications."""
        self.notifications.append((method, params or {}))

    async def initialize(self):
        """Handle initialization."""
        pass


@pytest.fixture
def handler():
    """Create test handler."""
    return MockRequestHandler()


@pytest.fixture
async def sse_server(handler):
    """Create and start SSE server for testing."""
    port = get_unused_port()
    server = SSEServer(handler=handler, host="127.0.0.1", port=port)

    # Start server in background
    server_task = asyncio.create_task(server.start())

    # Wait for server to start
    await asyncio.sleep(0.3)

    yield server

    # Cleanup
    await server.stop()
    server_task.cancel()
    try:
        await asyncio.wait_for(server_task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass


class TestSSEHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, sse_server):
        """Test /health endpoint returns status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{sse_server.port}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "active_sessions" in data

    @pytest.mark.asyncio
    async def test_ready_endpoint(self, sse_server):
        """Test /ready endpoint returns status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{sse_server.port}/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"


class TestSSEHTTPEndpoint:
    """Test HTTP message endpoint."""

    @pytest.mark.asyncio
    async def test_message_endpoint_with_request(self, sse_server):
        """Test POST /message with JSON-RPC request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{sse_server.port}/message",
                json={
                    "jsonrpc": "2.0",
                    "method": "ping",
                    "id": 1,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert data["result"]["pong"] is True

    @pytest.mark.asyncio
    async def test_message_endpoint_with_notification(self, sse_server, handler):
        """Test POST /message with notification."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{sse_server.port}/message",
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/test",
                    "params": {"key": "value"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["result"] is True

        # Verify notification was handled
        assert len(handler.notifications) == 1
        assert handler.notifications[0][0] == "notifications/test"

    @pytest.mark.asyncio
    async def test_message_endpoint_invalid_json(self, sse_server):
        """Test POST /message with invalid JSON returns error."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{sse_server.port}/message",
                content="invalid json",
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == -32700  # PARSE_ERROR

    @pytest.mark.asyncio
    async def test_message_endpoint_with_tools_list(self, sse_server):
        """Test POST /message with tools/list request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{sse_server.port}/message",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert "tools" in data["result"]


class TestSSEServerManagement:
    """Test SSE server management."""

    @pytest.mark.asyncio
    async def test_server_is_connected(self, sse_server):
        """Test server is_connected property."""
        assert sse_server.is_connected is True

    @pytest.mark.asyncio
    async def test_server_port(self, sse_server):
        """Test server has correct port."""
        assert sse_server.port > 0
        assert sse_server.port <= 65535
