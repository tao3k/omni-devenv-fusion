"""Unit tests for SSE transport."""

import pytest
import asyncio

from omni.mcp.transport.sse import SSESession, SSESessionManager
from omni.mcp.types import JSONRPCRequest


class TestSSESession:
    """Tests for SSESession dataclass."""

    def test_session_creation(self):
        """Test session creation with required fields."""
        session = SSESession(session_id="test-123", handler=None)
        assert session.session_id == "test-123"
        assert session.connected is True
        assert session.notification_queue is not None

    @pytest.mark.asyncio
    async def test_send_notification_queues_message(self):
        """Test that send_notification queues the message."""
        session = SSESession(session_id="test-123", handler=None)

        await session.send_notification("test/method", {"key": "value"})

        # Check that notification was queued
        assert session.notification_queue.qsize() == 1

        # Verify the queued message
        notification = await session.notification_queue.get()
        assert notification["method"] == "test/method"
        assert notification["params"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_send_notification_to_disconnected_session(self):
        """Test that notifications are skipped for disconnected sessions."""
        session = SSESession(session_id="test-123", handler=None)
        session.connected = False

        # This should not raise and should not queue anything
        await session.send_notification("test/method", {})

        assert session.notification_queue.empty()

    def test_disconnect(self):
        """Test session disconnect."""
        session = SSESession(session_id="test-123", handler=None)
        assert session.connected is True

        session.disconnect()

        assert session.connected is False


class TestSSESessionManager:
    """Tests for SSESessionManager."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        manager = SSESessionManager()

        session = await manager.create_session(handler=None)

        assert session.session_id is not None
        assert len(session.session_id) == 8  # UUID truncated

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting an existing session."""
        manager = SSESessionManager()

        created = await manager.create_session(handler=None)
        retrieved = await manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist."""
        manager = SSESessionManager()

        session = await manager.get_session("nonexistent")

        assert session is None

    @pytest.mark.asyncio
    async def test_remove_session(self):
        """Test session removal."""
        manager = SSESessionManager()

        session = await manager.create_session(handler=None)
        session_id = session.session_id

        await manager.remove_session(session_id)

        # Session should be disconnected and removed
        assert session.connected is False
        assert await manager.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_active_sessions_count(self):
        """Test counting active sessions."""
        manager = SSESessionManager()

        # Initially empty
        assert manager.active_sessions == 0

        # Add sessions
        await manager.create_session(handler=None)
        await manager.create_session(handler=None)

        assert manager.active_sessions == 2

    @pytest.mark.asyncio
    async def test_broadcast_notification(self):
        """Test broadcasting to all sessions."""
        manager = SSESessionManager()

        # Create multiple sessions
        session1 = await manager.create_session(handler=None)
        session2 = await manager.create_session(handler=None)

        # Broadcast a notification
        await manager.broadcast_notification("broadcast/test", {"broadcast": True})

        # Both sessions should receive it
        assert session1.notification_queue.qsize() == 1
        assert session2.notification_queue.qsize() == 1
