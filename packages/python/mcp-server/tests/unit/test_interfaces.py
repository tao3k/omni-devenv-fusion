"""Unit tests for omni.mcp.interfaces."""

from typing import Any

import pytest
from mcp.types import JSONRPCRequest, JSONRPCResponse

from omni.mcp.interfaces import (
    MCPRequestContext,
    MCPRequestHandler,
    MCPSession,
    MCPTransport,
)


class TestMCPRequestHandlerProtocol:
    """Tests for MCPRequestHandler protocol compliance."""

    def test_protocol_defines_required_methods(self):
        """Verify protocol has all required methods."""
        # Protocol should define handle_request, handle_notification, initialize
        assert hasattr(MCPRequestHandler, "__protocol_attrs__")

    @pytest.mark.asyncio
    async def test_mock_handler_implements_protocol(self):
        """Test that a mock handler can satisfy the protocol."""

        class MockHandler:
            async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
                req_id = request.get("id")
                return JSONRPCResponse(jsonrpc="2.0", id=req_id, result={})

            async def handle_notification(self, method: str, params: Any) -> None:
                pass

            async def initialize(self) -> None:
                pass

        handler = MockHandler()
        # Verify it can be used where MCPRequestHandler is expected
        assert isinstance(handler, MCPRequestHandler)


class TestMCPTransportProtocol:
    """Tests for MCPTransport protocol compliance."""

    def test_protocol_defines_required_methods(self):
        """Verify transport protocol has all required methods."""
        assert hasattr(MCPTransport, "__protocol_attrs__")

    @pytest.mark.asyncio
    async def test_mock_transport_implements_protocol(self):
        """Test that a mock transport can satisfy the protocol."""

        class MockTransport:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def set_handler(self, handler) -> None:
                pass

        transport = MockTransport()
        assert isinstance(transport, MCPTransport)


class TestMCPSessionProtocol:
    """Tests for MCPSession protocol compliance."""

    def test_protocol_defines_session_id_property(self):
        """Verify session protocol has session_id property."""
        assert hasattr(MCPSession, "__protocol_attrs__")

    @pytest.mark.asyncio
    async def test_mock_session_implements_protocol(self):
        """Test that a mock session can satisfy the protocol."""

        class MockSession:
            @property
            def session_id(self) -> str:
                return "test-session-123"

            async def send_notification(self, method: str, params: Any | None = None) -> None:
                pass

        session = MockSession()
        assert isinstance(session, MCPSession)
        assert session.session_id == "test-session-123"


class TestMCPRequestContextProtocol:
    """Tests for MCPRequestContext protocol compliance."""

    def test_protocol_defines_session_property(self):
        """Verify context protocol has session property."""
        assert hasattr(MCPRequestContext, "__protocol_attrs__")

    @pytest.mark.asyncio
    async def test_mock_context_implements_protocol(self):
        """Test that a mock context can satisfy the protocol."""

        class MockContext:
            @property
            def session(self) -> MCPSession | None:
                return None

            async def send_notification(self, method: str, params: Any | None = None) -> None:
                pass

        context = MockContext()
        assert isinstance(context, MCPRequestContext)
