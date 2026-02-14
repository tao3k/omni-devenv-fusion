"""
Tests for MCP SSE/HTTP transport.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from omni.agent.mcp_server.sse import create_sse_app


# Mock handler for testing
class MockHandler:
    """Mock MCP handler for testing."""

    def __init__(self):
        self.initialized = False

    async def initialize(self):
        self.initialized = True

    async def handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo tool",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"message": {"type": "string"}},
                                "required": ["message"],
                            },
                        }
                    ]
                },
            }
        elif method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            if tool_name == "echo":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Echo: {args.get('message', '')}"}]
                    },
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }


@pytest.fixture
def mock_handler():
    """Create mock handler."""
    return MockHandler()


@pytest.fixture
def test_app(mock_handler):
    """Create test Starlette app with SSE routes."""
    return create_sse_app(mock_handler, host="127.0.0.1", port=3003)


@pytest.mark.asyncio
async def test_health_endpoint(test_app):
    """Test health endpoint returns OK."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "active_sessions" in data


@pytest.mark.asyncio
async def test_oauth_discovery(test_app):
    """Test OAuth discovery endpoint."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/.well-known/openid-configuration")
        assert response.status_code == 200
        data = response.json()
        assert "issuer" in data
        assert data["issuer"] == "http://127.0.0.1:3003"


@pytest.mark.asyncio
async def test_oauth_register(test_app):
    """Test OAuth register endpoint."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/register")
        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data


@pytest.mark.asyncio
async def test_tools_list(test_app):
    """Test tools/list method."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        tools = data["result"].get("tools", [])
        assert any(t["name"] == "echo" for t in tools)


@pytest.mark.asyncio
async def test_tool_call(test_app):
    """Test tools/call method."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {"message": "Hello"},
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        content = data["result"].get("content", [])
        assert any(c.get("text") == "Echo: Hello" for c in content)


@pytest.mark.asyncio
async def test_initialize(test_app):
    """Test initialize method."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"


@pytest.mark.asyncio
async def test_invalid_json(test_app):
    """Test invalid JSON request."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            content="not valid json",
            headers={"content-type": "application/json"},
        )
        # Should return parse error (400 for invalid JSON)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_empty_body(test_app):
    """Test empty body request."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/", content="")
        # Should return error for empty body
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_unknown_method(test_app):
    """Test unknown method."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "unknown/method",
                "params": {},
            },
        )
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_sse_endpoint(test_app):
    """Test /sse endpoint works."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/sse",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            },
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_messages_endpoint(test_app):
    """Test /messages/ endpoint works."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/messages/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            },
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
