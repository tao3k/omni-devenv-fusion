"""
kernel/components/mcp_tool.py - MCP Tool Adapter

Integrates Kernel skill commands with MCP Server tool protocol.
Provides unified tool registration, discovery, and execution.

Usage:
    from agent.core.kernel.components.mcp_tool import MCPToolAdapter

    adapter = MCPToolAdapter(server)
    adapter.register_tool("git", "commit", commit_func)
    tools = await adapter.list_tools()
"""

from __future__ import annotations

from typing import Any

from omni.core.errors import CoreErrorCode, OmniError
from omni.core.responses import ToolResponse

from omni.foundation.config.logging import get_logger

logger = get_logger(__name__)


class MCPToolAdapter:
    """Adapter that bridges Kernel skill commands to MCP Server tools.

    Responsibilities:
    - Register skill commands as MCP tools
    - List all registered tools
    - Execute tool calls via skill runtime
    - Handle tool change notifications

    This adapter maintains compatibility with the existing skill_runtime
    while providing a clean interface for MCP integration.
    """

    def __init__(self, server: Server) -> None:
        """Initialize the MCP tool adapter.

        Args:
            server: The MCP Server instance to register handlers with.
        """
        self._server = server
        self._tools: dict[
            str, tuple[str, str, Callable]
        ] = {}  # tool_name -> (skill, command, func)

        # Register handlers with the server
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register list_tools and call_tool handlers with the MCP server."""
        self._server.list_tools()(self._handle_list_tools)
        self._server.call_tool()(self._handle_call_tool)

    async def _handle_list_tools(self) -> list[Tool]:
        """Handle MCP list_tools request.

        Returns:
            List of all registered MCP tools.
        """
        return await self.list_tools()

    async def _handle_call_tool(self, name: str, arguments: dict | None) -> list:
        """Handle MCP call_tool request.

        Args:
            name: Tool name in format "skill.command"
            arguments: Tool arguments dictionary

        Returns:
            List of text content results.
        """
        return await self.call_tool(name, arguments or {})

    # =============================================================================
    # Tool Registration
    # =============================================================================

    def register_tool(
        self,
        skill_name: str,
        command_name: str,
        func: Callable,
        description: str | None = None,
    ) -> str:
        """Register a skill command as an MCP tool.

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "commit")
            func: The command function
            description: Optional tool description

        Returns:
            The full tool name (skill.command format)
        """
        tool_name = f"{skill_name}.{command_name}"

        # Extract description from function if not provided
        if description is None:
            description = getattr(func, "__doc__", None) or f"Execute {tool_name}"
            if description:
                # Take first line only
                description = description.strip().split("\n")[0]

        # Store tool metadata
        config = getattr(func, "_skill_config", {})
        input_schema = config.get("input_schema", {"type": "object"})

        self._tools[tool_name] = (skill_name, command_name, func)

        logger.debug(
            "Tool registered",
            tool=tool_name,
            description=description[:50] if description else None,
        )

        return tool_name

    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister an MCP tool.

        Args:
            tool_name: The tool name to remove

        Returns:
            True if tool was removed, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.debug("Tool unregistered", tool=tool_name)
            return True
        return False

    def get_tool(self, tool_name: str) -> tuple[str, str, Callable] | None:
        """Get tool metadata.

        Args:
            tool_name: The tool name

        Returns:
            Tuple of (skill_name, command_name, function) or None
        """
        return self._tools.get(tool_name)

    # =============================================================================
    # Tool Listing
    # =============================================================================

    async def list_tools(self) -> list[Tool]:
        """List all registered MCP tools.

        Returns:
            List of MCP Tool objects
        """
        tools: list[Tool] = []

        for tool_name, (skill_name, command_name, func) in self._tools.items():
            # Get tool configuration
            config = getattr(func, "_skill_config", {})
            description = (
                config.get("description")
                or getattr(func, "__doc__", None)
                or f"Execute {tool_name}"
            )

            # Get input schema
            input_schema = config.get("input_schema", {"type": "object"})

            tools.append(
                Tool(
                    name=tool_name,
                    description=description,
                    inputSchema=input_schema,
                )
            )

        logger.info(f"[Tools] Listed {len(tools)} tools from adapter")
        return tools

    # =============================================================================
    # Tool Execution
    # =============================================================================

    async def call_tool(self, name: str, args: dict) -> list[dict]:
        """Execute a tool call.

        Args:
            name: Tool name in format "skill.command"
            args: Tool arguments

        Returns:
            List of content dictionaries (MCP protocol format)
        """
        tool_data = self.get_tool(name)
        if tool_data is None:
            logger.error(f"Tool not found: {name}")
            response = ToolResponse.error(
                message=f"Tool not found: {name}",
                code=CoreErrorCode.TOOL_NOT_FOUND.value,
                metadata={"tool": name},
            )
            return response.to_mcp()

        skill_name, command_name, func = tool_data

        # Validate required arguments before execution
        config = getattr(func, "_skill_config", {})
        input_schema = config.get("input_schema", {})
        required_fields = input_schema.get("required", [])

        missing_fields = [f for f in required_fields if f not in args or args.get(f) is None]
        if missing_fields:
            # Provide helpful error with expected format
            properties = input_schema.get("properties", {})
            format_hint = ""
            for field in required_fields:
                field_type = properties.get(field, {}).get("type", "any")
                format_hint += f'  "{field}": <{field_type}>, '

            error_msg = (
                f"Missing required arguments: {', '.join(missing_fields)}\n"
                f"Expected format:\n"
                f"[TOOL_CALL: {name}]({{{format_hint.rstrip(', ')}}})"
            )
            logger.warning(f"Tool call validation failed for {name}: {missing_fields}")
            response = ToolResponse.error(
                message=error_msg,
                code=CoreErrorCode.MISSING_REQUIRED.value,
                metadata={
                    "tool": name,
                    "missing_fields": missing_fields,
                },
            )
            return response.to_mcp()

        try:
            # Check if function is async
            import asyncio

            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            # Result should be ToolResponse
            if isinstance(result, ToolResponse):
                return result.to_mcp()

            # Legacy support: wrap raw result
            return ToolResponse.success(data=result).to_mcp()

        except OmniError as e:
            logger.error(f"Tool execution error: {e}")
            response = ToolResponse.error(
                message=e.message,
                code=e.code.value if e.code else None,
                metadata={
                    "tool": name,
                    **e.details,
                },
            )
            return response.to_mcp()

        except Exception as e:
            error_msg = f"Error executing {name}: {e}"
            logger.error(error_msg, exc_info=True)
            response = ToolResponse.error(
                message=str(e),
                code=CoreErrorCode.TOOL_EXECUTION_FAILED.value,
                metadata={
                    "tool": name,
                    "error_type": type(e).__name__,
                },
            )
            return response.to_mcp()

    # =============================================================================
    # Properties
    # =============================================================================

    @property
    def tool_count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)

    @property
    def tool_names(self) -> list[str]:
        """Get list of all tool names."""
        return list(self._tools.keys())
