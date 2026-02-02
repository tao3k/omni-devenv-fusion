"""
Tests for the TUI Bridge module with reverse connection architecture.
"""

import asyncio
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.agent.cli.tui_bridge import (
    TUIManager,
    TUIConfig,
    TUIBridgeProtocol,
    NullTUIBridge,
    create_tui_bridge,
    get_env_bool,
)


class MockStreamWriter:
    """Mock asyncio StreamWriter to avoid RuntimeWarnings."""

    def __init__(self):
        self.data = []
        self._closed = False
        self._close_called = False

    def write(self, data):
        """Write is not a coroutine, returns None."""
        self.data.append(data)

    def close(self):
        """Close is NOT a coroutine - called synchronously in cleanup."""
        self._close_called = True
        self._closed = True

    async def drain(self):
        """Drain is a coroutine."""
        pass

    async def wait_closed(self):
        """Wait closed is a coroutine."""
        pass

    @property
    def closed(self):
        return self._closed


class TestGetEnvBool:
    """Test environment variable boolean parsing."""

    def test_default_value(self):
        """Returns default when env var not set."""
        assert get_env_bool("NONEXISTENT", True) is True
        assert get_env_bool("NONEXISTENT", False) is False

    def test_positive_values(self):
        """Positive values return True."""
        assert get_env_bool("VAR", True) is True
        with patch.dict(os.environ, {"VAR": "1"}):
            assert get_env_bool("VAR", False) is True
        with patch.dict(os.environ, {"VAR": "true"}):
            assert get_env_bool("VAR", False) is True
        with patch.dict(os.environ, {"VAR": "yes"}):
            assert get_env_bool("VAR", False) is True
        with patch.dict(os.environ, {"VAR": "on"}):
            assert get_env_bool("VAR", False) is True

    def test_negative_values(self):
        """Negative values return False."""
        with patch.dict(os.environ, {"VAR": "0"}):
            assert get_env_bool("VAR", True) is False
        with patch.dict(os.environ, {"VAR": "false"}):
            assert get_env_bool("VAR", True) is False
        with patch.dict(os.environ, {"VAR": "no"}):
            assert get_env_bool("VAR", True) is False
        with patch.dict(os.environ, {"VAR": "off"}):
            assert get_env_bool("VAR", True) is False


class TestTUIConfig:
    """Test TUI configuration."""

    def test_default_values(self):
        """Default config has sensible values."""
        config = TUIConfig()
        assert config.enabled is True
        assert config.connect_timeout == 5.0
        assert config.theme == "dark"
        # UUID-based socket path
        assert config.socket_path.startswith("/tmp/omni_tui_")

    def test_custom_values(self):
        """Custom config overrides defaults."""
        config = TUIConfig(
            enabled=False,
            connect_timeout=10.0,
            socket_path="/tmp/custom.sock",
            theme="light",
        )
        assert config.enabled is False
        assert config.connect_timeout == 10.0
        assert config.socket_path == "/tmp/custom.sock"
        assert config.theme == "light"


class TestNullTUIBridge:
    """Test NullTUIBridge for non-interactive environments."""

    def test_null_bridge_is_inactive(self):
        """NullTUIBridge is always inactive."""
        bridge = NullTUIBridge()
        assert bridge.is_active is False

    @pytest.mark.asyncio
    async def test_null_bridge_noops_events(self):
        """NullTUIBridge silently drops events."""
        bridge = NullTUIBridge()
        await bridge.send_event("test/topic", {"data": "value"})
        await bridge.send_log("info", "test message")


class TestTUIManagerEnvironmentDetection:
    """Test TUI environment detection."""

    def test_disabled_by_config(self):
        """TUI can be disabled via config."""
        manager = TUIManager(TUIConfig(enabled=False))
        with patch("sys.stdout.isatty", return_value=True):
            assert manager.should_enable() is False

    def test_disabled_without_tty(self):
        """TUI is disabled without TTY."""
        manager = TUIManager(TUIConfig(enabled=True))
        with patch("sys.stdout.isatty", return_value=False):
            assert manager.should_enable() is False

    def test_disabled_in_mcp_mode(self):
        """TUI is disabled in MCP mode."""
        manager = TUIManager(TUIConfig(enabled=True))
        with patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {"OMNI_MODE": "mcp"}):
                assert manager.should_enable() is False

    def test_disabled_in_headless_mode(self):
        """TUI is disabled in headless mode."""
        manager = TUIManager(TUIConfig(enabled=True))
        with patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {"OMNI_MODE": "headless"}):
                assert manager.should_enable() is False

    def test_disabled_with_no_tui_env(self):
        """TUI is disabled with NO_TUI env var."""
        manager = TUIManager(TUIConfig(enabled=True))
        with patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {"NO_TUI": "1"}):
                assert manager.should_enable() is False

    @pytest.mark.asyncio
    async def test_enabled_in_interactive_mode(self):
        """TUI is enabled in interactive terminal."""
        manager = TUIManager(TUIConfig(enabled=True))
        with patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                assert manager.should_enable() is True


class TestTUIManagerLifecycle:
    """Test TUI lifecycle management with reverse connection."""

    @pytest.mark.asyncio
    async def test_disabled_uses_null_bridge(self):
        """Disabled TUI returns NullTUIBridge."""
        manager = TUIManager(TUIConfig(enabled=False))

        async with manager.lifecycle() as bridge:
            assert isinstance(bridge, NullTUIBridge)
            assert bridge.is_active is False

    @pytest.mark.asyncio
    async def test_lifecycle_yields_self_when_enabled(self):
        """Enabled TUI yields itself during lifecycle."""
        manager = TUIManager(TUIConfig(enabled=True, socket_path="/tmp/test.sock"))

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_server_socket = MagicMock()
        mock_conn = MagicMock()

        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("socket.socket", return_value=mock_server_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Track time for timeout logic
            time_values = [0.0, 0.1, 0.2]
            time_iter = iter(time_values)
            mock_loop_instance.time = MagicMock(side_effect=lambda: next(time_iter))

            # Mock sock_accept to succeed on first call
            async def mock_accept(*args, **kwargs):
                return (mock_conn, None)

            mock_loop_instance.sock_accept = AsyncMock(side_effect=mock_accept)

            # Mock sock_sendall as async
            mock_loop_instance.sock_sendall = AsyncMock()

            async with manager.lifecycle() as tui:
                assert tui is manager
                assert tui.is_active is True

            # Verify cleanup
            assert manager.is_active is False
            mock_proc.terminate.assert_called()

    @pytest.mark.asyncio
    async def test_process_spawned_with_correct_args(self):
        """TUI process is spawned with correct arguments."""
        manager = TUIManager(TUIConfig(enabled=True, socket_path="/tmp/test.sock"))

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_server_socket = MagicMock()
        mock_conn = MagicMock()

        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("socket.socket", return_value=mock_server_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Track time for timeout logic
            time_values = [0.0, 0.1]
            time_iter = iter(time_values)
            mock_loop_instance.time = MagicMock(side_effect=lambda: next(time_iter))

            async def mock_accept(*args, **kwargs):
                return (mock_conn, None)

            mock_loop_instance.sock_accept = AsyncMock(side_effect=mock_accept)

            async with manager.lifecycle():
                pass

            # Verify subprocess was called with correct args
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert "omni-tui" in args[0]
            assert "--socket" in args
            assert "/tmp/test.sock" in args
            assert "--role" in args
            assert "client" in args

    @pytest.mark.asyncio
    async def test_event_emission(self):
        """Events are sent to the TUI socket."""
        manager = TUIManager(TUIConfig(enabled=True, socket_path="/tmp/test.sock"))

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_server_socket = MagicMock()
        mock_conn = MagicMock()

        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc),
            patch("socket.socket", return_value=mock_server_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Track time for timeout logic
            time_values = [0.0, 0.1]
            time_iter = iter(time_values)
            mock_loop_instance.time = MagicMock(side_effect=lambda: next(time_iter))

            async def mock_accept(*args, **kwargs):
                return (mock_conn, None)

            mock_loop_instance.sock_accept = AsyncMock(side_effect=mock_accept)

            # Mock sock_sendall as async
            mock_loop_instance.sock_sendall = AsyncMock()

            async with manager.lifecycle() as tui:
                await tui.send_event("test/topic", {"foo": "bar"})

                # Verify sock_sendall was called
                mock_loop_instance.sock_sendall.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_on_exit(self):
        """Cleanup is called on context exit."""
        manager = TUIManager(TUIConfig(enabled=True, socket_path="/tmp/test.sock"))

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_server_socket = MagicMock()
        mock_conn = MagicMock()

        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc),
            patch("socket.socket", return_value=mock_server_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Track time for timeout logic
            time_values = [0.0, 0.1]
            time_iter = iter(time_values)
            mock_loop_instance.time = MagicMock(side_effect=lambda: next(time_iter))

            async def mock_accept(*args, **kwargs):
                return (mock_conn, None)

            mock_loop_instance.sock_accept = AsyncMock(side_effect=mock_accept)

            # Mock sock_sendall as async
            mock_loop_instance.sock_sendall = AsyncMock()

            async with manager.lifecycle() as tui:
                assert tui.is_active is True

            # Verify cleanup
            assert manager.is_active is False
            mock_conn.close.assert_called()
            mock_server_socket.close.assert_called()
            mock_proc.terminate.assert_called()


class TestConcurrentEventEmission:
    """Test concurrent event emission."""

    @pytest.mark.asyncio
    async def test_rapid_event_sequence(self):
        """Many events can be sent rapidly."""
        manager = TUIManager(TUIConfig(enabled=True, socket_path="/tmp/test.sock"))

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        mock_server_socket = MagicMock()
        mock_conn = MagicMock()

        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc),
            patch("socket.socket", return_value=mock_server_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Track time for timeout logic
            time_values = [0.0, 0.1]
            time_iter = iter(time_values)
            mock_loop_instance.time = MagicMock(side_effect=lambda: next(time_iter))

            async def mock_accept(*args, **kwargs):
                return (mock_conn, None)

            mock_loop_instance.sock_accept = AsyncMock(side_effect=mock_accept)

            # Mock sock_sendall as async
            mock_loop_instance.sock_sendall = AsyncMock()

            async with manager.lifecycle() as tui:
                # Send many events rapidly
                for i in range(100):
                    await tui.send_event(f"task/{i}", {"index": i})

                # All sends should have been attempted (100 + 1 for handshake)
                assert mock_loop_instance.sock_sendall.call_count == 101


class TestCreateTUIBridge:
    """Test TUI bridge factory function."""

    def test_creates_null_bridge_when_disabled(self):
        """create_tui_bridge returns NullTUIBridge when disabled."""
        with patch("sys.stdout.isatty", return_value=False):
            bridge = create_tui_bridge()
            assert isinstance(bridge, NullTUIBridge)
            assert bridge.is_active is False

    def test_creates_manager_when_enabled(self):
        """create_tui_bridge returns TUIManager when enabled."""
        with patch("sys.stdout.isatty", return_value=True):
            bridge = create_tui_bridge()
            assert isinstance(bridge, TUIManager)
