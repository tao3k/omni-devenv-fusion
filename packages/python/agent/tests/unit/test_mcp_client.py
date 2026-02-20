"""Unit tests for omni.agent.mcp_client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from omni.agent.mcp_client import MCPClient


@pytest.mark.asyncio
async def test_call_tool_extracts_text_from_jsonrpc_result() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "cli-client",
        "result": {
            "content": [{"type": "text", "text": "hello"}],
            "isError": False,
        },
    }
    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response
    client._client = mock_http  # type: ignore[assignment]

    result = await client.call_tool("demo.echo", {"message": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_call_tool_returns_none_when_result_has_no_text() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"jsonrpc": "2.0", "id": "x", "result": {"items": [1, 2, 3]}}
    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response
    client._client = mock_http  # type: ignore[assignment]

    result = await client.call_tool("demo.echo", {"message": "hello"})
    assert result is None


@pytest.mark.asyncio
async def test_call_tool_wraps_http_errors_as_connection_error() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")

    mock_http = AsyncMock()
    mock_http.post.side_effect = httpx.HTTPError("network down")
    client._client = mock_http  # type: ignore[assignment]

    with pytest.raises(ConnectionError, match="demo.echo"):
        await client.call_tool("demo.echo", {"message": "hello"})


@pytest.mark.asyncio
async def test_embed_texts_parses_json_payload() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}
    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response
    client._client = mock_http  # type: ignore[assignment]
    client.call_tool = AsyncMock(return_value="[[0.1, 0.2], [0.3, 0.4]]")  # type: ignore[method-assign]

    vectors = await client.embed_texts(["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_embed_texts_prefers_direct_embed_batch_endpoint() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"vectors": [[0.9, 0.8], [0.7, 0.6]]}
    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response
    client._client = mock_http  # type: ignore[assignment]
    client.call_tool = AsyncMock(return_value="[[0.1, 0.2]]")  # type: ignore[method-assign]

    vectors = await client.embed_texts(["a", "b"])

    assert vectors == [[0.9, 0.8], [0.7, 0.6]]
    client.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_embed_single_prefers_direct_embed_single_endpoint() -> None:
    client = MCPClient(base_url="http://127.0.0.1:3000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"vector": [0.9, 0.8, 0.7]}
    mock_http = AsyncMock()
    mock_http.post.return_value = mock_response
    client._client = mock_http  # type: ignore[assignment]
    client.call_tool = AsyncMock(return_value="[0.1, 0.2, 0.3]")  # type: ignore[method-assign]

    vector = await client.embed_single("hello")

    assert vector == [0.9, 0.8, 0.7]
    client.call_tool.assert_not_called()
