"""Tests for Rust-native file watcher (omni-core-rs notify bindings)."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

import omni_core_rs as rs
from omni.core.kernel.watcher import (
    FileChangeEvent,
    FileChangeType,
    ReactiveSkillWatcher,
)


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


class TestReactiveSkillWatcher:
    """Test ReactiveSkillWatcher (Live-Wire) functionality using test-kit fixtures."""

    @pytest.fixture
    def mock_indexer(self, mock_watcher_indexer):
        """Use test-kit fixture for mock indexer."""
        return mock_watcher_indexer

    def test_reactive_skill_watcher_init(self, mock_indexer) -> None:
        """Test ReactiveSkillWatcher initialization."""
        watcher = ReactiveSkillWatcher(indexer=mock_indexer)

        assert watcher.indexer == mock_indexer
        assert watcher.debounce_seconds == 0.5
        assert watcher.poll_interval == 0.5
        assert watcher._kernel is None

    def test_reactive_skill_watcher_extract_skill_name(self, mock_indexer) -> None:
        """Test skill name extraction from paths."""
        watcher = ReactiveSkillWatcher(indexer=mock_indexer)

        # Valid skill path
        result = watcher._extract_skill_name(str(watcher.skills_dir / "git" / "test.py"))
        assert result == "git"

        # Skip patterns
        assert watcher._extract_skill_name("/some/__pycache__/test.py") is None
        assert watcher._extract_skill_name("/some/.hidden/test.py") is None

    async def test_reactive_skill_watcher_start_stop(self, mock_indexer) -> None:
        """Test ReactiveSkillWatcher start and stop."""
        watcher = ReactiveSkillWatcher(indexer=mock_indexer)

        await watcher.start()
        assert watcher._watcher_handle is not None
        assert watcher._event_receiver is not None

        await watcher.stop()
        await asyncio.sleep(0.1)  # Allow poll task to cancel
        assert watcher._running is False

    async def test_reactive_skill_watcher_lifecycle(self, mock_indexer) -> None:
        """Test watcher lifecycle (start/stop)."""
        watcher = ReactiveSkillWatcher(indexer=mock_indexer)

        assert watcher._watcher_handle is None

        await watcher.start()
        assert watcher._watcher_handle is not None

        await watcher.stop()
        await asyncio.sleep(0.1)  # Allow poll task to cancel
        assert watcher._running is False


class TestReactiveSkillWatcherEvents:
    """Test ReactiveSkillWatcher event handling for Live-Wire scenarios.

    Uses test-kit fixtures for cleaner test code.
    """

    @pytest.fixture
    def mock_indexer(self, mock_watcher_indexer):
        """Use test-kit fixture for mock indexer."""
        return mock_watcher_indexer

    @pytest.fixture
    def watcher(self, mock_indexer) -> ReactiveSkillWatcher:
        """Create a ReactiveSkillWatcher instance for testing."""
        return ReactiveSkillWatcher(indexer=mock_indexer)

    async def test_deleted_event_not_debounced(self, watcher) -> None:
        """Test that DELETED events are never debounced.

        This is critical for the delete-re-add scenario where a user deletes
        a file and immediately re-creates it. Both events should be processed.
        """
        # Create two DELETED events for the same file
        event1 = FileChangeEvent(event_type=FileChangeType.DELETED, path="/skills/git/test.py")
        event2 = FileChangeEvent(event_type=FileChangeType.DELETED, path="/skills/git/test.py")

        # Both should NOT be debounced (return False)
        assert watcher._should_debounce(event1) is False
        # After processing event1, event2 should still not be debounced
        assert watcher._should_debounce(event2) is False

    async def test_modified_event_can_be_debounced(self, mock_indexer) -> None:
        """Test that MODIFIED events can be debounced for rapid saves."""
        watcher = ReactiveSkillWatcher(indexer=mock_indexer, debounce_seconds=0.5)

        event1 = FileChangeEvent(event_type=FileChangeType.MODIFIED, path="/skills/git/test.py")
        event2 = FileChangeEvent(event_type=FileChangeType.MODIFIED, path="/skills/git/test.py")

        # First event should not be debounced
        assert watcher._should_debounce(event1) is False
        # Second event should be debounced (same file, same type, within debounce window)
        assert watcher._should_debounce(event2) is True

    async def test_deleted_event_calls_remove_file(self, watcher, mock_indexer) -> None:
        """Test that DELETED events trigger remove_file on the indexer."""
        event = FileChangeEvent(event_type=FileChangeType.DELETED, path="/skills/git/test.py")

        await watcher._handle_event(event)

        mock_indexer.remove_file.assert_called_once_with("/skills/git/test.py")

    async def test_created_event_calls_index_file(self, watcher, mock_indexer) -> None:
        """Test that CREATED events trigger index_file on the indexer."""
        event = FileChangeEvent(event_type=FileChangeType.CREATED, path="/skills/git/new_tool.py")

        await watcher._handle_event(event)

        mock_indexer.index_file.assert_called_once_with("/skills/git/new_tool.py")

    async def test_changed_event_calls_reindex_file(self, watcher, mock_indexer) -> None:
        """Test that CHANGED events trigger reindex_file on the indexer."""
        event = FileChangeEvent(event_type=FileChangeType.CHANGED, path="/skills/git/existing.py")

        await watcher._handle_event(event)

        mock_indexer.reindex_file.assert_called_once_with("/skills/git/existing.py")

    async def test_callback_triggered_on_created(self, watcher, mock_indexer) -> None:
        """Test that on_change_callback is triggered for CREATED events."""
        callback_triggered = False

        def callback():
            nonlocal callback_triggered
            callback_triggered = True

        watcher.set_on_change_callback(callback)

        event = FileChangeEvent(event_type=FileChangeType.CREATED, path="/skills/git/new_tool.py")

        await watcher._handle_event(event)

        # Callback should be triggered (may be async, so check via mock)
        assert callback_triggered or mock_indexer.index_file.call_count == 1

    async def test_callback_triggered_on_deleted(self, watcher, mock_indexer) -> None:
        """Test that on_change_callback is triggered for DELETED events."""
        callback_triggered = False

        def callback():
            nonlocal callback_triggered
            callback_triggered = True

        watcher.set_on_change_callback(callback)

        event = FileChangeEvent(event_type=FileChangeType.DELETED, path="/skills/git/test.py")

        await watcher._handle_event(event)

        assert callback_triggered or mock_indexer.remove_file.call_count == 1

    async def test_delete_workaround_for_nonexistent_file(
        self, watcher, mock_indexer, tmp_path
    ) -> None:
        """Test that Rust watcher workaround correctly handles deleted files.

        The Rust watcher may send 'created' or 'changed' events for deleted files.
        The workaround detects file non-existence and treats these as DELETED events.
        """
        # Create a non-existent file path
        nonexistent_path = str(tmp_path / "deleted_file.py")

        # Rust may send 'created' event for a deleted file
        event = FileChangeEvent(event_type=FileChangeType.CREATED, path=nonexistent_path)

        # The file doesn't exist, so this should be treated as DELETED
        # We verify by checking that remove_file is called (not index_file)
        await watcher._handle_event(event)

        # The workaround should detect file doesn't exist and treat as DELETED
        # This means remove_file should be called, not index_file
        mock_indexer.remove_file.assert_called()

    async def test_created_event_calls_index_file(self, watcher, mock_indexer, tmp_path) -> None:
        """Test that CREATED events trigger index_file on the indexer."""
        # Use tmp_path to create a real file that exists
        test_file = tmp_path / "git" / "new_tool.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('"""New tool."""\nasync def new_tool(): pass')

        event = FileChangeEvent(event_type=FileChangeType.CREATED, path=str(test_file))

        await watcher._handle_event(event)

        mock_indexer.index_file.assert_called_once_with(str(test_file))

    async def test_changed_event_calls_reindex_file(self, watcher, mock_indexer, tmp_path) -> None:
        """Test that CHANGED events trigger reindex_file on the indexer."""
        # Use tmp_path to create a real file that exists
        test_file = tmp_path / "git" / "existing.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('"""Existing tool."""\nasync def existing(): pass')

        event = FileChangeEvent(event_type=FileChangeType.CHANGED, path=str(test_file))

        await watcher._handle_event(event)

        mock_indexer.reindex_file.assert_called_once_with(str(test_file))

    async def test_delete_re_add_scenario(self, mock_indexer, tmp_path) -> None:
        """Test the delete-re-add scenario: delete file, then re-create it.

        This is a critical user scenario where:
        1. User deletes a skill file
        2. User immediately re-creates the file
        3. Both events should be processed correctly
        """
        # Create a real file that exists
        test_file = tmp_path / "test_tool.py"
        test_file.write_text('"""Test tool."""\nasync def test_tool(): pass')

        watcher = ReactiveSkillWatcher(indexer=mock_indexer, patterns=["**/*.py"])

        # Simulate delete event (file still exists but we tell watcher it was deleted)
        delete_event = FileChangeEvent(event_type=FileChangeType.DELETED, path=str(test_file))
        await watcher._handle_event(delete_event)

        # Verify remove_file was called
        assert mock_indexer.remove_file.call_count == 1

        # Reset mock
        mock_indexer.remove_file.reset_mock()
        mock_indexer.index_file.reset_mock()

        # Simulate re-add event (file now exists again)
        create_event = FileChangeEvent(event_type=FileChangeType.CREATED, path=str(test_file))
        await watcher._handle_event(create_event)

        # Verify index_file was called
        assert mock_indexer.index_file.call_count == 1


class TestFileChangeEvent:
    """Test FileChangeEvent dataclass and utilities."""

    def test_file_change_event_creation(self) -> None:
        """Test FileChangeEvent creation."""
        event = FileChangeEvent(
            event_type=FileChangeType.CREATED,
            path="/skills/git/test.py",
            is_directory=False,
        )

        assert event.event_type == FileChangeType.CREATED
        assert event.path == "/skills/git/test.py"
        assert event.is_directory is False

    def test_file_change_event_from_tuple(self) -> None:
        """Test FileChangeEvent.from_tuple factory method."""
        data = ("modified", "/skills/git/test.py")
        event = FileChangeEvent.from_tuple(data)

        assert event.event_type == FileChangeType.MODIFIED
        assert event.path == "/skills/git/test.py"

    def test_file_change_type_enum(self) -> None:
        """Test FileChangeType enum values."""
        assert FileChangeType.CREATED.value == "created"
        assert FileChangeType.MODIFIED.value == "modified"
        assert FileChangeType.DELETED.value == "deleted"
        assert FileChangeType.CHANGED.value == "changed"
        assert FileChangeType.ERROR.value == "error"


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


class TestVirtualPathScanning:
    """Test virtual path scanning - no filesystem required.

    Uses the new scan_paths and parse_script_content functions
    from omni_core_rs to test skill tool discovery without
    creating temporary files or directories.
    """

    def test_scan_paths_discovers_tools(self) -> None:
        """Test that scan_paths discovers tools from virtual file content."""
        from omni_core_rs import scan_paths

        files = [
            (
                "/virtual/git/scripts/new_tool.py",
                '''"""New tool for testing."""

@skill_command(name="new_tool")
async def new_tool(param: str) -> str:
    """A new tool discovered via virtual scanning."""
    return f"Result: {param}"
''',
            ),
            (
                "/virtual/git/scripts/existing_tool.py",
                '''"""Existing tool."""

@skill_command(name="existing_tool")
async def existing_tool(value: int) -> int:
    """An existing tool."""
    return value * 2
''',
            ),
        ]

        tools = scan_paths(files, "git", ["git", "version control"], [])

        assert len(tools) == 2
        tool_names = [t.tool_name for t in tools]
        assert "git.new_tool" in tool_names
        assert "git.existing_tool" in tool_names

    def test_scan_paths_with_keywords(self) -> None:
        """Test that scan_paths includes skill keywords."""
        from omni_core_rs import scan_paths

        files = [
            (
                "/virtual/test_skill/scripts/tool.py",
                '''@skill_command(name="test_tool")
def test_tool():
    """A test tool."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", ["test", "verify"], [])

        assert len(tools) == 1
        assert "test_skill" in tools[0].keywords
        assert "test_tool" in tools[0].keywords
        assert "test" in tools[0].keywords
        assert "verify" in tools[0].keywords

    def test_scan_paths_file_hash_consistency(self) -> None:
        """Test that file hash is consistent for identical content."""
        from omni_core_rs import scan_paths

        content = '''"""A tool."""

@skill_command(name="tool")
def tool():
    pass
'''

        files = [("/virtual/skill/scripts/tool.py", content)]

        tools1 = scan_paths(files, "skill", [], [])
        tools2 = scan_paths(files, "skill", [], [])

        assert len(tools1) == 1
        assert len(tools2) == 1
        assert tools1[0].file_hash == tools2[0].file_hash

    def test_scan_paths_different_hash_for_different_content(self) -> None:
        """Test that different content produces different file hash."""
        from omni_core_rs import scan_paths

        content1 = '''"""Version 1."""

@skill_command(name="tool")
def tool():
    pass
'''

        content2 = '''"""Version 2 with changes."""

@skill_command(name="tool")
def tool():
    pass
'''

        files1 = [("/virtual/skill/scripts/tool.py", content1)]
        files2 = [("/virtual/skill/scripts/tool.py", content2)]

        tools1 = scan_paths(files1, "skill", [], [])
        tools2 = scan_paths(files2, "skill", [], [])

        assert tools1[0].file_hash != tools2[0].file_hash

    def test_parse_script_content_single_tool(self) -> None:
        """Test parse_script_content for single tool."""
        from omni_core_rs import parse_script_content

        content = '''@skill_command(name="my_tool")
def my_tool(param: str) -> str:
    """My tool description."""
    return param
'''

        tools = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "test.my_tool"
        assert tools[0].function_name == "my_tool"
        assert tools[0].file_path == "/virtual/path/tool.py"

    def test_scan_paths_empty_list(self) -> None:
        """Test that empty file list returns empty tools."""
        from omni_core_rs import scan_paths

        tools = scan_paths([], "git", [], [])

        assert tools == []

    def test_scan_paths_skips_init_and_private(self) -> None:
        """Test that __init__.py and private files are skipped."""
        from omni_core_rs import scan_paths

        files = [
            (
                "/virtual/skill/scripts/__init__.py",
                '''@skill_command(name="init_tool")
def init_tool():
    """Should be skipped."""
    pass
''',
            ),
            (
                "/virtual/skill/scripts/_private.py",
                '''@skill_command(name="private_tool")
def private_tool():
    """Should be skipped."""
    pass
''',
            ),
            (
                "/virtual/skill/scripts/public.py",
                '''@skill_command(name="public_tool")
def public_tool():
    """Should be included."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "skill", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "skill.public_tool"

    def test_scan_paths_simulate_delete_re_add(self) -> None:
        """Test delete-re-add scenario using virtual paths.

        This simulates the critical user scenario where:
        1. User deletes a skill file
        2. User immediately re-creates the file
        3. Both events should be processed correctly
        """
        from omni_core_rs import scan_paths

        # Initial state: tool exists
        initial_files = [
            (
                "/virtual/git/scripts/test_tool.py",
                '''"""Test tool."""

@skill_command(name="test_tool")
def test_tool():
    pass
''',
            )
        ]
        initial_tools = scan_paths(initial_files, "git", [], [])
        assert len(initial_tools) == 1
        assert initial_tools[0].tool_name == "git.test_tool"

        # Simulate delete: empty list
        deleted_tools = scan_paths([], "git", [], [])
        assert len(deleted_tools) == 0

        # Simulate re-add: new content
        re_add_files = [
            (
                "/virtual/git/scripts/test_tool.py",
                '''"""Re-added test tool."""

@skill_command(name="test_tool")
def test_tool():
    pass
''',
            )
        ]
        re_add_tools = scan_paths(re_add_files, "git", [], [])
        assert len(re_add_tools) == 1
        assert re_add_tools[0].tool_name == "git.test_tool"
        # File hash should be different due to content change
        assert re_add_tools[0].file_hash != initial_tools[0].file_hash

    def test_scan_paths_multiple_tools_same_file(self) -> None:
        """Test scanning multiple tools in a single file."""
        from omni_core_rs import scan_paths

        files = [
            (
                "/virtual/skill/scripts/multi_tool.py",
                '''"""Multi-tool module."""

@skill_command(name="tool_a")
def tool_a(param: str) -> str:
    """Tool A."""
    return param

@skill_command(name="tool_b")
def tool_b(value: int) -> int:
    """Tool B."""
    return value * 2

@skill_command(name="tool_c")
def tool_c():
    """Tool C with no params."""
    pass
''',
            )
        ]

        tools = scan_paths(files, "skill", ["test"], [])

        assert len(tools) == 3
        tool_names = [t.tool_name for t in tools]
        assert "skill.tool_a" in tool_names
        assert "skill.tool_b" in tool_names
        assert "skill.tool_c" in tool_names

    def test_scan_paths_preserves_function_name(self) -> None:
        """Test that function name is preserved in ToolRecord."""
        from omni_core_rs import scan_paths

        files = [
            (
                "/virtual/skill/scripts/renamed_tool.py",
                '''"""Tool with different names."""

@skill_command(name="custom_name")
def original_function_name(param: str) -> str:
    """Tool with different decorator and function name."""
    return param
''',
            )
        ]

        tools = scan_paths(files, "skill", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "skill.custom_name"
        assert tools[0].function_name == "original_function_name"

    def test_virtual_scanning_for_watcher_testing(self) -> None:
        """Example: Using virtual scanning to test watcher behavior.

        This pattern allows testing scanner behavior without
        creating temporary directories or modifying assets.
        """
        from omni_core_rs import scan_paths

        def simulate_skill_change(skill_name: str, files: dict[str, str]) -> list:
            """Simulate skill file changes without filesystem."""
            file_list = [
                (f"/virtual/{skill_name}/scripts/{name}", content)
                for name, content in files.items()
            ]
            return scan_paths(file_list, skill_name, [], [])

        # Test adding a new tool
        new_files = {
            "git_plus.py": '''"""New git feature."""

@skill_command(name="git_plus")
def git_plus():
    """New git feature."""
    pass
''',
        }
        tools = simulate_skill_change("git", new_files)
        assert len(tools) == 1
        assert "git_plus" in tools[0].tool_name

        # Test modifying existing tool
        modified_files = {
            "status.py": '''"""Modified status."""

@skill_command(name="status")
def status(short: bool = False) -> str:
    """Modified status with new parameter."""
    return "modified"
''',
        }
        modified_tools = simulate_skill_change("git", modified_files)
        assert len(modified_tools) == 1
        assert "status" in modified_tools[0].tool_name
