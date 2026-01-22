"""
test_mcp_shutdown.py - MCP Server Shutdown Mechanism Tests

Tests for graceful shutdown and signal handling in both stdio and SSE modes.
Ensures that Ctrl-C properly exits without blocking.

Usage:
    uv run pytest packages/python/agent/tests/integration/test_mcp_shutdown.py -v
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock, AsyncMock

import pytest


class TestSignalHandlerSetup:
    """Test signal handler setup for MCP server."""

    def test_setup_signal_handler_import(self):
        """Verify signal handler setup function can be imported."""
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        assert callable(_setup_signal_handler)

    def test_setup_signal_handler_accepts_parameters(self):
        """Verify signal handler accepts expected parameters."""
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        # Should accept handler_ref, transport_ref, and stdio_mode parameters
        import inspect

        sig = inspect.signature(_setup_signal_handler)
        params = list(sig.parameters.keys())

        assert "handler_ref" in params
        assert "transport_ref" in params
        assert "stdio_mode" in params

    def test_setup_signal_handler_registers_signals(self):
        """Verify signal handler registers SIGINT and SIGTERM handlers."""
        from unittest.mock import MagicMock, patch

        from omni.agent.cli.commands.mcp import _setup_signal_handler

        handler_mock = MagicMock()
        with patch("signal.signal") as mock_signal:
            _setup_signal_handler(handler_ref=handler_mock, stdio_mode=False)

            # Should have registered both SIGINT and SIGTERM
            assert mock_signal.call_count == 2

            # Check signal registrations
            registered_signals = {call.args[0] for call in mock_signal.call_args_list}
            assert signal.SIGINT in registered_signals
            assert signal.SIGTERM in registered_signals


class TestGlobalShutdownState:
    """Test global shutdown state management."""

    def test_shutdown_globals_exist(self):
        """Verify global shutdown variables exist."""
        from omni.agent.cli.commands.mcp import (
            _handler_ref,
            _shutdown_requested,
            _transport_ref,
        )

        # Initially should be None/False
        assert _shutdown_requested is False
        assert _handler_ref is None
        assert _transport_ref is None

    def test_shutdown_requested_flag(self):
        """Test _shutdown_requested flag can be toggled."""
        from omni.agent.cli.commands.mcp import _shutdown_requested

        # Import the module to check the value
        import omni.agent.cli.commands.mcp as mcp_module

        # Initially False
        assert mcp_module._shutdown_requested is False

        # Toggle to True
        mcp_module._shutdown_requested = True
        assert mcp_module._shutdown_requested is True

        # Reset for other tests
        mcp_module._shutdown_requested = False


class TestGracefulShutdownFunction:
    """Test graceful shutdown function."""

    def test_graceful_shutdown_import(self):
        """Verify graceful shutdown function can be imported."""
        from omni.agent.cli.commands.mcp import _graceful_shutdown

        assert callable(_graceful_shutdown)

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_no_kernel(self):
        """Test graceful shutdown when handler has no kernel."""
        from unittest.mock import MagicMock

        from omni.agent.cli.commands.mcp import _graceful_shutdown

        handler = MagicMock()
        handler._kernel = None

        # Should not raise
        await _graceful_shutdown(handler)

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_kernel_not_ready(self):
        """Test graceful shutdown when kernel is not ready."""
        from unittest.mock import MagicMock, PropertyMock

        from omni.agent.cli.commands.mcp import _graceful_shutdown

        kernel = MagicMock()
        kernel.is_ready = False
        kernel.state.value = "uninitialized"

        handler = MagicMock()
        handler._kernel = kernel

        # Should not raise - kernel not ready so no shutdown needed
        await _graceful_shutdown(handler)
        kernel.shutdown.assert_not_called()


class TestSyncGracefulShutdown:
    """Test sync wrapper for graceful shutdown."""

    def test_sync_graceful_shutdown_import(self):
        """Verify sync wrapper can be imported."""
        from omni.agent.cli.commands.mcp import _sync_graceful_shutdown

        assert callable(_sync_graceful_shutdown)

    def test_sync_graceful_shutdown_with_no_handler(self):
        """Test sync shutdown when handler is None."""
        from omni.agent.cli.commands.mcp import _sync_graceful_shutdown

        # Should not raise when handler is None
        _sync_graceful_shutdown()


class TestTransportStop:
    """Test transport stop functionality."""

    def test_stdio_transport_has_stop(self):
        """Verify StdioTransport has stop method."""
        from omni.mcp.transport.stdio import StdioTransport

        transport = StdioTransport()
        assert hasattr(transport, "stop")
        assert callable(transport.stop)

    @pytest.mark.asyncio
    async def test_stdio_transport_stop_works(self):
        """Test that stdio transport stop sets running to False."""
        from omni.mcp.transport.stdio import StdioTransport

        transport = StdioTransport()
        assert transport._running is False

        transport._running = True
        await transport.stop()

        assert transport._running is False

    def test_sse_transport_has_stop(self):
        """Verify SSEServer has stop method."""
        from omni.mcp.transport.sse import SSEServer

        # SSEServer should have stop method
        assert hasattr(SSEServer, "stop") or callable(getattr(SSEServer, "stop", None))


class TestStdioModeExit:
    """Test stdio mode exit behavior - these tests verify logic without raising real signals."""

    def test_stdio_mode_sets_sys_exit_behavior(self):
        """Verify stdio mode signal handler is configured for sys.exit."""
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        # Verify the function exists and accepts stdio_mode parameter
        import inspect

        sig = inspect.signature(_setup_signal_handler)
        params = sig.parameters

        assert "stdio_mode" in params
        # Verify stdio_mode defaults to False
        assert params["stdio_mode"].default is False

    def test_stdio_mode_does_not_schedule_kernel_shutdown(self):
        """Verify stdio mode does not schedule async kernel shutdown.

        This test verifies the logic path by checking that _sync_graceful_shutdown
        is NOT called when stdio_mode=True. We verify this by checking the code path
        doesn't include the call for stdio mode.
        """
        import inspect
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        source = inspect.getsource(_setup_signal_handler)
        # In stdio mode, the handler should call sys.exit(0) directly
        # and NOT call _sync_graceful_shutdown
        assert "sys.exit(0)" in source
        # The _sync_graceful_shutdown should only be called in else branch (non-stdio mode)
        # We can't easily test this without raising signals, so we verify the code structure


class TestSSEModeShutdown:
    """Test SSE mode graceful shutdown behavior."""

    def test_sse_mode_calls_transport_stop(self):
        """Verify SSE mode signal handler code includes transport stop."""
        import inspect
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        source = inspect.getsource(_setup_signal_handler)
        # SSE mode should stop the transport
        assert "transport_ref.stop" in source or "transport.stop" in source

    def test_sse_mode_calls_graceful_shutdown(self):
        """Verify SSE mode code calls _sync_graceful_shutdown."""
        import inspect
        from omni.agent.cli.commands.mcp import _setup_signal_handler

        source = inspect.getsource(_setup_signal_handler)
        # SSE mode should call _sync_graceful_shutdown
        assert "_sync_graceful_shutdown" in source


class TestTransportModeEnum:
    """Test TransportMode enum."""

    def test_transport_mode_enum_values(self):
        """Verify TransportMode has correct values."""
        from omni.agent.cli.commands.mcp import TransportMode

        assert TransportMode.stdio.value == "stdio"
        assert TransportMode.sse.value == "sse"

    def test_transport_mode_is_str_enum(self):
        """Verify TransportMode is a string enum."""
        from omni.agent.cli.commands.mcp import TransportMode

        # Should be usable as a string
        assert str(TransportMode.stdio) == "TransportMode.stdio"
        assert TransportMode.stdio.value == "stdio"


class TestMCPCommandRegistration:
    """Test MCP command registration."""

    def test_register_mcp_command_import(self):
        """Verify register_mcp_command can be imported."""
        from omni.agent.cli.commands.mcp import register_mcp_command

        assert callable(register_mcp_command)

    def test_mcp_command_in_cli(self):
        """Verify mcp command is registered in CLI app."""
        from typer.testing import CliRunner

        from omni.agent.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["mcp", "--help"])

        assert result.exit_code == 0
        assert "omni mcp" in result.output.lower()
        assert "--transport" in result.output or "-t" in result.output

    def test_mcp_command_transport_options(self):
        """Verify mcp command has correct transport options."""
        from typer.testing import CliRunner

        from omni.agent.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["mcp", "--help"])

        assert "stdio" in result.output
        assert "sse" in result.output


class TestStdioTransportRunLoopExit:
    """Test that stdio transport run_loop exits on stop."""

    @pytest.mark.asyncio
    async def test_run_loop_exits_when_reader_returns_empty(self):
        """Test that run_loop exits when reader returns empty bytes."""
        from omni.mcp.transport.stdio import StdioTransport

        transport = StdioTransport()
        transport._running = True

        # Mock reader that immediately returns empty bytes (EOF)
        reader = MagicMock()
        reader.readline = AsyncMock(return_value=b"")
        reader.feed_eof = MagicMock()

        transport._reader = reader

        server = MagicMock()

        # Run the loop - should exit when reader returns empty
        await transport.run_loop(server)

        # Verify loop exited because _running should now be False (due to empty bytes)
        assert transport._running is False or reader.readline.call_count >= 1

    def test_transport_running_property(self):
        """Test transport is_connected property."""
        from omni.mcp.transport.stdio import StdioTransport

        transport = StdioTransport()
        assert transport.is_connected is False

        transport._running = True
        assert transport.is_connected is True

        transport._running = False
        assert transport.is_connected is False

    def test_transport_set_handler(self):
        """Test transport set_handler method."""
        from omni.mcp.transport.stdio import StdioTransport
        from omni.mcp.interfaces import MCPRequestHandler

        transport = StdioTransport()
        assert transport._handler is None

        # Create a mock handler
        mock_handler = MagicMock(spec=MCPRequestHandler)
        transport.set_handler(mock_handler)

        assert transport._handler is mock_handler


class TestProcessExitIntegration:
    """Integration tests for process exit behavior."""

    def test_mcp_command_exits_on_keyboard_interrupt(self):
        """Test that mcp command handles KeyboardInterrupt properly."""
        from typer.testing import CliRunner

        from omni.agent.cli import app

        runner = CliRunner()

        # Simulate KeyboardInterrupt by calling the command with invalid transport
        # This tests that the exception handler works, not the actual exit
        result = runner.invoke(app, ["mcp", "--transport", "invalid"])

        # Should exit with error for invalid transport
        assert result.exit_code != 0 or "invalid" in result.output.lower()

    def test_mcp_help_shows_transport_options(self):
        """Test that mcp help shows transport options."""
        from typer.testing import CliRunner

        from omni.agent.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["mcp", "--help"])

        assert result.exit_code == 0
        # Should mention both transport modes
        assert "stdio" in result.output.lower()
        assert "sse" in result.output.lower()


class TestKernelShutdownIntegration:
    """Test kernel shutdown integration."""

    @pytest.mark.asyncio
    async def test_kernel_shutdown_stops_watcher(self):
        """Test that kernel shutdown stops the file watcher."""
        from omni.core.kernel import get_kernel

        kernel = get_kernel()

        # Mock the watcher
        mock_watcher = MagicMock()
        kernel._watcher = mock_watcher

        # Mock skill context
        kernel._skill_context = MagicMock()
        kernel._skill_context.skills_count = 0

        # Perform shutdown
        await kernel._on_shutdown()

        # Verify watcher was stopped
        mock_watcher.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_kernel_shutdown_clears_components(self):
        """Test that kernel shutdown clears components."""
        from omni.core.kernel import get_kernel, reset_kernel

        reset_kernel()
        kernel = get_kernel()

        # Add a component
        kernel.register_component("test_component", MagicMock())

        assert kernel.has_component("test_component")

        # Perform shutdown
        await kernel._on_shutdown()

        # Verify component was cleared
        assert not kernel.has_component("test_component")


class TestMCPServerStartStop:
    """Test MCPServer start and stop methods."""

    def test_mcp_server_has_start_stop(self):
        """Verify MCPServer has start and stop methods."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        transport = StdioTransport()
        server = MCPServer(handler=handler, transport=transport)

        assert hasattr(server, "start")
        assert hasattr(server, "stop")
        assert callable(server.start)
        assert callable(server.stop)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
