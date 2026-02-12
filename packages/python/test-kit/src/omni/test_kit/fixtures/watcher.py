"""Watcher test fixtures and helpers for Live-Wire testing."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_watcher_indexer():
    """Create a mock skill indexer for watcher tests.

    Provides mocked versions of:
    - index_file: Returns 1 tool indexed
    - reindex_file: Returns 1 tool reindexed
    - remove_file: Returns 1 tool removed
    """
    mock = MagicMock()
    mock.index_file = AsyncMock(return_value=1)
    mock.reindex_file = AsyncMock(return_value=1)
    mock.remove_file = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def mock_watcher_indexer_with_count(mock_watcher_indexer):
    """Create a mock indexer with configurable return values.

    Use mock_watcher_indexer.index_file.return_value = X to configure.
    """
    return mock_watcher_indexer


@pytest.fixture
def temp_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary directory simulating a skills directory."""
    target = tmp_path / "skills"
    target.mkdir(parents=True, exist_ok=True)
    return target


@pytest.fixture
def sample_skill_script() -> str:
    """Return a sample skill script content with one tool."""
    return '''"""Sample skill script for testing."""

async def example_tool(param: str) -> str:
    """An example tool for testing.

    Args:
        param: A parameter

    Returns:
        A result string
    """
    return f"Result: {param}"
'''


@pytest.fixture
def sample_skill_with_tools() -> dict[str, str]:
    """Return a dict of sample skill scripts with multiple tools."""
    return {
        "tool_a.py": '''"""Tool A."""

async def tool_a(name: str) -> str:
    """Tool A implementation."""
    return f"A: {name}"
''',
        "tool_b.py": '''"""Tool B."""

async def tool_b(value: int) -> int:
    """Tool B implementation."""
    return value * 2
''',
    }


class WatcherTestHelper:
    """Helper class for watcher tests."""

    def __init__(self, mock_indexer):
        self.mock_indexer = mock_indexer

    async def simulate_created_event(self, watcher, file_path: str) -> None:
        """Simulate a file creation event."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType

        event = FileChangeEvent(
            event_type=FileChangeType.CREATED,
            path=file_path,
            is_directory=False,
        )
        await watcher._handle_event(event)

    async def simulate_deleted_event(self, watcher, file_path: str) -> None:
        """Simulate a file deletion event."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType

        event = FileChangeEvent(
            event_type=FileChangeType.DELETED,
            path=file_path,
            is_directory=False,
        )
        await watcher._handle_event(event)

    async def simulate_changed_event(self, watcher, file_path: str) -> None:
        """Simulate a file modification event."""
        from omni.core.kernel.watcher import FileChangeEvent, FileChangeType

        event = FileChangeEvent(
            event_type=FileChangeType.CHANGED,
            path=file_path,
            is_directory=False,
        )
        await watcher._handle_event(event)

    def verify_index_file_called(self, path: str) -> None:
        """Verify index_file was called with the given path."""
        self.mock_indexer.index_file.assert_called_once_with(path)

    def verify_remove_file_called(self, path: str) -> None:
        """Verify remove_file was called with the given path."""
        self.mock_indexer.remove_file.assert_called_once_with(path)

    def verify_reindex_file_called(self, path: str) -> None:
        """Verify reindex_file was called with the given path."""
        self.mock_indexer.reindex_file.assert_called_once_with(path)


@pytest.fixture
def watcher_test_helper(mock_watcher_indexer):
    """Provide a WatcherTestHelper instance."""
    return WatcherTestHelper(mock_watcher_indexer)


# Re-export for convenience
__all__ = [
    "mock_watcher_indexer",
    "mock_watcher_indexer_with_count",
    "temp_skill_dir",
    "sample_skill_script",
    "sample_skill_with_tools",
    "WatcherTestHelper",
    "watcher_test_helper",
]
