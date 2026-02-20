from unittest.mock import AsyncMock, patch

import pytest

from omni.agent.mcp_server import lifespan


@pytest.mark.asyncio
async def test_notify_tools_changed_skips_warning_without_server() -> None:
    """No warning should be emitted when running outside MCP server context."""
    lifespan.set_mcp_server(None)

    with patch.object(lifespan, "log") as mock_log:
        await lifespan._notify_tools_changed({"knowledge": "modified"})

    mock_log.warning.assert_not_called()
    mock_log.debug.assert_called_once()
    message = mock_log.debug.call_args[0][0]
    assert "Skipping Live-Wire tool notification" in message


@pytest.mark.asyncio
async def test_notify_tools_changed_uses_registered_server() -> None:
    """When server is registered, listChanged notification should be sent."""
    mock_server = AsyncMock()
    lifespan.set_mcp_server(mock_server)

    try:
        await lifespan._notify_tools_changed({"knowledge": "modified"})
    finally:
        lifespan.set_mcp_server(None)

    mock_server.send_tool_list_changed.assert_called_once()
