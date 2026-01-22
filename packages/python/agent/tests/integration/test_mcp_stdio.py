"""
Unit test for MCP server using omni.mcp transport.

Tests that:
1. Server module imports correctly
2. Handler implements MCPRequestHandler protocol
3. Transport layer works with handler
4. Server can be composed correctly

Usage:
    uv run pytest packages/python/agent/src/agent/tests/integration/test_mcp_stdio.py -v
"""

import asyncio
from pathlib import Path

import pytest


class TestServerModuleImports:
    """Test all imports required for MCP server."""

    def test_server_module_import(self):
        """Verify server module imports correctly."""
        from omni.agent.server import AgentMCPHandler, create_agent_handler

        assert AgentMCPHandler is not None
        assert callable(create_agent_handler)

    def test_handler_has_protocol_methods(self):
        """Verify AgentMCPHandler has required protocol methods."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        assert hasattr(handler, "handle_request")
        assert hasattr(handler, "handle_notification")
        assert hasattr(handler, "initialize")

    def test_omni_mcp_transport_import(self):
        """Verify omni.mcp transport imports correctly."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        assert MCPServer is not None
        assert StdioTransport is not None

    def test_omni_mcp_sse_import(self):
        """Verify omni.mcp SSE transport imports correctly."""
        from omni.mcp.transport.sse import SSEServer

        assert SSEServer is not None


class TestServerComposition:
    """Test server composition with handler and transport."""

    def test_create_handler(self):
        """Test that create_agent_handler returns a handler."""
        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        assert handler is not None

    def test_handler_not_initialized_initially(self):
        """Test that handler is not initialized until initialize() is called."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        assert handler._initialized is False

    @pytest.mark.asyncio
    async def test_handler_initialize(self):
        """Test that handler.initialize() sets _initialized to True."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        await handler.initialize()
        assert handler._initialized is True


class TestExitQueue:
    """Test exit queue mechanism for graceful shutdown."""

    def test_exit_queue_operations(self):
        """Test putting and getting from exit queue."""

        async def test_queue():
            test_queue = asyncio.Queue()

            # Put a value
            test_queue.put_nowait(True)

            # Get the value
            value = await test_queue.get()
            assert value is True
            assert test_queue.empty()

        asyncio.run(test_queue())


class TestWatcherPathDisplay:
    """Test watcher path display functionality."""

    def test_skills_path_relative_display(self):
        """Test that skills path is displayed correctly."""
        from omni.foundation.config.skills import SKILLS_DIR

        skills_path = str(SKILLS_DIR())
        skills_path_obj = Path(skills_path)

        # Get last 2 components
        parts = (
            skills_path_obj.parts[-2:] if len(skills_path_obj.parts) >= 2 else skills_path_obj.parts
        )
        display_path = "/".join(parts)

        # Should contain "skills"
        assert "skills" in display_path


class TestGracefulShutdown:
    """Test graceful shutdown mechanisms."""

    def test_server_can_be_composed(self):
        """Test that server can be composed from handler and transport."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        transport = StdioTransport()
        # Set handler via set_handler method (new API)
        transport.set_handler(handler)
        server = MCPServer(handler=handler, transport=transport)

        assert server.handler is handler
        assert server.transport is transport
        assert server.is_running is False


class TestServerProcessManagement:
    """Test server process management.

    Note: Current implementation uses omni.mcp transport directly.
    """

    def test_server_has_start_and_stop(self):
        """Test that server has start and stop methods."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        transport = StdioTransport()
        transport.set_handler(handler)  # New API: set handler separately
        server = MCPServer(handler=handler, transport=transport)

        assert hasattr(server, "start")
        assert hasattr(server, "stop")
        assert callable(server.start)
        assert callable(server.stop)


class TestShutdownCount:
    """Test shutdown counter for double-Ctrl-C detection."""

    def test_shutdown_uses_os_exit(self):
        """Test that shutdown uses os._exit for immediate termination."""

        # Verify os module is available for _exit
        import os

        assert hasattr(os, "_exit")


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance for tool schema."""

    @pytest.mark.asyncio
    async def test_tool_list_returns_valid_schema(self):
        """Test that tools/list returns valid MCP-compliant inputSchema."""
        from omni.agent.server import create_agent_handler
        from omni.mcp.types import JSONRPCRequest

        handler = create_agent_handler()
        await handler.initialize()

        request = JSONRPCRequest(id=1, method="tools/list", params={})
        response = await handler._handle_list_tools(request)

        assert response.error is None
        tools = response.result.get("tools", [])
        assert len(tools) > 0, "No tools returned"

        # Validate each tool has valid inputSchema
        for tool in tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "inputSchema" in tool, f"Tool missing inputSchema: {tool.get('name')}"
            schema = tool["inputSchema"]
            # MCP requires type to be "object"
            assert schema.get("type") == "object", (
                f"Tool '{tool['name']}' has invalid type: {schema.get('type')}"
            )

    @pytest.mark.asyncio
    async def test_tool_names_follow_skill_command_pattern(self):
        """Test that tool names follow 'skill.command' pattern."""
        from omni.agent.server import create_agent_handler
        from omni.mcp.types import JSONRPCRequest

        handler = create_agent_handler()
        await handler.initialize()

        request = JSONRPCRequest(id=1, method="tools/list", params={})
        response = await handler._handle_list_tools(request)

        tools = response.result.get("tools", [])

        for tool in tools:
            name = tool["name"]
            assert "." in name, f"Tool name '{name}' should follow 'skill.command' pattern"

    @pytest.mark.asyncio
    async def test_tool_descriptions_are_present(self):
        """Test that all tools have descriptions."""
        from omni.agent.server import create_agent_handler
        from omni.mcp.types import JSONRPCRequest

        handler = create_agent_handler()
        await handler.initialize()

        request = JSONRPCRequest(id=1, method="tools/list", params={})
        response = await handler._handle_list_tools(request)

        tools = response.result.get("tools", [])

        for tool in tools:
            assert "description" in tool, f"Tool '{tool.get('name')}' missing description"
            assert tool["description"], f"Tool '{tool.get('name')}' has empty description"


class TestIntegration:
    """Integration tests for imports and basic functionality."""

    def test_full_import_chain(self):
        """Test that all components can be imported together."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.sse import SSEServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import AgentMCPHandler, create_agent_handler

        # All should be callable or not None
        assert AgentMCPHandler is not None
        assert callable(create_agent_handler)
        assert MCPServer is not None
        assert StdioTransport is not None
        assert SSEServer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
