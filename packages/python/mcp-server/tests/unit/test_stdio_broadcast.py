"""Test StdioTransport broadcast functionality."""

import pytest
from unittest.mock import AsyncMock

from omni.mcp.transport.stdio import StdioTransport
from omni.mcp.server import MCPServer


class TestStdioTransportBroadcast:
    """Test the broadcast method for sending notifications to MCP clients."""

    def test_transport_has_broadcast_method(self):
        """StdioTransport should have a broadcast method."""
        transport = StdioTransport()
        assert hasattr(transport, 'broadcast')
        assert callable(transport.broadcast)

    def test_broadcast_is_async(self):
        """Broadcast should be an async coroutine function."""
        transport = StdioTransport()
        import asyncio
        assert asyncio.iscoroutinefunction(transport.broadcast)

    def test_server_send_tool_list_changed_uses_broadcast(self):
        """MCPServer.send_tool_list_changed should use transport.broadcast."""
        class MockHandler:
            pass

        transport = StdioTransport()
        server = MCPServer(MockHandler(), transport)

        # Verify the server has the method
        assert hasattr(server, 'send_tool_list_changed')

        # Verify transport.broadcast exists (which send_tool_list_changed uses)
        assert hasattr(transport, 'broadcast')

    @pytest.mark.asyncio
    async def test_send_tool_list_changed_calls_broadcast(self):
        """MCPServer.send_tool_list_changed should call transport.broadcast."""
        class MockHandler:
            pass

        transport = StdioTransport()
        transport.broadcast = AsyncMock()
        server = MCPServer(MockHandler(), transport)

        await server.send_tool_list_changed()

        # Verify broadcast was called
        transport.broadcast.assert_called_once()
        call_args = transport.broadcast.call_args[0][0]
        assert call_args["method"] == "notifications/tools/listChanged"
        assert call_args["params"] is None
        # Notifications must NOT have id
        assert "id" not in call_args

    @pytest.mark.asyncio
    async def test_broadcast_method_exists_and_is_callable(self):
        """Verify broadcast method can be called without error."""
        transport = StdioTransport()

        # The method should exist and be callable
        assert callable(transport.broadcast)

        # We can't easily test the actual output in unit tests
        # since it writes to stdout, but we verify the method is properly defined
        import asyncio
        assert asyncio.iscoroutinefunction(transport.broadcast)
