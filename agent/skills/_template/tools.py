"""
agent/skills/_template/tools.py
MCP tools for the template skill.
"""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register all tools for this skill."""

    @mcp.tool()
    async def example_tool(param: str) -> str:
        """
        An example tool for the template skill.

        Args:
            param: Description of the parameter

        Returns:
            Description of the return value
        """
        return f"Result: {param}"
