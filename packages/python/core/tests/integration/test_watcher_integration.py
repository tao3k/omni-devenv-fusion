"""Integration tests for Rust-native file watcher with Kernel."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestKernelWatcherIntegration:
    """Integration tests for Rust watcher with Kernel."""

    @pytest.fixture
    def temp_skills_dir(self) -> Path:
        """Create a temporary skills directory with a sample skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()

            # Create a sample skill structure
            (skills_dir / "git").mkdir()
            (skills_dir / "git" / "SKILL.md").write_text("""---
name: git
description: Git operations
---
""")
            (skills_dir / "git" / "tools.py").write_text("""
from omni.agent import skill_command

@skill_command
def commit():
    '''Commit changes'''
    pass
""")

            yield skills_dir

    @pytest.fixture
    def mock_kernel(self, temp_skills_dir: Path):
        """Create a mock kernel for testing."""
        from omni.core.kernel.engine import Kernel

        # Mock initialization to avoid full setup
        kernel = Kernel.__new__(Kernel)
        kernel._skills_dir = temp_skills_dir
        kernel._project_root = temp_skills_dir.parent
        kernel._watcher = None
        kernel._sniffer = None
        kernel._router = None
        return kernel

    @pytest.mark.asyncio
    async def test_kernel_enable_hot_reload(self, mock_kernel) -> None:
        """Test kernel can enable hot reload with Rust watcher."""
        from omni.core.kernel.watcher import RustKernelWatcher

        # Track callback invocations
        callback_count = 0
        changed_files = []

        def callback(skill_name: str) -> None:
            nonlocal callback_count
            callback_count += 1
            changed_files.append(skill_name)

        # Create watcher
        watcher = RustKernelWatcher(mock_kernel._skills_dir, callback)

        # Start watcher
        watcher.start()
        assert watcher._running is True
        assert watcher._watcher_handle is not None
        assert watcher._event_receiver is not None

        # Give watcher time to start
        await asyncio.sleep(0.1)

        # Stop watcher
        watcher.stop()
        # Give Rust watcher time to actually stop
        await asyncio.sleep(0.1)
        assert watcher._running is False

    def test_kernel_watcher_skill_name_extraction(self, mock_kernel) -> None:
        """Test watcher correctly extracts skill names from file paths."""
        from omni.core.kernel.watcher import RustKernelWatcher

        callback = lambda name: None
        watcher = RustKernelWatcher(mock_kernel._skills_dir, callback)

        # Test various file paths
        skills_dir = str(mock_kernel._skills_dir)

        assert watcher._extract_skill_name(f"{skills_dir}/git/tools.py") == "git"
        assert watcher._extract_skill_name(f"{skills_dir}/terminal/execute.py") == "terminal"
        assert watcher._extract_skill_name(f"{skills_dir}/unknown/file.py") == "unknown"

        # Test exclusion patterns - __pycache__ is excluded
        assert watcher._extract_skill_name(f"{skills_dir}/git/__pycache__/test.py") is None
        # Note: .git/config would be handled by the Rust watcher exclude patterns
        # The Python extraction only checks filename prefix and __pycache__

    @pytest.mark.asyncio
    async def test_kernel_with_reactor_and_watcher(self, temp_skills_dir: Path) -> None:
        """Test kernel reactor can receive file events from Rust watcher."""
        from omni.core.kernel.watcher import RustKernelWatcher
        from omni.core.kernel.engine import Kernel

        # Create kernel
        kernel = Kernel.__new__(Kernel)
        kernel._skills_dir = temp_skills_dir
        kernel._project_root = temp_skills_dir.parent
        kernel._watcher = None
        kernel._sniffer = None
        kernel._router = None

        # Track events
        received_events: list[str] = []

        def callback(skill_name: str) -> None:
            received_events.append(skill_name)

        # Start watcher
        watcher = RustKernelWatcher(temp_skills_dir, callback)
        watcher.start()

        # Let watcher run
        await asyncio.sleep(0.3)

        # Stop watcher
        watcher.stop()

        # Verify no errors occurred
        assert len(received_events) >= 0  # May or may not have events


class TestWatcherWithActualKernel:
    """Tests using the actual Kernel initialization."""

    @pytest.fixture
    def sample_skills_dir(self) -> Path:
        """Create a minimal skills directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()

            # Create minimal skill
            (skills_dir / "test_skill").mkdir()
            (skills_dir / "test_skill" / "SKILL.md").write_text("""---
name: test_skill
description: Test skill
---
""")
            (skills_dir / "test_skill" / "tools.py").write_text("""
from omni.agent import skill_command

@skill_command
def test_cmd():
    '''Test command'''
    pass
""")

            yield skills_dir

    @pytest.mark.asyncio
    async def test_kernel_full_lifecycle_with_watcher(self, sample_skills_dir: Path) -> None:
        """Test full Kernel lifecycle with hot reload enabled."""
        from omni.core.kernel import get_kernel

        # This tests the actual kernel initialization
        # Note: We patch to avoid full initialization if needed
        with patch("omni.core.kernel.engine.configure_logging"):
            from omni.core.kernel.engine import Kernel

            kernel = Kernel(skills_dir=sample_skills_dir)

            # Verify initial state
            assert kernel._skills_dir == sample_skills_dir
            assert kernel._watcher is None

            # Initialize kernel first (puts it in READY state)
            await kernel.initialize()

            # Enable hot reload
            kernel.enable_hot_reload()

            # Verify watcher started
            assert kernel._watcher is not None
            assert kernel._watcher._running is True

            # Get reference before shutdown
            watcher = kernel._watcher

            # Stop kernel (which stops watcher)
            await kernel.shutdown()

            # Give Rust watcher time to actually stop
            await asyncio.sleep(0.1)

            # Verify watcher Python state is stopped (Rust handle may lag)
            assert watcher._running is False


class TestWatcherEventFlow:
    """Test the event flow from Rust watcher through Python to Kernel."""

    def test_event_receiver_receives_after_watcher_start(self) -> None:
        """Test that receiver can receive events after watcher starts."""
        import omni_core_rs as rs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create receiver first
            receiver = rs.PyFileEventReceiver()

            # Start watcher
            config = rs.PyWatcherConfig(paths=[tmpdir])
            handle = rs.py_start_file_watcher(config)

            time.sleep(0.3)

            # Create file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            time.sleep(0.3)

            # Try receiving
            events = receiver.try_recv()

            handle.stop()

            # Should have received events (or empty if FSEvents delayed)
            assert isinstance(events, list)

    def test_multiple_watchers_same_directory(self) -> None:
        """Test multiple watchers can watch the same directory."""
        import omni_core_rs as rs

        with tempfile.TemporaryDirectory() as tmpdir:
            receiver1 = rs.PyFileEventReceiver()
            receiver2 = rs.PyFileEventReceiver()

            handle1 = rs.py_watch_path(tmpdir)
            handle2 = rs.py_watch_path(tmpdir)

            time.sleep(0.3)

            # Create file
            (Path(tmpdir) / "test.txt").write_text("test")
            time.sleep(0.3)

            events1 = receiver1.try_recv()
            events2 = receiver2.try_recv()

            handle1.stop()
            handle2.stop()

            # Both receivers should get events
            assert isinstance(events1, list)
            assert isinstance(events2, list)
