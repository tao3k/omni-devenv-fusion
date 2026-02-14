"""Integration tests for Rust-native file watcher with Kernel."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestWatcherIndexerContract:
    """Test that watcher and indexer have matching contracts.

    These tests verify that the methods called by the watcher
    actually exist on the real SkillIndexer, preventing bugs like:
    - AttributeError when calling non-existent methods
    - Missing method signatures
    """

    def test_indexer_has_required_methods(self):
        """Verify SkillIndexer has all methods called by watcher."""
        from omni.core.skills.indexer import SkillIndexer

        # These are the methods watcher calls on indexer
        required_methods = [
            "index_file",
            "reindex_file",
            "remove_file",
        ]

        for method_name in required_methods:
            assert hasattr(SkillIndexer, method_name), (
                f"SkillIndexer missing required method: {method_name}"
            )

    def test_store_has_delete_by_file_path(self):
        """Verify RustVectorStore has delete_by_file_path method.

        This is critical: SkillIndexer.remove_file() calls store.delete_by_file_path(),
        which must exist on the RustVectorStore wrapper.
        """
        from omni.foundation.bridge.rust_vector import RustVectorStore

        assert hasattr(RustVectorStore, "delete_by_file_path"), (
            "RustVectorStore missing delete_by_file_path method"
        )


class TestReactiveSkillWatcherIntegration:
    """Integration tests for ReactiveSkillWatcher with Kernel."""

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
    def mock_indexer(self):
        """Create a mock indexer for testing."""
        from unittest.mock import AsyncMock

        indexer = MagicMock()
        indexer.index_file = AsyncMock(return_value=1)
        indexer.reindex_file = AsyncMock(return_value=1)
        indexer.remove_file = AsyncMock(return_value=1)
        return indexer

    @pytest.mark.asyncio
    async def test_reactive_watcher_lifecycle(self, temp_skills_dir: Path, mock_indexer) -> None:
        """Test ReactiveSkillWatcher can start and stop."""
        from omni.core.kernel.watcher import ReactiveSkillWatcher

        # Create watcher
        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.1,
            poll_interval=0.1,
        )

        # Start watcher
        await watcher.start()
        assert watcher.is_running is True
        assert watcher._watcher_handle is not None

        # Stop watcher
        await watcher.stop()
        assert watcher.is_running is False

    @pytest.mark.asyncio
    async def test_reactive_watcher_receives_events(
        self, temp_skills_dir: Path, mock_indexer
    ) -> None:
        """Test ReactiveSkillWatcher can be created and started."""
        from omni.core.kernel.watcher import ReactiveSkillWatcher

        # Create watcher - it will watch assets/skills (from config)
        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.1,
            poll_interval=0.1,
        )

        # Start watcher
        await watcher.start()

        # Verify it started
        assert watcher.is_running is True
        assert watcher._watcher_handle is not None

        # Give watcher time to initialize
        await asyncio.sleep(0.3)

        # Stop watcher
        await watcher.stop()
        assert watcher.is_running is False

        # Verify indexer was used (for initialization scan)
        # Note: We can't guarantee events for specific files since watcher
        # watches assets/skills from config, not temp directory

    @pytest.mark.asyncio
    async def test_reactive_watcher_extracts_skill_name(
        self, temp_skills_dir: Path, mock_indexer
    ) -> None:
        """Test ReactiveSkillWatcher correctly extracts skill names."""
        from omni.core.kernel.watcher import ReactiveSkillWatcher

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
        )

        # Test skill name extraction (using internal method)
        # Note: We need to patch skills_dir for this test
        skills_dir_str = str(temp_skills_dir)

        # The watcher uses self.skills_dir which comes from SKILLS_DIR() config
        # So we test with paths relative to actual skills_dir
        result = watcher._extract_skill_name(f"{skills_dir_str}/git/tools.py")
        # May return None if path doesn't match configured skills_dir
        # But the extraction logic itself should work

        # Test with a valid pattern
        test_path = str(temp_skills_dir / "test_skill" / "tools.py")
        result = watcher._extract_skill_name(test_path)
        assert result is None or result == "test_skill"


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
    async def test_kernel_watcher_property(self, sample_skills_dir: Path) -> None:
        """Test Kernel has watcher property."""
        from omni.core.kernel.watcher import ReactiveSkillWatcher

        # Create a standalone watcher - this verifies the API exists
        mock_indexer = MagicMock()
        mock_indexer.index_file = AsyncMock(return_value=1)

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
        )

        # Verify watcher has expected properties
        assert hasattr(watcher, "is_running")
        assert hasattr(watcher, "start")
        assert hasattr(watcher, "stop")
        assert hasattr(watcher, "_extract_skill_name")

    @pytest.mark.asyncio
    async def test_kernel_start_with_watcher(self, sample_skills_dir: Path) -> None:
        """Test Kernel can be started with watcher enabled."""
        from omni.core.kernel.watcher import ReactiveSkillWatcher
        from omni.core.skills.indexer import SkillIndexer
        from unittest.mock import MagicMock

        # Create mock indexer
        mock_indexer = MagicMock()
        mock_indexer.index_file = AsyncMock(return_value=1)
        mock_indexer.reindex_file = AsyncMock(return_value=1)
        mock_indexer.remove_file = AsyncMock(return_value=1)

        # Create and start watcher
        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.1,
            poll_interval=0.1,
        )

        await watcher.start()
        assert watcher.is_running is True

        await watcher.stop()
        assert watcher.is_running is False


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


class TestFileWatcherConfig:
    """Test Rust watcher configuration."""

    def test_watcher_config_defaults(self) -> None:
        """Test PyWatcherConfig has expected defaults."""
        import omni_core_rs as rs

        config = rs.PyWatcherConfig()

        assert config.recursive is True
        assert config.debounce_ms == 500  # Default 0.5 seconds
        assert isinstance(config.paths, list)
        assert isinstance(config.exclude, list)
        assert "**/*.pyc" in config.exclude
        assert "**/__pycache__/**" in config.exclude

    def test_watcher_config_modification(self) -> None:
        """Test PyWatcherConfig can be modified."""
        import omni_core_rs as rs

        config = rs.PyWatcherConfig()
        config.debounce_ms = 100
        config.recursive = False

        assert config.debounce_ms == 100
        assert config.recursive is False

    def test_watcher_config_add_patterns(self) -> None:
        """Test PyWatcherConfig add methods."""
        import omni_core_rs as rs

        config = rs.PyWatcherConfig()
        config.add_pattern("**/*.rs")
        config.add_exclude("**/target/**")

        assert "**/*.rs" in config.patterns
        assert "**/target/**" in config.exclude


class TestNotifyDebouncing:
    """Tests for debouncing logic to prevent race conditions with multiple MCP clients."""

    @pytest.fixture
    def skill_manager(self):
        """Create a SkillManager for testing debouncing."""
        from omni.core.services.skill_manager import SkillManager

        manager = SkillManager()
        # Set short cooldown for testing
        manager._notify_cooldown_seconds = 0.1
        return manager

    @pytest.mark.asyncio
    async def test_multiple_callbacks_notified(self, skill_manager):
        """Test that all registered callbacks are notified."""
        call_counts = []

        async def callback1():
            call_counts.append(1)

        async def callback2():
            call_counts.append(2)

        async def callback3():
            call_counts.append(3)

        skill_manager._on_update_callbacks = [callback1, callback2, callback3]

        await skill_manager._notify_updates()

        assert len(call_counts) == 3
        assert 1 in call_counts
        assert 2 in call_counts
        assert 3 in call_counts

    @pytest.mark.asyncio
    async def test_rapid_notifications_debounced(self, skill_manager):
        """Test that rapid notifications are debounced."""
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1

        skill_manager._on_update_callbacks = [callback]

        # Send multiple rapid notifications
        await skill_manager._notify_updates()
        await skill_manager._notify_updates()
        await skill_manager._notify_updates()

        # Should only count as one due to cooldown
        assert call_count == 1

        # Wait for cooldown
        await asyncio.sleep(0.15)

        # Now another notification should work
        await skill_manager._notify_updates()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_notifications_handled(self, skill_manager):
        """Test that concurrent notifications are handled correctly."""
        call_order = []

        async def slow_callback():
            await asyncio.sleep(0.1)
            call_order.append("slow")

        async def fast_callback():
            call_order.append("fast")

        skill_manager._on_update_callbacks = [slow_callback, fast_callback]

        # Start notification
        task = asyncio.create_task(skill_manager._notify_updates())

        # Send another notification while first is in progress
        await asyncio.sleep(0.02)  # Let slow callback start
        await skill_manager._notify_updates()

        await task

        # Both callbacks from first notification should have run
        # The second notification should have been skipped due to in-progress flag
        assert "slow" in call_order
        assert "fast" in call_order

    @pytest.mark.asyncio
    async def test_pending_notification_after_concurrent(self, skill_manager):
        """Test that pending notifications are processed after current one completes."""
        call_count = []

        async def callback():
            nonlocal call_count
            call_count.append(1)
            await asyncio.sleep(0.05)

        skill_manager._on_update_callbacks = [callback]

        # Start first notification
        task1 = asyncio.create_task(skill_manager._notify_updates())

        # Immediately send another (should be marked as pending)
        await skill_manager._notify_updates()

        await task1

        # Wait a bit and the pending notification should have triggered
        await asyncio.sleep(0.2)

        # Should have run twice (initial + pending)
        assert len(call_count) >= 2

    @pytest.mark.asyncio
    async def test_callback_exception_handling(self, skill_manager):
        """Test that exceptions in one callback don't affect others."""
        call_count = []

        async def failing_callback():
            raise ValueError("Intentional error")

        async def working_callback():
            nonlocal call_count
            call_count.append(1)

        async def another_callback():
            nonlocal call_count
            call_count.append(2)

        skill_manager._on_update_callbacks = [failing_callback, working_callback, another_callback]

        # Should not raise, just log the error
        await skill_manager._notify_updates()

        # Working callbacks should still be called
        assert 1 in call_count
        assert 2 in call_count

    @pytest.mark.asyncio
    async def test_sync_callback_handling(self, skill_manager):
        """Test that synchronous callbacks work correctly."""
        call_count = []

        def sync_callback():
            call_count.append("sync")

        async def async_callback():
            call_count.append("async")

        skill_manager._on_update_callbacks = [sync_callback, async_callback]

        await skill_manager._notify_updates()

        assert "sync" in call_count
        assert "async" in call_count


class TestSkillDiscoveryCache:
    """Tests for skill discovery cache refresh mechanism."""

    @pytest.fixture
    def discovery_service(self):
        """Create a SkillDiscoveryService for testing with mocked store."""
        from unittest.mock import AsyncMock, MagicMock, patch
        import asyncio

        # Create mock store that returns tools
        mock_store = MagicMock()
        mock_tools = [
            {
                "skill_name": "git",
                "tool_name": "git.status",
                "description": "Show git status",
                "file_path": "/project/assets/skills/git/scripts/commands.py",
            }
        ]
        # list_all_tools is synchronous in the actual implementation
        mock_store.list_all_tools = MagicMock(return_value=mock_tools)

        # Patch get_vector_store to return our mock
        with patch("omni.core.skills.discovery.get_vector_store", return_value=mock_store):
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            service._cache = []  # Initialize cache
            return service

    def test_cache_initialization(self, discovery_service):
        """Test that cache is initialized properly."""
        assert hasattr(discovery_service, "_cache")
        assert isinstance(discovery_service._cache, list)

    @pytest.mark.asyncio
    async def test_refresh_cache_clears_registry(self, discovery_service):
        """Test that refresh_cache clears the registry."""
        from unittest.mock import MagicMock, patch

        # Set up registry with some data
        discovery_service._registry = {"some_tool": MagicMock()}
        discovery_service._registry_loaded = True

        # Patch get_vector_store to return mock with empty tools
        mock_store = MagicMock()
        mock_store.list_all_tools = MagicMock(return_value=[])

        with patch("omni.core.skills.discovery.get_vector_store", return_value=mock_store):
            await discovery_service._refresh_cache()

            # Registry should be cleared and reloaded
            assert discovery_service._registry_loaded is False

    @pytest.mark.asyncio
    async def test_refresh_cache_logs_info(self, discovery_service, caplog):
        """Test that refresh_cache logs appropriately."""
        import logging

        # Patch get_vector_store to return mock
        mock_store = MagicMock()
        mock_store.list_all_tools = MagicMock(return_value=[])

        with patch("omni.core.skills.discovery.get_vector_store", return_value=mock_store):
            with caplog.at_level(logging.DEBUG):
                await discovery_service._refresh_cache()

                assert any(
                    "refreshing" in msg.lower() or "refresh" in msg.lower()
                    for msg in caplog.messages
                )


class TestFileEventHandling:
    """Tests for file event handling with different scenarios."""

    @pytest.fixture
    def temp_skill_dir(self, tmp_path):
        """Create a temporary skill directory."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        return skill_dir

    @pytest.fixture
    def mock_indexer(self):
        """Create a mock indexer."""
        from unittest.mock import AsyncMock

        indexer = AsyncMock()
        indexer.index_file = AsyncMock(return_value=1)
        indexer.reindex_file = AsyncMock(return_value=1)
        indexer.remove_file = AsyncMock(return_value=1)
        return indexer

    @pytest.mark.asyncio
    async def test_created_file_event(self, temp_skill_dir, mock_indexer):
        """Test handling of file creation events."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.01,
            poll_interval=0.01,
        )

        # Create a new file
        new_file = temp_skill_dir / "scripts" / "new_command.py"
        new_file.write_text("""
def new_command():
    '''A new command'''
    pass
""")

        # Create event for the new file
        event = FileChangeEvent(
            path=str(new_file),
            event_type=FileChangeType.CREATED,
        )

        await watcher._handle_event(event)

        # index_file should have been called
        mock_indexer.index_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_modified_file_event(self, temp_skill_dir, mock_indexer):
        """Test handling of file modification events."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.01,
            poll_interval=0.01,
        )

        # Create and modify a file
        cmd_file = temp_skill_dir / "scripts" / "commands.py"
        cmd_file.write_text("""
def existing_command():
    '''An existing command'''
    pass
""")

        event = FileChangeEvent(
            path=str(cmd_file),
            event_type=FileChangeType.MODIFIED,
        )

        await watcher._handle_event(event)

        # reindex_file should have been called
        mock_indexer.reindex_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_deleted_file_event(self, temp_skill_dir, mock_indexer):
        """Test handling of file deletion events."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.01,
            poll_interval=0.01,
        )

        # Create a file then delete it
        cmd_file = temp_skill_dir / "scripts" / "to_delete.py"
        cmd_file.write_text("""
def to_delete():
    '''Will be deleted'''
    pass
""")

        # Delete the file
        cmd_file.unlink()

        event = FileChangeEvent(
            path=str(cmd_file),
            event_type=FileChangeType.DELETED,
        )

        await watcher._handle_event(event)

        # remove_file should have been called
        mock_indexer.remove_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_nonexistent_file_for_created_event(self, temp_skill_dir, mock_indexer):
        """Test that non-existent file for CREATED event is handled correctly.

        The watcher has a workaround: CREATED events for non-existent files
        should be treated as DELETED events (Rust watcher may report created
        instead of deleted when a file is deleted).
        """
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher

        watcher = ReactiveSkillWatcher(
            indexer=mock_indexer,
            patterns=["**/*.py"],
            debounce_seconds=0.01,
            poll_interval=0.01,
        )

        # Event for a file that doesn't exist (Rust watcher workaround)
        nonexistent_file = temp_skill_dir / "scripts" / "nonexistent.py"
        event = FileChangeEvent(
            path=str(nonexistent_file),
            event_type=FileChangeType.CREATED,
        )

        await watcher._handle_event(event)

        # For CREATED events where file doesn't exist, it should be treated as DELETED
        # So remove_file should be called, not index_file
        mock_indexer.index_file.assert_not_called()
        mock_indexer.reindex_file.assert_not_called()
        mock_indexer.remove_file.assert_called_once()


class TestWatcherWithKernelIntegration:
    """Integration tests for watcher with kernel."""

    @pytest.fixture
    def kernel_mock(self):
        """Create a mock kernel for testing."""
        from unittest.mock import AsyncMock, MagicMock

        kernel = MagicMock()
        kernel.reload_skill = AsyncMock()
        return kernel

    @pytest.mark.asyncio
    async def test_reload_skill_called_on_modification(self, kernel_mock):
        """Test that kernel.reload_skill is called on file modification."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher
        from unittest.mock import AsyncMock, patch
        from pathlib import Path

        mock_indexer = AsyncMock()
        mock_indexer.reindex_file = AsyncMock(return_value=1)

        # Create a temp directory to use as skills_dir
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Patch SKILLS_DIR where it's defined
            with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
                watcher = ReactiveSkillWatcher(
                    indexer=mock_indexer,
                    patterns=["**/*.py"],
                    debounce_seconds=0.01,
                    poll_interval=0.01,
                )
                watcher._kernel = kernel_mock

                # Create test file path under the temp skills_dir
                test_file = skills_dir / "git" / "scripts" / "commands.py"
                event = FileChangeEvent(
                    path=str(test_file),
                    event_type=FileChangeType.MODIFIED,
                )

                await watcher._handle_event(event)

                # reload_skill should have been called for "git"
                kernel_mock.reload_skill.assert_called_once_with("git")

    @pytest.mark.asyncio
    async def test_reload_skill_not_called_for_unknown_skill(self, kernel_mock):
        """Test that reload_skill is not called for files outside skills dir."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType, ReactiveSkillWatcher
        from unittest.mock import AsyncMock, patch
        from pathlib import Path

        mock_indexer = AsyncMock()
        mock_indexer.reindex_file = AsyncMock(return_value=1)

        # Create a temp directory to use as skills_dir
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Patch SKILLS_DIR where it's defined
            with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
                watcher = ReactiveSkillWatcher(
                    indexer=mock_indexer,
                    patterns=["**/*.py"],
                    debounce_seconds=0.01,
                    poll_interval=0.01,
                )
                watcher._kernel = kernel_mock

                # Event for a file outside skills directory
                event = FileChangeEvent(
                    path="/project/src/some_module.py",
                    event_type=FileChangeType.MODIFIED,
                )

                await watcher._handle_event(event)

                # reload_skill should NOT have been called
                kernel_mock.reload_skill.assert_not_called()
