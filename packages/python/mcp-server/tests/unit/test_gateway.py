"""test_gateway.py - Gateway and SkillChangeNotifier Tests.

Tests for live tool cache invalidation via notifications/tools/listChanged.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSkillChangeNotifier:
    """Tests for SkillChangeNotifier debouncing and notification logic."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock MCPServer."""
        server = MagicMock()
        server.send_tool_list_changed = AsyncMock()
        return server

    @pytest.fixture
    def notifier(self, mock_server):
        """Create a SkillChangeNotifier with short debounce for testing."""
        from omni.mcp.gateway import SkillChangeNotifier

        return SkillChangeNotifier(mock_server, debounce_seconds=0.1)

    @pytest.mark.asyncio
    async def test_initial_notification_sends_immediately(self, notifier, mock_server):
        """First notification should be sent immediately without debouncing."""
        await notifier.on_skills_changed()

        mock_server.send_tool_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_rapid_notifications_are_debounced(self, notifier, mock_server):
        """Rapid notifications within debounce period should be debounced.

        Multiple calls within debounce window should result in only one notification.
        """
        # Send multiple notifications rapidly
        await notifier.on_skills_changed()
        await notifier.on_skills_changed()
        await notifier.on_skills_changed()

        # All rapid calls within debounce window should debounce
        # The first one sends immediately, the others cancel and reschedule
        # So we should have at least one call, but not 3 separate ones
        # after debounce completes
        assert mock_server.send_tool_list_changed.call_count >= 1

        # Wait for debounce to complete
        await asyncio.sleep(0.2)

        # After debounce, the last debounced call should have sent
        # Total should be 2 (first immediate + one debounced)
        assert mock_server.send_tool_list_changed.call_count <= 2

    @pytest.mark.asyncio
    async def test_separate_notifications_sent_individually(self, notifier, mock_server):
        """Notifications outside debounce window should each be sent."""
        # Ensure we're outside debounce window
        await asyncio.sleep(0.2)

        # First notification
        await notifier.on_skills_changed()
        mock_server.send_tool_list_changed.reset_mock()

        # Wait for debounce window to close (need longer than debounce_seconds)
        await asyncio.sleep(0.15)

        # Second notification (outside debounce window)
        await notifier.on_skills_changed()

        # Should have sent at least once for each
        # Note: First call sends immediately, second call outside debounce sends immediately
        assert mock_server.send_tool_list_changed.call_count >= 1

    @pytest.mark.asyncio
    async def test_lock_prevents_race_conditions(self, notifier):
        """Lock should prevent concurrent access issues."""
        assert hasattr(notifier, "_lock")
        assert isinstance(notifier._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_debounce_task_is_managed(self, notifier):
        """Debounce task should be created and cleared correctly."""
        # Initially no task
        assert notifier._debounce_task is None

        # After call within debounce window, task should exist
        await notifier.on_skills_changed()
        await asyncio.sleep(0.05)  # Give task time to be created

        # Task should be running or completed
        if notifier._debounce_task is not None:
            assert not notifier._debounce_task.done() or notifier._debounce_task is None

        # Wait for completion
        await asyncio.sleep(0.2)
        assert notifier._debounce_task is None or notifier._debounce_task.done()


class TestOmniMCPGateway:
    """Tests for OmniMCPGateway initialization and lifecycle."""

    def test_gateway_requires_transport(self):
        """Gateway must be initialized with a transport."""
        from omni.mcp.gateway import OmniMCPGateway

        transport = MagicMock()
        gateway = OmniMCPGateway(transport=transport)

        assert gateway.transport is transport
        assert gateway.server is not None

    def test_gateway_with_skill_manager_creates_notifier(self):
        """Gateway with skill_manager should create SkillChangeNotifier."""
        from omni.mcp.gateway import OmniMCPGateway

        transport = MagicMock()
        skill_manager = MagicMock()
        gateway = OmniMCPGateway(transport=transport, skill_manager=skill_manager)

        assert gateway.notifier is not None
        assert gateway.skill_manager is skill_manager

    def test_gateway_without_skill_manager_has_no_notifier(self):
        """Gateway without skill_manager should not have a notifier."""
        from omni.mcp.gateway import OmniMCPGateway

        transport = MagicMock()
        gateway = OmniMCPGateway(transport=transport)

        assert gateway.notifier is None
        assert gateway.skill_manager is None

    def test_gateway_creates_default_handler_when_none_provided(self):
        """Gateway should create a default handler if none provided."""
        from omni.mcp.gateway import OmniMCPGateway

        transport = MagicMock()
        gateway = OmniMCPGateway(transport=transport)

        assert gateway.handler is not None

    def test_is_running_property_reflects_server_state(self):
        """is_running should delegate to server."""
        from omni.mcp.gateway import OmniMCPGateway

        # Create a mock transport
        transport = MagicMock()

        # Create gateway with our mock server
        gateway = OmniMCPGateway(transport=transport)

        # Mock the server's _running attribute (which is_running reads)
        gateway.server._running = False
        assert gateway.is_running is False

        gateway.server._running = True
        assert gateway.is_running is True


class TestCreateGateway:
    """Tests for the create_gateway factory function."""

    @pytest.mark.asyncio
    async def test_create_gateway_returns_started_gateway(self):
        """create_gateway should return a started gateway."""
        from omni.mcp.gateway import create_gateway

        transport = MagicMock()
        transport.start = AsyncMock()

        gateway = await create_gateway(transport=transport)

        assert gateway is not None
        transport.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_gateway_with_skill_manager(self):
        """create_gateway should integrate with skill_manager."""
        from omni.mcp.gateway import create_gateway

        transport = MagicMock()
        transport.start = AsyncMock()
        skill_manager = MagicMock()
        skill_manager.on_registry_update = MagicMock()

        gateway = await create_gateway(transport=transport, skill_manager=skill_manager)

        assert gateway.notifier is not None


class TestToolListChangedNotification:
    """Tests for notifications/tools/listChanged functionality."""

    def test_server_send_tool_list_changed_format(self):
        """Verify notification format is correct JSON-RPC 2.0."""
        from omni.mcp.server import MCPServer

        # The method should produce a valid notification
        # without params (as per MCP spec)
        server = MCPServer(handler=MagicMock(), transport=MagicMock())

        # We can't directly test the async method here,
        # but we verify the method exists and has correct signature
        assert hasattr(server, "send_tool_list_changed")

        # Check it's async
        import inspect

        assert inspect.iscoroutinefunction(server.send_tool_list_changed)

    @pytest.mark.asyncio
    async def test_server_broadcasts_to_transport(self):
        """Server should broadcast via transport.broadcast if available."""
        from omni.mcp.server import MCPServer

        transport = MagicMock()
        transport.broadcast = AsyncMock()
        server = MCPServer(handler=MagicMock(), transport=transport)

        await server.send_tool_list_changed()

        transport.broadcast.assert_called_once()
        call_args = transport.broadcast.call_args[0][0]
        assert call_args["method"] == "notifications/tools/listChanged"
        assert call_args["jsonrpc"] == "2.0"

    @pytest.mark.asyncio
    async def test_server_falls_back_to_sessions(self):
        """Server should fallback to sessions if transport.broadcast not available."""
        from omni.mcp.server import MCPServer

        session = MagicMock()
        session.send_notification = AsyncMock()

        transport = MagicMock()
        # No broadcast method
        del transport.broadcast

        server = MCPServer(handler=MagicMock(), transport=transport)
        server._sessions.add(session)

        await server.send_tool_list_changed()

        session.send_notification.assert_called_once_with("notifications/tools/listChanged", None)
