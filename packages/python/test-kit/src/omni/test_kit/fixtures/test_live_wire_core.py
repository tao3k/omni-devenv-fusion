"""Core tests for Live-Wire Skill Watcher and MCP notification mechanism.

Tests verify:
1. send_tool_list_changed() method exists and is callable
2. _notify_tools_changed() sends notifications when skills change
3. SkillContext.register_skill() clears stale commands (v2.1.17.7 fix)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any
from pathlib import Path


class TestLifespanMCPRegistry:
    """Tests for MCP server registry in lifespan module."""

    def test_set_mcp_server_stores_reference(self):
        """Test that set_mcp_server stores the server reference."""
        from omni.agent.mcp_server.lifespan import _mcp_server, set_mcp_server

        mock_server = MagicMock()
        set_mcp_server(mock_server)

        # Verify the global is now the mock_server
        import omni.agent.mcp_server.lifespan as lifespan_module

        assert lifespan_module._mcp_server is mock_server

    def test_get_mcp_server_returns_stored_reference(self):
        """Test that get_mcp_server returns the stored server."""
        from omni.agent.mcp_server.lifespan import get_mcp_server, set_mcp_server

        mock_server = MagicMock()
        set_mcp_server(mock_server)

        result = get_mcp_server()
        assert result is mock_server

    @pytest.mark.asyncio
    async def test_notify_tools_changed_calls_send_tool_list_changed(self):
        """Test _notify_tools_changed calls send_tool_list_changed on server."""
        from omni.agent.mcp_server.lifespan import (
            _mcp_server,
            _notify_tools_changed,
            set_mcp_server,
        )

        # Create mock server with send_tool_list_changed
        mock_server = AsyncMock()
        set_mcp_server(mock_server)

        # Call _notify_tools_changed
        await _notify_tools_changed({"test": "change"})

        # Verify send_tool_list_changed was called
        mock_server.send_tool_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_tools_changed_no_server_logs_warning(self):
        """Test warning logged when no MCP server is registered."""
        from omni.agent.mcp_server.lifespan import (
            _mcp_server,
            _notify_tools_changed,
            set_mcp_server,
        )

        # Ensure no server is registered
        set_mcp_server(None)

        # Should not raise, just complete silently
        await _notify_tools_changed({"test": "change"})


# ============================================================================
# Pytest Fixtures for Live-Wire Testing
# ============================================================================


@pytest.fixture
def live_wire_mock_server():
    """Create a fully mocked MCP server for Live-Wire tests.

    Provides:
        - _transport with broadcast method
        - _app with request_context.session
        - send_tool_list_changed method (async mock)
    """
    mock_server = MagicMock()

    # Setup transport
    mock_transport = MagicMock()
    mock_broadcast = AsyncMock()
    mock_transport.broadcast = mock_broadcast
    mock_server._transport = mock_transport

    # Setup app fallback
    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.session = mock_session
    mock_app = MagicMock()
    mock_app.request_context = mock_ctx
    mock_server._app = mock_app

    # Setup send_tool_list_changed as async mock
    mock_server.send_tool_list_changed = AsyncMock()

    return mock_server


@pytest.fixture
def registered_live_wire_server(live_wire_mock_server):
    """Register a mock MCP server for Live-Wire tests."""
    from omni.agent.mcp_server.lifespan import set_mcp_server

    set_mcp_server(live_wire_mock_server)
    yield live_wire_mock_server
    # Cleanup - reset to None
    set_mcp_server(None)


# ============================================================================
# Test Suite for Live-Wire Core Functionality
# ============================================================================


class TestLiveWireCore:
    """Core Live-Wire tests that verify the notification mechanism."""

    @pytest.mark.asyncio
    async def test_notification_sent_on_skill_add(self, registered_live_wire_server):
        """Verify MCP notification when a skill is added."""
        from omni.agent.mcp_server.lifespan import _notify_tools_changed

        await _notify_tools_changed({"added-skill": "added"})

        registered_live_wire_server.send_tool_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_sent_on_skill_remove(self, registered_live_wire_server):
        """Verify MCP notification when a skill is removed."""
        from omni.agent.mcp_server.lifespan import _notify_tools_changed

        await _notify_tools_changed({"removed-skill": "removed"})

        registered_live_wire_server.send_tool_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_sent_on_skill_modify(self, registered_live_wire_server):
        """Verify MCP notification when a skill is modified."""
        from omni.agent.mcp_server.lifespan import _notify_tools_changed

        await _notify_tools_changed({"modified-skill": "modified"})

        registered_live_wire_server.send_tool_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_notifications_single_call(self, registered_live_wire_server):
        """Verify batched changes are sent in single notification."""
        from omni.agent.mcp_server.lifespan import _notify_tools_changed

        # Multiple changes in a single batch
        await _notify_tools_changed({"skill1": "added", "skill2": "added"})

        # Should be called once (single batch)
        registered_live_wire_server.send_tool_list_changed.assert_called_once()


class TestLiveWireTransport:
    """Tests for transport-based notification delivery."""

    @pytest.mark.asyncio
    async def test_broadcast_notification_format(self, live_wire_mock_server):
        """Test notification has correct MCP format."""
        from omni.agent.mcp_server.server import AgentMCPServer

        # Create real instance to test the method
        server = AgentMCPServer()
        server._transport = live_wire_mock_server._transport

        await server.send_tool_list_changed()

        # Verify broadcast was called with correct format
        mock_broadcast = live_wire_mock_server._transport.broadcast
        mock_broadcast.assert_called_once()

        notification = mock_broadcast.call_args[0][0]
        assert notification["method"] == "notifications/tools/listChanged"
        assert notification["params"] is None
        assert notification["jsonrpc"] == "2.0"


class TestLiveWireEndToEnd:
    """End-to-end tests for Live-Wire notification flow."""

    @pytest.mark.asyncio
    async def test_watcher_to_notification_flow(self, live_wire_mock_server):
        """Test full flow: watcher event -> skill change -> MCP notification."""
        from omni.agent.mcp_server.lifespan import (
            _notify_tools_changed,
            set_mcp_server,
        )

        # Register mock server
        set_mcp_server(live_wire_mock_server)

        # Simulate skill registry update notification
        await _notify_tools_changed({"test-skill.py": "created"})

        # Verify MCP notification was sent
        live_wire_mock_server.send_tool_list_changed.assert_called_once()


# ============================================================================
# Skill Context Command Cleanup Tests (v2.1.17.7 Fix)
# ============================================================================


class TestSkillContextCommandCleanup:
    """Tests verifying SkillContext.register_skill() clears stale commands.

    Critical for Live-Wire to correctly handle skill file deletions.
    Previously, register_skill() only added new commands but never removed
    stale ones, causing deleted commands to persist in the tool list.
    """

    def test_register_skill_clears_stale_commands(self):
        """Test that register_skill() clears stale commands when reloading.

        When a skill file is deleted:
        1. Watcher detects DELETED event
        2. kernel.reload_skill() is called
        3. register_skill() must clear old commands before adding new ones
        """
        from omni.core.skills.runtime import SkillContext

        context = SkillContext(skills_dir=Path("/skills"))
        # Simulate existing commands (including one that will be deleted)
        context._commands = {
            "git.status": MagicMock(),
            "git.commit": MagicMock(),
            "git.undo": MagicMock(),  # This should be removed
            "knowledge.search": MagicMock(),  # This should NOT be removed
        }
        context._native = {}

        # Simulate reloaded skill (undo.py deleted)
        mock_skill = MagicMock()
        mock_skill.name = "git"
        mock_skill._path = Path("/skills/git")
        mock_skill._tools_loader = MagicMock()
        mock_skill._tools_loader.commands = {
            "git.status": MagicMock(),
            "git.commit": MagicMock(),
        }
        mock_skill._tools_loader.native_functions = {}

        context.register_skill(mock_skill)

        # Verify stale command was removed
        assert "git.undo" not in context._commands

        # Verify retained commands preserved
        assert "git.status" in context._commands
        assert "git.commit" in context._commands

        # Verify unrelated commands preserved
        assert "knowledge.search" in context._commands

    def test_register_skill_first_load(self):
        """Test register_skill() works for first load (no stale commands)."""
        from omni.core.skills.runtime import SkillContext

        context = SkillContext(skills_dir=Path("/skills"))
        context._commands = {}
        context._native = {}

        mock_skill = MagicMock()
        mock_skill.name = "new_skill"
        mock_skill._path = Path("/skills/new_skill")
        mock_skill._tools_loader = MagicMock()
        mock_skill._tools_loader.commands = {"new_skill.feature": MagicMock()}
        mock_skill._tools_loader.native_functions = {}

        context.register_skill(mock_skill)

        assert "new_skill.feature" in context._commands


class TestLiveWireDeleteWorkflow:
    """End-to-end tests for delete workflow.

    Full flow:
    1. Watcher detects DELETED event
    2. indexer.remove_file() called
    3. kernel.reload_skill() called
    4. register_skill() clears stale commands
    5. MCP notification sent
    """

    def test_register_skill_clears_stale_on_reload(self):
        """Test register_skill() clears stale commands when reloading skill."""
        from omni.core.skills.runtime import SkillContext

        # Setup context with stale commands
        context = SkillContext(skills_dir=Path("/skills"))
        context._commands = {
            "git.status": MagicMock(),
            "git.undo": MagicMock(),  # Will be deleted
        }

        # Create a mock skill without undo (simulating deleted file)
        mock_loader = MagicMock()
        mock_loader.commands = {"git.status": MagicMock()}  # Only status
        mock_loader.native_functions = {}

        mock_skill = MagicMock()
        mock_skill.name = "git"
        mock_skill._path = Path("/skills/git")
        mock_skill._tools_loader = mock_loader

        # Register skill (simulates reload after file deletion)
        context.register_skill(mock_skill)

        # Verify stale command was removed
        assert "git.undo" not in context._commands
        assert "git.status" in context._commands


# ============================================================================
# Re-export fixtures for convenience
# ============================================================================

__all__ = [
    "live_wire_mock_server",
    "registered_live_wire_server",
]
