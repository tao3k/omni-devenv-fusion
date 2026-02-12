"""
mcp_client.py - MCP Client for CLI Commands

Enables CLI commands to connect to a running MCP server and call tools
(like embedding) without reloading models.

Usage:
    from omni.agent.mcp_client import get_mcp_client, embed_texts

    client = get_mcp_client()
    vectors = await client.call_tool("embed_texts", {"texts": ["hello world"]})
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

# Default MCP server URL for SSE mode
DEFAULT_MCP_URL = "http://127.0.0.1:3000"

# Global client instance
_mcp_client: "MCPClient | None" = None


class MCPClient:
    """HTTP client for MCP SSE server."""

    def __init__(self, base_url: str = DEFAULT_MCP_URL):
        """Initialize MCP client.

        Args:
            base_url: Base URL of the MCP SSE server
        """
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure async client is ready."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        client = await self._ensure_client()

        # MCP SSE uses POST /message for tool calls
        request = {
            "jsonrpc": "2.0",
            "id": "cli-client",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }

        try:
            response = await client.post(
                f"{self.base_url}/message",
                json=request,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            # Extract result from JSON-RPC response
            if "result" in result and result["result"]:
                content = result["result"].get("content", [])
                if content and isinstance(content, list):
                    # Return the text content
                    return content[0].get("text", "")
            return None

        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to call MCP tool '{name}': {e}")

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via MCP server.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        result = await self.call_tool("embed_texts", {"texts": texts})
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return []
        return []

    async def embed_single(self, text: str) -> list[float]:
        """Generate a single embedding via MCP server.

        Args:
            text: Text to embed

        Returns:
            Single embedding vector
        """
        result = await self.call_tool("embed_single", {"text": text})
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return []
        return []


async def get_mcp_client(base_url: str | None = None) -> MCPClient:
    """Get or create MCP client.

    Args:
        base_url: Optional base URL override

    Returns:
        MCPClient instance
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(base_url=base_url or DEFAULT_MCP_URL)
    return _mcp_client


async def close_mcp_client() -> None:
    """Close the global MCP client."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None


async def embed_via_mcp(texts: list[str]) -> list[list[float]]:
    """Convenience function to embed texts via MCP server.

    Returns:
        List of embedding vectors, or None if MCP server is not available
    """
    try:
        client = await get_mcp_client()
        return await client.embed_texts(texts)
    except ConnectionError:
        return None


__all__ = [
    "MCPClient",
    "get_mcp_client",
    "close_mcp_client",
    "embed_via_mcp",
]
