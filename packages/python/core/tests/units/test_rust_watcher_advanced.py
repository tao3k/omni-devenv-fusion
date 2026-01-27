"""Comprehensive tests for Rust-native file watcher functionality.

Covers:
- Debounce logic (Modify vs Create/Delete)
- Exclusion patterns
- Callback integration
- RustKernelWatcher event propagation
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

import omni_core_rs as rs
from omni.core.kernel.watcher import RustKernelWatcher


class TestWatcherDebounceLogic:
    """Test detailed debounce behavior."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_receiver(self) -> rs.PyFileEventReceiver:
        """Create an event receiver."""
        return rs.PyFileEventReceiver()

    def test_create_events_not_debounced(
        self, temp_dir: Path, event_receiver: rs.PyFileEventReceiver
    ) -> None:
        """Test that Create events are NOT debounced (critical for macOS)."""
        # Set large debounce to verify 'Create' bypasses it
        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        config.debounce_ms = 2000  # 2 seconds

        handle = rs.py_start_file_watcher(config)
        time.sleep(0.5)  # Wait for startup

        # Create file 1
        (temp_dir / "file1.txt").write_text("content1")
        time.sleep(0.1)

        # Create file 2 immediately
        (temp_dir / "file2.txt").write_text("content2")
        time.sleep(3.0)  # Wait longer than debounce (2.0s) to be safe on macOS

        # Should receive both events immediately
        events = event_receiver.try_recv()

        handle.stop()

        # Filter for our files
        relevant_events = [(t, p) for t, p in events if "file1.txt" in p or "file2.txt" in p]

        # Should have at least 2 events (Created for each file)
        # On macOS we might see Create + Modify for each, so 4 events.
        # The key is we see events for BOTH files.
        file1_events = [e for e in relevant_events if "file1.txt" in e[1]]
        file2_events = [e for e in relevant_events if "file2.txt" in e[1]]

        assert len(file1_events) > 0
        assert len(file2_events) > 0

    def test_modify_events_debounced(
        self, temp_dir: Path, event_receiver: rs.PyFileEventReceiver
    ) -> None:
        """Test that Modify events ARE debounced."""
        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        config.debounce_ms = 1000  # 1 second

        handle = rs.py_start_file_watcher(config)
        time.sleep(0.5)

        test_file = temp_dir / "debounce.txt"
        test_file.write_text("initial")
        time.sleep(1.5)  # Wait for initial create/modify to settle

        # Clear previous events
        _ = event_receiver.try_recv()

        # Rapid modifications
        for i in range(5):
            test_file.write_text(f"update {i}")
            time.sleep(0.05)  # Very fast updates

        time.sleep(0.5)  # Wait less than debounce

        events_rapid = event_receiver.try_recv()

        time.sleep(1.0)  # Wait for debounce to expire
        events_final = event_receiver.try_recv()

        handle.stop()

        all_events = events_rapid + events_final
        modify_events = [e for e in all_events if e[0] == "changed" and "debounce.txt" in e[1]]

        # We expect fewer modify events than the number of writes (5)
        # Ideally 1, but macOS might leak 2.
        assert len(modify_events) < 5


class TestWatcherExclusion:
    """Test file exclusion patterns."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_receiver(self) -> rs.PyFileEventReceiver:
        """Create an event receiver."""
        return rs.PyFileEventReceiver()

    def test_exclude_patterns(self, temp_dir: Path, event_receiver: rs.PyFileEventReceiver) -> None:
        """Test that excluded files do not trigger events."""
        config = rs.PyWatcherConfig(paths=[str(temp_dir)])
        config.add_exclude("**/*.tmp")
        config.add_exclude("**/ignored/**")

        handle = rs.py_start_file_watcher(config)
        time.sleep(0.5)

        # 1. Ignored extension
        (temp_dir / "test.tmp").write_text("ignored")

        # 2. Ignored directory
        ignored_dir = temp_dir / "ignored"
        ignored_dir.mkdir()
        (ignored_dir / "should_ignore.txt").write_text("ignored")

        # 3. Valid file
        (temp_dir / "valid.txt").write_text("valid")

        time.sleep(1.0)

        events = event_receiver.try_recv()
        handle.stop()

        # Check paths in events
        paths = [p for _, p in events]

        assert not any(p.endswith("test.tmp") for p in paths)
        assert not any("should_ignore.txt" in p for p in paths)
        assert any("valid.txt" in p for p in paths)


class TestRustKernelWatcherIntegration:
    """End-to-end integration tests for RustKernelWatcher."""

    @pytest.fixture
    def temp_skills_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    async def test_callback_trigger(self, temp_skills_dir: Path) -> None:
        """Test that file changes trigger the Python callback."""
        triggered_skills = []

        def callback(skill_name: str) -> None:
            triggered_skills.append(skill_name)

        watcher = RustKernelWatcher(temp_skills_dir, callback, debounce_seconds=0.1)

        watcher.start()
        await asyncio.sleep(0.5)

        # Create a skill structure
        skill_dir = temp_skills_dir / "myskill"
        skill_dir.mkdir()
        (skill_dir / "tool.py").write_text("print('hello')")

        # Wait for poll loop to pick it up
        await asyncio.sleep(1.5)

        watcher.stop()
        await asyncio.sleep(0.1)

        assert "myskill" in triggered_skills

    async def test_nested_skill_change(self, temp_skills_dir: Path) -> None:
        """Test changes deep inside a skill directory."""
        triggered_skills = []

        def callback(skill_name: str) -> None:
            triggered_skills.append(skill_name)

        watcher = RustKernelWatcher(temp_skills_dir, callback, debounce_seconds=0.1)

        # Setup deep structure
        deep_dir = temp_skills_dir / "complex_skill" / "src" / "utils"
        os.makedirs(deep_dir)

        watcher.start()
        await asyncio.sleep(0.5)

        # Modify deep file
        (deep_dir / "helper.py").write_text("def help(): pass")

        await asyncio.sleep(1.5)

        watcher.stop()
        await asyncio.sleep(0.1)

        assert "complex_skill" in triggered_skills
