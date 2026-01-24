"""Test configuration and fixtures for omni.mcp."""

import socket
from typing import Any

import pytest
from omni.mcp.types import make_success_response


@pytest.fixture
def unused_port() -> int:
    """Get an available port for testing servers."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url(unused_port: int) -> str:
    """Generate a server URL for testing."""
    return f"http://127.0.0.1:{unused_port}"


class MockRequestHandler:
    """Mock MCP request handler for testing."""

    def __init__(self):
        self.notifications: list[tuple[str, Any]] = []
        self.requests: list[Any] = []
        self.initialized = False

    async def handle_request(self, request: Any) -> Any:
        """Handle a JSON-RPC request."""
        self.requests.append(request)
        return make_success_response(id=request.id, result={"success": True})

    async def handle_notification(self, method: str, params: Any) -> None:
        """Handle a JSON-RPC notification."""
        self.notifications.append((method, params))

    async def initialize(self) -> None:
        """Handle MCP initialization."""
        self.initialized = True


@pytest.fixture
def mock_handler() -> MockRequestHandler:
    """Create a mock request handler."""
    return MockRequestHandler()
