"""
src/agent/capabilities/output.py
Output Formatting Tools - MCP response beautification

Provides:
- format_mcp_response: Format MCP response as readable JSON
- pretty_json: Format Python dict as pretty-printed JSON
- view_structured_data: Format data as Markdown lists

Philosophy:
- Output should be human-readable
- Pure Python json module, no external dependencies
- Simple and direct
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
import structlog

logger = structlog.get_logger(__name__)


def _format_json(data: Any, indent: int = 2) -> str:
    """Format data as pretty-printed JSON using Python's built-in json module."""
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True)


def register_output_tools(mcp: FastMCP) -> None:
    """Register all output formatting tools with the MCP server."""

    @mcp.tool()
    async def format_mcp_response(response: dict) -> str:
        """
        Format MCP response data as human-readable JSON.

        Args:
            response: The dictionary returned by an MCP tool

        Returns:
            Formatted string wrapped in Markdown code block

        Example:
            format_mcp_response({
                "success": True,
                "results": [...],
                "count": 5
            })
        """
        json_str = _format_json(response)
        return f"```json\n{json_str}\n```"

    @mcp.tool()
    async def pretty_json(data: dict, indent: int = 2) -> str:
        """
        Pretty-print a Python dictionary as formatted JSON.

        Args:
            data: The Python dictionary to format
            indent: Number of spaces for indentation (default: 2)

        Returns:
            Formatted JSON string

        Example:
            pretty_json({"name": "test", "version": "1.0.0"})
        """
        return _format_json(data, indent)

    @mcp.tool()
    async def view_structured_data(
        title: str,
        data: dict,
    ) -> str:
        """
        Display structured data as formatted Markdown lists.

        Args:
            title: Title for the data section
            data: The data to display

        Returns:
            Formatted output as Markdown

        Example:
            view_structured_data("Results", {"users": ["alice", "bob"]})
        """
        lines = [f"## {title}", ""]

        def format_value(value: Any, indent: int = 0) -> list[str]:
            """Recursively format values."""
            prefix = "  " * indent

            if isinstance(value, dict):
                if not value:
                    return [f"{prefix}- (empty dict)"]
                result = []
                for k, v in value.items():
                    if isinstance(v, (dict, list)) and v:
                        result.append(f"{prefix}- **{k}**:")
                        result.extend(format_value(v, indent + 1))
                    else:
                        result.append(f"{prefix}- **{k}**: {v}")
                return result
            elif isinstance(value, list):
                if not value:
                    return [f"{prefix}- (empty list)"]
                result = []
                for i, item in enumerate(value):
                    if isinstance(item, (dict, list)):
                        result.append(f"{prefix}- Item {i + 1}:")
                        result.extend(format_value(item, indent + 1))
                    else:
                        result.append(f"{prefix}- {item}")
                return result
            else:
                return [f"{prefix}{value}"]

        lines.extend(format_value(data))
        lines.append("")

        return "\n".join(lines)

    logger.info("Output formatting tools registered")


__all__ = [
    "register_output_tools",
]
