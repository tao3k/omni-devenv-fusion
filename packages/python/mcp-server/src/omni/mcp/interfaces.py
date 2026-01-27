"""
interfaces.py - MCP Server Interfaces

Updated to use MCP SDK types.

Dependency inversion: MCP server only talks to these interfaces.
Business layer (Agent) implements them.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Use MCP SDK types for compatibility
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse


@runtime_checkable
class MCPRequestHandler(Protocol):
    """
    Protocol for handling MCP requests.

    The Agent (business layer) must implement this interface.
    MCP server only knows this protocol, not the concrete Agent class.
    """

    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """
        Handle a JSON-RPC request with ID (expects response).
        """
        ...

    async def handle_notification(self, method: str, params: Any | None) -> None:
        """
        Handle a JSON-RPC notification (no response expected).
        """
        ...

    async def initialize(self) -> None:
        """
        Called when MCP handshake completes (initialize request).
        """
        ...


@runtime_checkable
class MCPTransport(Protocol):
    """Protocol for transport layer implementations."""

    async def start(self) -> None:
        """Start the transport."""
        ...

    async def stop(self) -> None:
        """Stop the transport."""
        ...

    def is_connected(self) -> bool:
        """Check if transport is connected."""
        ...

    def set_handler(self, handler: MCPRequestHandler) -> None:
        """Set the request handler (optional, for transports that need it)."""
        ...


@runtime_checkable
class MCPSession(Protocol):
    """
    Protocol for MCP session (SSE connection).

    Allows business layer to send notifications to connected clients.
    """

    @property
    def session_id(self) -> str:
        """Unique session identifier."""
        ...

    async def send_notification(self, method: str, params: Any | None = None) -> None:
        """
        Send a JSON-RPC notification to this session.

        Args:
            method: Notification method name (e.g., "notifications/tools/listChanged")
            params: Optional parameters
        """
        ...


@runtime_checkable
class MCPRequestContext(Protocol):
    """
    Protocol for request context containing session info.

    Passed to handlers to allow sending notifications back to client.
    """

    @property
    def session(self) -> MCPSession | None:
        """Get the current session."""
        ...

    async def send_notification(self, method: str, params: Any | None = None) -> None:
        """Send notification to the client that initiated this request."""
        ...


# Generic Server Protocol for typed context handling
class MCPServerProtocol[ContextT](Protocol):
    """
    Protocol for the MCP Server implementation with generic context.

    Type parameter ContextT specifies the type of context passed to handlers.
    """

    async def run(self, transport: MCPTransport) -> None: ...

    async def handle_message(
        self,
        message: JSONRPCMessage,
        context: ContextT,
    ) -> JSONRPCResponse | None: ...


__all__ = [
    "MCPRequestContext",
    "MCPRequestHandler",
    "MCPSession",
    "MCPTransport",
    "MCPServerProtocol",
]
