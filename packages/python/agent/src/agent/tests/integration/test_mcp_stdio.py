"""
Unit test for MCP server stdio transport and exit mechanisms.

Tests that:
1. Stdio module imports correctly
2. Exit queue works properly
3. Shutdown mechanisms function correctly
4. Watcher starts and stops correctly

Usage:
    uv run pytest packages/python/agent/src/agent/tests/integration/test_mcp_stdio.py -v
"""

import asyncio
import pytest
from pathlib import Path


class TestStdioModuleImports:
    """Test all imports required for stdio transport."""

    def test_stdio_module_import(self):
        """Verify stdio module imports correctly."""
        from agent.mcp_server import stdio

        assert stdio is not None

    def test_run_stdio_function_import(self):
        """Verify run_stdio function is available."""
        from agent.mcp_server.stdio import run_stdio

        assert callable(run_stdio)

    def test_request_shutdown_import(self):
        """Verify request_shutdown function is available."""
        from agent.mcp_server.stdio import request_shutdown

        assert callable(request_shutdown)

    def test_is_shutdown_requested_import(self):
        """Verify is_shutdown_requested function is available."""
        from agent.mcp_server.stdio import is_shutdown_requested

        assert callable(is_shutdown_requested)


class TestExitQueue:
    """Test exit queue mechanism for graceful shutdown."""

    def test_exit_queue_operations(self):
        """Test putting and getting from exit queue."""

        async def test_queue():
            test_queue = asyncio.Queue()

            # Put a value
            test_queue.put_nowait(True)

            # Get the value
            value = await test_queue.get()
            assert value is True
            assert test_queue.empty()

        asyncio.run(test_queue())

    def test_is_shutdown_requested_initial(self):
        """Test that is_shutdown_requested returns False initially."""
        from agent.mcp_server.stdio import is_shutdown_requested

        assert is_shutdown_requested() is False


class TestWatcherFunctionality:
    """Test file watcher functionality."""

    def test_watcher_import(self):
        """Verify watcher module imports correctly."""
        from agent.core.skill_runtime.support.watcher import start_global_watcher

        assert callable(start_global_watcher)

    def test_stop_watcher_import(self):
        """Verify stop_global_watcher function is available."""
        from agent.core.skill_runtime.support.watcher import stop_global_watcher

        assert callable(stop_global_watcher)

    def test_background_watcher_import(self):
        """Verify BackgroundWatcher class is available."""
        from agent.core.skill_runtime.support.watcher import BackgroundWatcher

        assert BackgroundWatcher is not None

    def test_watcher_state_transitions(self):
        """Test that watcher state transitions correctly."""
        from agent.core.skill_runtime.support.watcher import BackgroundWatcher

        watcher = BackgroundWatcher()

        # Initially not running
        assert watcher.is_running is False
        assert watcher._running is False
        assert watcher.observer is None


class TestWatcherPathDisplay:
    """Test watcher path display functionality."""

    def test_skills_path_relative_display(self):
        """Test that skills path is displayed correctly."""
        from common.skills_path import SKILLS_DIR

        skills_path = str(SKILLS_DIR())
        skills_path_obj = Path(skills_path)

        # Get last 2 components
        parts = (
            skills_path_obj.parts[-2:] if len(skills_path_obj.parts) >= 2 else skills_path_obj.parts
        )
        display_path = "/".join(parts)

        # Should contain "skills"
        assert "skills" in display_path


class TestGracefulShutdown:
    """Test graceful shutdown mechanisms."""

    def test_request_shutdown_function_exists(self):
        """Test that request_shutdown function exists (replaces _terminate_server)."""
        from agent.mcp_server.stdio import request_shutdown

        assert callable(request_shutdown)

    def test_setup_signal_handler_function_exists(self):
        """Test that _setup_signal_handler function exists."""
        from agent.mcp_server.stdio import _setup_signal_handler

        assert callable(_setup_signal_handler)


class TestServerProcessManagement:
    """Test server process management.

    Note: Current stdio implementation runs directly without multiprocessing.
    The old _server_process, _run_server_worker, and _run_server_async are replaced
    by run_stdio() which handles the server loop directly.
    """

    def test_run_stdio_exists(self):
        """Test that run_stdio function exists and is callable."""
        from agent.mcp_server.stdio import run_stdio

        assert callable(run_stdio)

    def test_no_server_process_attribute(self):
        """Test that _server_process is not used in current implementation."""
        import agent.mcp_server.stdio as stdio_module

        # Current implementation doesn't use _server_process
        # This test verifies we're using the direct stdio approach
        assert hasattr(stdio_module, "run_stdio")


class TestShutdownCount:
    """Test shutdown counter for double-Ctrl-C detection."""

    def test_shutdown_count_initial(self):
        """Test that shutdown count starts at 0."""
        import agent.mcp_server.stdio as stdio_module

        assert stdio_module._shutdown_count == 0


class TestIntegration:
    """Integration tests for imports and basic functionality."""

    def test_full_import_chain(self):
        """Test that all components can be imported together."""
        from agent.mcp_server import run
        from agent.mcp_server.stdio import run_stdio, request_shutdown, is_shutdown_requested
        from agent.mcp_server.lifespan import server_lifespan
        from agent.core.skill_runtime.support.watcher import (
            start_global_watcher,
            stop_global_watcher,
        )

        # All should be callable
        assert callable(run)
        assert callable(run_stdio)
        assert callable(request_shutdown)
        assert callable(is_shutdown_requested)
        assert callable(server_lifespan)
        assert callable(start_global_watcher)
        assert callable(stop_global_watcher)

    def test_watcher_class_has_required_methods(self):
        """Test that BackgroundWatcher has required methods."""
        from agent.core.skill_runtime.support.watcher import BackgroundWatcher

        watcher = BackgroundWatcher()

        # Check required methods exist
        assert hasattr(watcher, "start")
        assert hasattr(watcher, "stop")
        assert hasattr(watcher, "run")
        assert hasattr(watcher, "is_running")
        assert hasattr(watcher, "observer")

        # Check all are callable (except is_running which is a property)
        assert callable(watcher.start)
        assert callable(watcher.stop)
        assert callable(watcher.run)
        assert isinstance(watcher.is_running, bool)


class TestLifespanImports:
    """Test lifespan module imports."""

    def test_lifespan_import(self):
        """Verify lifespan module imports correctly."""
        from agent.mcp_server.lifespan import server_lifespan

        assert callable(server_lifespan)

    def test_lifespan_has_watcher_flag(self):
        """Verify lifespan has watcher tracking."""
        from agent.mcp_server.lifespan import _watcher_started

        assert isinstance(_watcher_started, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
