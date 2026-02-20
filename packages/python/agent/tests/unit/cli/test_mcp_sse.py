"""
Tests for MCP SSE/HTTP transport.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import omni.agent.mcp_server.sse as sse_module
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
        assert "ready" in data
        assert "initializing" in data
        assert "observability" in data
        assert "total_requests" in data["observability"]
        assert "in_flight" in data["observability"]


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
async def test_health_observability_increments_after_mcp_requests(test_app):
    """Health should expose request counters after MCP traffic."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/health")
        before_total = first.json()["observability"]["total_requests"]

        response = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/list",
                "params": {},
            },
        )
        assert response.status_code == 200

        second = await client.get("/health")
        after = second.json()["observability"]
        assert after["total_requests"] >= before_total + 1
        assert any(item["endpoint"].startswith("mcp:") for item in after["top_endpoints"])


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
async def test_sse_delete_endpoint(test_app):
    """Test /sse DELETE session close is accepted (streamable HTTP compatibility)."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/sse",
            headers={"MCP-Session-Id": "test-session"},
        )
        assert response.status_code == 204
        assert response.headers.get("mcp-session-id") == "test-session"


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


@pytest.mark.asyncio
async def test_messages_delete_endpoint(test_app):
    """Test /messages/ DELETE session close is accepted."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/messages/",
            headers={"MCP-Session-Id": "test-session"},
        )
        assert response.status_code == 204
        assert response.headers.get("mcp-session-id") == "test-session"


@pytest.mark.asyncio
async def test_embed_single_uses_threadpool(test_app):
    """Test /embed/single offloads blocking embed call to threadpool."""
    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed(_text: str):
            return [[0.11, 0.22, 0.33]]

    async def _threadpool_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        mock_threadpool.side_effect = _threadpool_side_effect
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed/single", json={"text": "hello"})

    assert response.status_code == 200
    assert response.json()["vector"] == [0.11, 0.22, 0.33]
    assert mock_threadpool.await_count == 1


@pytest.mark.asyncio
async def test_embed_batch_uses_threadpool(test_app):
    """Test /embed/batch offloads blocking embed call to threadpool."""
    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed_batch(_texts: list[str]):
            return [[0.11, 0.22, 0.33], [0.44, 0.55, 0.66]]

    async def _threadpool_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        mock_threadpool.side_effect = _threadpool_side_effect
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed/batch", json={"texts": ["a", "b"]})

    assert response.status_code == 200
    assert response.json()["vectors"] == [[0.11, 0.22, 0.33], [0.44, 0.55, 0.66]]
    assert mock_threadpool.await_count == 1


@pytest.mark.asyncio
async def test_embed_alias_routes_to_embed_batch(test_app):
    """Test /embed alias behaves the same as /embed/batch."""
    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed_batch(_texts: list[str]):
            return [[0.11, 0.22, 0.33]]

    async def _threadpool_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        mock_threadpool.side_effect = _threadpool_side_effect
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed", json={"texts": ["a"]})

    assert response.status_code == 200
    assert response.json()["vectors"] == [[0.11, 0.22, 0.33]]
    assert mock_threadpool.await_count == 1


@pytest.mark.asyncio
async def test_embed_batch_fail_fast_on_overload():
    """Concurrent embed requests should fast-fail with 503 when queue is saturated."""
    with patch.object(sse_module, "_resolve_embed_http_limits", return_value=(5.0, 0.01, 1)):
        test_app = create_sse_app(MockHandler(), host="127.0.0.1", port=3003)
    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed_batch(_texts: list[str]):
            return [[0.11, 0.22, 0.33]]

    async def _slow_threadpool(func, *args, **kwargs):
        await asyncio.sleep(0.08)
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        mock_threadpool.side_effect = _slow_threadpool
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(client.post("/embed/batch", json={"texts": ["a"]}))
            await asyncio.sleep(0.005)
            second = await client.post("/embed/batch", json={"texts": ["b"]})
            first_response = await first

    assert first_response.status_code == 200
    assert second.status_code == 503
    assert second.json()["code"] == "embedding_overloaded"
    assert mock_threadpool.await_count >= 1


@pytest.mark.asyncio
async def test_embed_batch_fail_fast_on_timeout():
    """Slow embedding backend should return timeout 503 instead of hanging."""
    with patch.object(sse_module, "_resolve_embed_http_limits", return_value=(0.01, 0.5, 4)):
        test_app = create_sse_app(MockHandler(), host="127.0.0.1", port=3003)
    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed_batch(_texts: list[str]):
            return [[0.11, 0.22, 0.33]]

    async def _slow_threadpool(func, *args, **kwargs):
        await asyncio.sleep(0.05)
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        mock_threadpool.side_effect = _slow_threadpool
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed/batch", json={"texts": ["a"]})

    assert response.status_code == 503
    assert response.json()["code"] == "embedding_timeout"
    assert mock_threadpool.await_count == 1


@pytest.mark.asyncio
async def test_embed_batch_returns_503_when_unavailable_and_recovery_fails(test_app):
    """Test /embed/batch returns 503 when embedding backend is unavailable after auto-heal attempt."""
    from omni.foundation.services.embedding import EmbeddingUnavailableError

    transport = ASGITransport(app=test_app)

    class _Svc:
        @staticmethod
        def embed_batch(_texts: list[str]):
            raise EmbeddingUnavailableError("upstream unavailable")

    async def _threadpool_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=_Svc()),
        patch(
            "omni.agent.mcp_server.sse._attempt_embedding_backend_recovery", new=AsyncMock()
        ) as m_heal,
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        m_heal.return_value = False
        mock_threadpool.side_effect = _threadpool_side_effect
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed/batch", json={"texts": ["a", "b"]})

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "embedding_unavailable"
    assert payload["vectors"] == []
    assert m_heal.await_count == 1


@pytest.mark.asyncio
async def test_embed_batch_retries_after_auto_heal_success(test_app):
    """Test /embed/batch retries once after successful auto-heal."""
    from omni.foundation.services.embedding import EmbeddingUnavailableError

    transport = ASGITransport(app=test_app)

    class _Svc:
        def __init__(self):
            self.calls = 0
            self.reset_calls = 0

        def embed_batch(self, _texts: list[str]):
            self.calls += 1
            if self.calls == 1:
                raise EmbeddingUnavailableError("connection refused")
            return [[0.11, 0.22, 0.33]]

        def reset_litellm_circuit(self):
            self.reset_calls += 1

    service = _Svc()

    async def _threadpool_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch("omni.foundation.services.embedding.get_embedding_service", return_value=service),
        patch(
            "omni.agent.mcp_server.sse._attempt_embedding_backend_recovery", new=AsyncMock()
        ) as m_heal,
        patch(
            "omni.agent.mcp_server.sse.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_threadpool,
    ):
        m_heal.return_value = True
        mock_threadpool.side_effect = _threadpool_side_effect
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/embed/batch", json={"texts": ["a"]})

    assert response.status_code == 200
    assert response.json()["vectors"] == [[0.11, 0.22, 0.33]]
    assert service.calls == 2
    assert m_heal.await_count == 1


@pytest.mark.asyncio
async def test_embedding_recovery_singleflight_under_concurrency():
    """Concurrent recovery requests should trigger one upstream heal attempt."""
    calls = 0

    def _recover() -> bool:
        nonlocal calls
        calls += 1
        time.sleep(0.02)
        return True

    with patch(
        "omni.agent.mcp_server.sse._recover_embedding_backend_blocking", side_effect=_recover
    ):
        sse_module._embed_recovery_next_attempt_at = 0.0
        results = await asyncio.gather(
            sse_module._attempt_embedding_backend_recovery("probe-a"),
            sse_module._attempt_embedding_backend_recovery("probe-b"),
            sse_module._attempt_embedding_backend_recovery("probe-c"),
        )

    assert results.count(True) == 1
    assert calls == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
