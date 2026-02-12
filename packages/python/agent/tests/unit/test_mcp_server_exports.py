"""Module export tests for agent.mcp_server package."""

from __future__ import annotations


def test_mcp_server_does_not_export_legacy_handle_list_tools_alias() -> None:
    import omni.agent.mcp_server as mcp_server

    assert not hasattr(mcp_server, "handle_list_tools")
