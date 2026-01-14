"""
Mock Fixtures

Mock objects for testing without external dependencies.
Loaded automatically as pytest plugins.

Fixtures:
    - mock_mcp_server: Mock MCP FastMCP server
    - mock_inference: Mock inference client
    - real_mcp: Simple mock MCP server
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def fixtures_mocks_mock_mcp_server():
    """Create a mock MCP FastMCP server."""
    mock = MagicMock()
    mock.list_tools = AsyncMock(return_value=[])
    mock.list_prompts = AsyncMock(return_value=[])
    mock.list_resources = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def fixtures_mocks_mock_inference():
    """Create a mock inference client."""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Mocked inference response")
    return mock


@pytest.fixture
def fixtures_mocks_real_mcp():
    """Create a mock MCP server for registry tests."""
    return MagicMock()
