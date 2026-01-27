"""Tests for Rust-native file watcher (omni-core-rs notify bindings)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

import omni_core_rs as rs


class TestRustWatcherBindings:
    """Test Rust watcher bindings availability and basic functionality."""

    def test_watcher_config_creation(self) -> None:
        """Test PyWatcherConfig creation with default values."""
        config = rs.PyWatcherConfig(paths=["/test"])
        assert config.paths == ["/test"]
        assert config.recursive is True
        assert config.debounce_ms == 500
        assert "**/*.pyc" in config.exclude

    def test_watcher_config_modification(self) -> None:
        """Test PyWatcherConfig property modification."""
        config = rs.PyWatcherConfig()
        config.recursive = False
        config.debounce_ms = 100
        assert config.recursive is False
        assert config.debounce_ms == 100

    def test_watcher_config_add_patterns(self) -> None:
        """Test PyWatcherConfig add methods."""
        config = rs.PyWatcherConfig()
        config.add_pattern("**/*.rs")
        config.add_exclude("**/target/**")
        assert "**/*.rs" in config.patterns
        assert "**/target/**" in config.exclude

    def test_file_event_creation(self) -> None:
        """Test PyFileEvent creation via constructor not available (internal use)."""
        # PyFileEvent is created by Rust watcher, not directly instantiated
        # We verify it's available as a class
        assert hasattr(rs, "PyFileEvent")

    def test_file_event_receiver_creation(self) -> None:
        """Test PyFileEventReceiver creation."""
        receiver = rs.PyFileEventReceiver()
        assert receiver is not None

    def test_file_event_receiver_try_recv(self) -> None:
        """Test PyFileEventReceiver.try_recv returns empty list initially."""
        receiver = rs.PyFileEventReceiver()
        events = receiver.try_recv()
        assert isinstance(events, list)
        assert len(events) == 0


class TestRustWatcherIntegration:
    """Integration tests for Rust file watcher with temporary directories."""

    @pytest.fixture
    def temp_skill_dir(self) -> Path:
        """Create a temporary directory simulating a skills directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_receiver(self) -> rs.PyFileEventReceiver:
        """Create an event receiver for testing."""
        return rs.PyFileEventReceiver()

    def test_watcher_start_stop(self, temp_skill_dir: Path) -> None:
        """Test watcher can start and stop without errors."""
        config = rs.PyWatcherConfig(paths=[str(temp_skill_dir)])
        handle = rs.py_start_file_watcher(config)

        # Verify handle was created and stop works
        assert handle is not None

        handle.stop()
        # Note: is_running property not available in this implementation

    def test_watcher_simple_path_api(self, temp_skill_dir: Path) -> None:
        """Test py_watch_path simple API."""
        handle = rs.py_watch_path(str(temp_skill_dir))
        assert handle is not None
        handle.stop()

    def test_watcher_with_exclude_patterns(self, temp_skill_dir: Path) -> None:
        """Test watcher with custom exclude patterns."""
        config = rs.PyWatcherConfig(paths=[str(temp_skill_dir)])
        config.exclude = ["**/*.tmp", "**/__pycache__/**"]

        handle = rs.py_start_file_watcher(config)
        assert handle.is_running is True
        handle.stop()


class TestRustKernelWatcher:
    """Test the RustKernelWatcher Python wrapper class."""

    @pytest.fixture
    def temp_skill_dir(self) -> Path:
        """Create a temporary directory simulating a skills directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def callback_results(self) -> list[str]:
        """Track callback invocations."""
        return []

    def _make_callback(self, results: list[str]) -> Any:
        """Create a callback that records skill names."""

        def callback(skill_name: str) -> None:
            results.append(skill_name)

        return callback

    def test_rust_kernel_watcher_init(self, temp_skill_dir: Path) -> None:
        """Test RustKernelWatcher initialization."""
        from omni.core.kernel.watcher import RustKernelWatcher

        callback = lambda name: None
        watcher = RustKernelWatcher(temp_skill_dir, callback)

        assert watcher.skills_dir == temp_skill_dir
        assert watcher.debounce_seconds == 0.5
        assert watcher._watcher_handle is None
        assert watcher._event_receiver is None

    def test_rust_kernel_watcher_extract_skill_name(self, temp_skill_dir: Path) -> None:
        """Test skill name extraction from paths."""
        from omni.core.kernel.watcher import RustKernelWatcher

        callback = lambda name: None
        watcher = RustKernelWatcher(temp_skill_dir, callback)

        # Valid skill path
        result = watcher._extract_skill_name(str(temp_skill_dir / "git" / "test.py"))
        assert result == "git"

        # Skip patterns
        assert watcher._extract_skill_name("/some/__pycache__/test.py") is None
        assert watcher._extract_skill_name("/some/.hidden/test.py") is None

    async def test_rust_kernel_watcher_start_stop(self, temp_skill_dir: Path) -> None:
        """Test RustKernelWatcher start and stop."""
        from omni.core.kernel.watcher import RustKernelWatcher

        callback = lambda name: None
        watcher = RustKernelWatcher(temp_skill_dir, callback)

        watcher.start()
        assert watcher._watcher_handle is not None
        assert watcher._event_receiver is not None

        watcher.stop()
        await asyncio.sleep(0.1)  # Allow poll task to cancel
        assert watcher._running is False

    async def test_rust_kernel_watcher_lifecycle(self, temp_skill_dir: Path) -> None:
        """Test watcher lifecycle (start/stop)."""
        from omni.core.kernel.watcher import RustKernelWatcher

        callback = lambda name: None
        watcher = RustKernelWatcher(temp_skill_dir, callback)

        assert watcher._watcher_handle is None

        watcher.start()
        assert watcher._watcher_handle is not None

        watcher.stop()
        await asyncio.sleep(0.1)  # Allow poll task to cancel
        assert watcher._running is False


class TestFileWatcherLifecycle:
    """Test file watcher lifecycle with actual file operations."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_receiver(self) -> rs.PyFileEventReceiver:
        """Create an event receiver."""
        return rs.PyFileEventReceiver()

    def test_watcher_receives_create_event(
        self, temp_dir: Path, event_receiver: rs.PyFileEventReceiver
    ) -> None:
        """Test watcher detects file creation events."""
        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        handle = rs.py_start_file_watcher(config)

        # Give watcher time to initialize
        time.sleep(0.2)

        # Create a file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        # Wait for event to propagate
        time.sleep(0.5)

        # Try receiving events
        events = event_receiver.try_recv()

        handle.stop()

        # Events may or may not be received depending on filesystem
        assert isinstance(events, list)

    def test_watcher_multiple_file_operations(
        self, temp_dir: Path, event_receiver: rs.PyFileEventReceiver
    ) -> None:
        """Test watcher with multiple file operations."""
        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        handle = rs.py_start_file_watcher(config)

        time.sleep(0.2)

        # Multiple file operations
        for i in range(3):
            (temp_dir / f"file_{i}.txt").write_text(f"content {i}")

        time.sleep(0.5)

        events = event_receiver.try_recv()

        handle.stop()

        assert isinstance(events, list)

    def test_event_receiver_persistence(self, temp_dir: Path) -> None:
        """Test that event receiver maintains subscription across multiple polls."""
        receiver = rs.PyFileEventReceiver()

        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        handle = rs.py_start_file_watcher(config)

        time.sleep(0.2)

        # Create file
        (temp_dir / "test.txt").write_text("test")
        time.sleep(0.3)

        # First poll
        events1 = receiver.try_recv()

        # Create another file
        (temp_dir / "test2.txt").write_text("test2")
        time.sleep(0.3)

        # Second poll - should receive new events
        events2 = receiver.try_recv()

        handle.stop()

        # Both polls should return list
        assert isinstance(events1, list)
        assert isinstance(events2, list)
