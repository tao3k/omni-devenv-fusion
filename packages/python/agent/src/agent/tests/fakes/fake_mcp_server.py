"""
Fake MCP Server for Testing.

A mock MCP server that simulates tool registration and execution.
"""

from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock


class FakeMCPServer:
    """
    Fake MCP server for testing without a real MCP Server instance.

    Simulates tool registration, prompt listing, and resource management.

    Usage:
        server = FakeMCPServer()
        server.add_tool("git_status", lambda: "main")
        result = await server.call_tool("git_status")
    """

    def __init__(self, name: str = "test"):
        self.name = name
        self._tools: Dict[str, Callable] = {}
        self._prompts: Dict[str, str] = {}
        self._resources: Dict[str, str] = {}
        self._context: Dict[str, Any] = {}

    def add_tool(
        self,
        name: str,
        func: Callable,
        description: str = "",
    ) -> None:
        """Register a tool function."""
        self._tools[name] = func
        if description:
            setattr(func, "__description__", description)

    def add_prompt(self, name: str, template: str) -> None:
        """Register a prompt template."""
        self._prompts[name] = template

    def add_resource(self, name: str, content: str) -> None:
        """Register a resource."""
        self._resources[name] = content

    async def list_tools(self) -> List[str]:
        """List registered tool names."""
        return list(self._tools.keys())

    async def list_prompts(self) -> List[str]:
        """List registered prompt names."""
        return list(self._prompts.keys())

    async def list_resources(self) -> List[str]:
        """List registered resource names."""
        return list(self._resources.keys())

    async def call_tool(self, name: str, **kwargs) -> Any:
        """Call a registered tool."""
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        func = self._tools[name]
        if callable(func):
            return func(**kwargs)
        return func

    def get_tool_description(self, name: str) -> Optional[str]:
        """Get tool description."""
        if name in self._tools:
            return getattr(self._tools[name], "__description__", "")
        return None

    def clear(self) -> None:
        """Clear all registered tools, prompts, and resources."""
        self._tools.clear()
        self._prompts.clear()
        self._resources.clear()
        self._context.clear()


class FakeMCPTool:
    """
    Fake MCP tool for testing tool decorators and registration.

    Usage:
        tool = FakeMCPStool("git_status", lambda ctx: "main")
        assert tool.name == "git_status"
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str = "",
    ):
        self.name = name
        self.func = func
        self.description = description

    async def call(self, **kwargs) -> Any:
        """Execute the tool."""
        return self.func(**kwargs)


def create_mock_mcp_server() -> MagicMock:
    """
    Create a mock MCP server for injection in tests.

    Returns a MagicMock with async methods for list_tools, list_prompts, etc.

    Usage:
        mock_server = create_mock_mcp_server()
        mock_server.list_tools = AsyncMock(return_value=["git_status"])
    """
    mock = MagicMock()
    mock.list_tools = AsyncMock(return_value=[])
    mock.list_prompts = AsyncMock(return_value=[])
    mock.list_resources = AsyncMock(return_value=[])
    return mock
