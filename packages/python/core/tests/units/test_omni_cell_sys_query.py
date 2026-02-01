"""Tests for sys_query (Project Cerebellum) in omni_cell.py."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from omni.core.skills.runtime.omni_cell import (
    OmniCellRunner,
    SysQueryResult,
    sys_query,
    ActionType,
)


class TestSysQueryResult:
    """Tests for SysQueryResult model."""

    def test_default_values(self):
        """Test default values for SysQueryResult."""
        result = SysQueryResult(success=True)
        assert result.success is True
        assert result.items == []
        assert result.count == 0
        assert result.error is None

    def test_with_items(self):
        """Test SysQueryResult with extracted items."""
        items = [
            {
                "text": "def hello(): pass",
                "start": 0,
                "end": 22,
                "line_start": 1,
                "line_end": 1,
                "captures": {"NAME": "hello"},
            }
        ]
        result = SysQueryResult(success=True, items=items, count=1)
        assert result.success is True
        assert len(result.items) == 1
        assert result.count == 1

    def test_with_error(self):
        """Test SysQueryResult with error."""
        result = SysQueryResult(success=False, error="File not found")
        assert result.success is False
        assert result.error == "File not found"


class TestOmniCellRunnerSysQuery:
    """Tests for OmniCellRunner.sys_query method."""

    @pytest_asyncio.fixture
    async def runner(self):
        """Create a runner for testing."""
        return OmniCellRunner()

    @pytest.mark.asyncio
    async def test_sys_query_missing_path(self, runner):
        """Test sys_query with missing path."""
        result = await runner.sys_query({"pattern": "def $NAME"})
        assert result.success is False
        assert "path" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sys_query_missing_pattern(self, runner):
        """Test sys_query with missing pattern."""
        result = await runner.sys_query({"path": "src/main.py"})
        assert result.success is False
        assert "pattern" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sys_query_invalid_action(self, runner):
        """Test sys_query with invalid action."""
        result = await runner.sys_query(
            {"path": "src/main.py", "pattern": "def $NAME"},
            action=ActionType.MUTATE,
        )
        assert result.success is False
        assert "observe" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sys_query_file_not_found(self, runner):
        """Test sys_query with non-existent file."""
        with patch.object(runner, "_read_file", return_value=None):
            result = await runner.sys_query(
                {
                    "path": "/nonexistent/file.py",
                    "pattern": "def $NAME",
                }
            )
            assert result.success is False
            assert "failed to read" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sys_query_success_python_functions(self, runner):
        """Test sys_query extracting Python functions."""
        content = '''
def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

def goodbye():
    pass
'''

        with patch.object(runner, "_read_file", return_value=content):
            with patch("omni_core_rs.py_extract_items") as mock_extract:
                mock_extract.return_value = json.dumps(
                    [
                        {
                            "text": "def hello(name: str) -> str:",
                            "start": 0,
                            "end": 35,
                            "line_start": 2,
                            "line_end": 4,
                            "captures": {"NAME": "hello"},
                        },
                        {
                            "text": "def goodbye():",
                            "start": 70,
                            "end": 85,
                            "line_start": 7,
                            "line_end": 8,
                            "captures": {"NAME": "goodbye"},
                        },
                    ]
                )

                result = await runner.sys_query(
                    {
                        "path": "src/main.py",
                        "pattern": "def $NAME",
                        "language": "python",
                        "captures": ["NAME"],
                    }
                )

                assert result.success is True
                assert result.count == 2
                assert len(result.items) == 2
                assert result.items[0]["captures"]["NAME"] == "hello"
                assert result.items[1]["captures"]["NAME"] == "goodbye"

    @pytest.mark.asyncio
    async def test_sys_query_with_captures(self, runner):
        """Test sys_query with specific captures."""
        content = "def hello(name: str): pass"

        with patch.object(runner, "_read_file", return_value=content):
            with patch("omni_core_rs.py_extract_items") as mock_extract:
                mock_extract.return_value = json.dumps(
                    [
                        {
                            "text": "def hello(name: str): pass",
                            "start": 0,
                            "end": 30,
                            "line_start": 1,
                            "line_end": 1,
                            "captures": {"NAME": "hello"},
                        },
                    ]
                )

                result = await runner.sys_query(
                    {
                        "path": "src/main.py",
                        "pattern": "def $NAME",
                        "captures": ["NAME"],
                    }
                )

                mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_sys_query_json_error(self, runner):
        """Test sys_query handling JSON decode errors."""
        content = "def hello(): pass"

        with patch.object(runner, "_read_file", return_value=content):
            with patch("omni_core_rs.py_extract_items") as mock_extract:
                mock_extract.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

                result = await runner.sys_query(
                    {
                        "path": "src/main.py",
                        "pattern": "def $NAME",
                    }
                )

                assert result.success is False
                assert "json" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sys_query_empty_results(self, runner):
        """Test sys_query with no matches."""
        content = "x = 42"

        with patch.object(runner, "_read_file", return_value=content):
            with patch("omni_core_rs.py_extract_items") as mock_extract:
                mock_extract.return_value = json.dumps([])

                result = await runner.sys_query(
                    {
                        "path": "src/main.py",
                        "pattern": "def $NAME",
                    }
                )

                assert result.success is True
                assert result.count == 0
                assert result.items == []


class TestSysQueryConvenienceFunction:
    """Tests for the module-level sys_query function."""

    @pytest.mark.asyncio
    async def test_sys_query_convenience_function(self):
        """Test the module-level sys_query convenience function."""
        with patch("omni.core.skills.runtime.omni_cell.get_runner") as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.sys_query = AsyncMock(
                return_value=SysQueryResult(
                    success=True,
                    count=1,
                    items=[{"text": "def test(): pass"}],
                )
            )
            mock_get_runner.return_value = mock_runner

            result = await sys_query(
                {
                    "path": "src/test.py",
                    "pattern": "def $NAME",
                }
            )

            assert result.success is True
            mock_runner.sys_query.assert_called_once()


class TestReadFile:
    """Tests for file reading methods."""

    @pytest_asyncio.fixture
    async def runner(self):
        """Create a runner for testing."""
        return OmniCellRunner()

    @pytest.mark.asyncio
    async def test_read_file_with_rust_bridge(self, runner):
        """Test reading file via Rust bridge."""
        with patch("omni_core_rs.read_file_safe") as mock_read:
            mock_read.return_value = "file content"

            content = await runner._read_file("src/main.py")
            assert content == "file content"

    @pytest.mark.asyncio
    async def test_read_file_fallback_on_error(self, runner):
        """Test fallback to async reading on Rust bridge error."""
        with patch("omni_core_rs.read_file_safe") as mock_read:
            mock_read.return_value = "Error: file not found"

            with patch.object(runner, "_read_file_async", new_callable=AsyncMock) as mock_async:
                mock_async.return_value = "async content"

                content = await runner._read_file("src/main.py")
                assert content == "async content"
                mock_async.assert_called_once_with("src/main.py")
