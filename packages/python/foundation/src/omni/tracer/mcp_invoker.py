"""
mcp_invoker.py - MCP-backed ToolInvoker adapters for pipeline nodes.

This module bridges compiled pipeline nodes to MCP clients/servers without
coupling pipeline compiler logic to a specific transport implementation.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from .node_factory import ToolInvoker


class MCPToolClient(Protocol):
    """Protocol for MCP clients/servers that can execute tools."""

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool by name with arguments."""


class MCPToolInvoker(ToolInvoker):
    """ToolInvoker adapter for MCP tool execution.

    Supports common call styles:
    - call_tool(name, arguments={...})  # MCP HTTP/SSE style
    - call_tool(name, **kwargs)         # adapter/fake server style
    """

    def __init__(self, client: MCPToolClient):
        self._client = client

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any] | Any:
        tool_name = f"{server}.{tool}"
        result = await self._call_tool(tool_name, payload)
        return self._normalize_result(result)

    async def _call_tool(self, tool_name: str, payload: dict[str, Any]) -> Any:
        """Execute MCP tool call across compatible signatures."""
        call_tool = getattr(self._client, "call_tool", None)
        if call_tool is None:
            raise TypeError("MCP client does not expose call_tool")

        # Preferred signature: call_tool(name, arguments={...})
        try:
            return await call_tool(tool_name, payload)
        except TypeError:
            pass
        # Fallback signature: call_tool(name, **kwargs)
        try:
            return await call_tool(tool_name, **payload)
        except TypeError:
            pass
        try:
            return await call_tool(tool_name, arguments=payload)
        except TypeError:
            pass
        # Last attempt for non-standard clients.
        return await call_tool(tool_name, payload)

    @staticmethod
    def _normalize_result(result: Any) -> dict[str, Any] | Any:
        """Normalize common MCP response shapes into dict payloads."""
        if isinstance(result, list):
            # Typical MCP content list: [{"type":"text","text":"..."}]
            if result and isinstance(result[0], dict):
                text = result[0].get("text")
                if isinstance(text, str):
                    parsed = MCPToolInvoker._try_parse_json_text(text)
                    return parsed if parsed is not None else {"text": text}
            return {"items": result}
        if isinstance(result, str):
            parsed = MCPToolInvoker._try_parse_json_text(result)
            return parsed if parsed is not None else {"text": result}
        return result

    @staticmethod
    def _try_parse_json_text(text: str) -> dict[str, Any] | list[Any] | None:
        """Parse JSON payloads embedded in text responses."""
        value = text.strip()
        if not value:
            return None
        if not (
            (value.startswith("{") and value.endswith("}"))
            or (value.startswith("[") and value.endswith("]"))
        ):
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None


__all__ = [
    "MCPToolClient",
    "MCPToolInvoker",
]
