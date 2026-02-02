from typing import Any, List, Optional
import pytest
from unittest.mock import MagicMock, AsyncMock


class McpTester:
    """
    Dedicated Tester for MCP Servers.
    """

    def __init__(self):
        self.notifications: List[tuple[str, Any]] = []
        self.requests: List[Any] = []

    def make_success_response(self, id_val: Any, result: Any) -> dict:
        """Create a JSON-RPC success response."""
        return {"jsonrpc": "2.0", "id": id_val, "result": result}

    def make_error_response(self, id_val: Any, code: int, message: str) -> dict:
        """Create a JSON-RPC error response."""
        return {"jsonrpc": "2.0", "id": id_val, "error": {"code": code, "message": message}}


@pytest.fixture
def mcp_tester():
    """Fixture to provide McpTester instance."""
    return McpTester()


@pytest.fixture
def unused_port():
    """Get an available port for testing servers."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
