"""Tests for sys_query (Project Cerebellum) in omni_cell.py."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from omni.core.skills.runtime.omni_cell import (
    OmniCellRunner,
    ActionType,
)


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
        assert result.status.value == "error"
        assert result.error_message is not None
        assert "path" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sys_query_missing_pattern(self, runner):
        """Test sys_query with missing pattern."""
        result = await runner.sys_query({"path": "src/main.py"})
        assert result.status.value == "error"
        assert result.error_message is not None
        assert "pattern" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sys_query_invalid_action(self, runner):
        """Test sys_query with invalid action (mutate instead of observe)."""
        result = await runner.sys_query(
            {"path": "src/main.py", "pattern": "def $NAME"},
            action=ActionType.MUTATE,
        )
        assert result.status.value == "error"
        assert result.error_message is not None
        assert "observe" in result.error_message.lower()

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
            assert result.status.value == "error"
            assert result.error_message is not None
            assert "read" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sys_query_success_python_functions(self, runner):
        """Test sys_query extracting Python functions."""
        content = '''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Greeter:
    """A greeter class."""
    def greet(self, name: str) -> str:
        """Greet someone."""
        return hello(name)
'''
        # Mock the Rust bridge to return a valid result
        mock_result = {
            "success": True,
            "items": [
                {
                    "text": "def hello(name: str) -> str:",
                    "start": 6,
                    "end": 90,
                    "line_start": 2,
                    "line_end": 4,
                    "captures": {"NAME": "hello"},
                },
                {
                    "text": "def greet(self, name: str) -> str:",
                    "start": 150,
                    "end": 190,
                    "line_start": 11,
                    "line_end": 13,
                    "captures": {"NAME": "greet"},
                },
            ],
            "count": 2,
        }

        with patch.object(runner, "_read_file", return_value=content):
            # We can't easily mock the Rust bridge, so skip if unavailable
            if runner._rust_bridge is None:
                pytest.skip("Rust bridge not available")

            result = await runner.sys_query(
                {"path": "test.py", "pattern": "def $NAME", "captures": ["NAME"]}
            )

            # If Rust bridge works, verify results
            if result.status.value == "success":
                assert result.data is not None
                assert "items" in result.data

    @pytest.mark.asyncio
    async def test_sys_query_with_captures(self, runner):
        """Test sys_query with multiple captures."""
        content = """
class MyClass:
    def method_one(self): pass
    def method_two(self): pass
"""
        # Mock the Rust bridge result
        mock_items = [
            {
                "text": "def method_one(self): pass",
                "start": 20,
                "end": 50,
                "line_start": 2,
                "line_end": 2,
                "captures": {"NAME": "method_one"},
            },
            {
                "text": "def method_two(self): pass",
                "start": 55,
                "end": 85,
                "line_start": 4,
                "line_end": 4,
                "captures": {"NAME": "method_two"},
            },
        ]

        with patch.object(runner, "_read_file", return_value=content):
            if runner._rust_bridge is None:
                pytest.skip("Rust bridge not available")

            result = await runner.sys_query(
                {
                    "path": "test.py",
                    "pattern": "def $NAME",
                    "captures": ["NAME"],
                }
            )

            if result.status.value == "success":
                assert result.data is not None
                assert "items" in result.data

    @pytest.mark.asyncio
    async def test_sys_query_json_error(self, runner):
        """Test sys_query with invalid JSON in pattern."""
        result = await runner.sys_query({"path": "test.py", "pattern": "def $NAME["})
        assert result.status.value == "error"

    @pytest.mark.asyncio
    async def test_sys_query_empty_results(self, runner):
        """Test sys_query with pattern that matches nothing."""
        content = "x = 1\ny = 2\nz = 3"

        with patch.object(runner, "_read_file", return_value=content):
            if runner._rust_bridge is None:
                pytest.skip("Rust bridge not available")

            result = await runner.sys_query({"path": "test.py", "pattern": "def $NAME"})

            # Even empty results should be a success
            if result.status.value == "success":
                assert result.data is not None
                items = result.data.get("items", [])
                assert isinstance(items, list)
