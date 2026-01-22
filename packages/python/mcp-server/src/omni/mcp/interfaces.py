"""
Protocol Interfaces

Dependency inversion: MCP server only talks to these interfaces.
Business layer (Agent) implements them.
"""

from typing import Protocol, Any, Optional, runtime_checkable
from .types import JSONRPCRequest, JSONRPCResponse


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

    async def handle_notification(self, method: str, params: Optional[Any]) -> None:
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

    async def send_notification(self, method: str, params: Optional[Any] = None) -> None:
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
    def session(self) -> Optional[MCPSession]:
        """Get the current session."""
        ...

    async def send_notification(self, method: str, params: Optional[Any] = None) -> None:
        """Send notification to the client that initiated this request."""
        ...


__all__ = [
    "MCPRequestHandler",
    "MCPTransport",
    "MCPSession",
    "MCPRequestContext",
]
