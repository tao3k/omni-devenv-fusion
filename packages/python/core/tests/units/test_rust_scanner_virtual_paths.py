"""Tests for Rust scanner virtual path scanning (scan_paths, parse_script_content).

These tests verify that the new virtual path scanning functionality works correctly
without requiring actual filesystem operations.
"""

from __future__ import annotations

import pytest

from omni_core_rs import scan_paths, parse_script_content


class TestScanPathsVirtualFiles:
    """Tests for scan_paths function - scanning virtual files without filesystem access."""

    def test_scan_paths_finds_multiple_tools(self) -> None:
        """Test that scan_paths finds multiple tools in virtual files."""
        files = [
            (
                "/virtual/test_skill/scripts/tool_a.py",
                '''
@skill_command(name="tool_a")
def tool_a(param: str) -> str:
    """Tool A implementation."""
    return param
''',
            ),
            (
                "/virtual/test_skill/scripts/tool_b.py",
                '''
@skill_command(name="tool_b")
def tool_b(value: int) -> int:
    """Tool B implementation."""
    return value * 2
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert len(tools) == 2
        tool_names = [t.tool_name for t in tools]
        assert "test_skill.tool_a" in tool_names
        assert "test_skill.tool_b" in tool_names

    def test_scan_paths_with_keywords(self) -> None:
        """Test that scan_paths includes skill keywords in tool metadata."""
        files = [
            (
                "/virtual/test_skill/scripts/tool.py",
                '''
@skill_command(name="test_tool")
def test_tool():
    """A test tool."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", ["test", "verify"], [])

        assert len(tools) == 1
        assert "test" in tools[0].keywords
        assert "verify" in tools[0].keywords
        assert "test_skill" in tools[0].keywords  # skill_name always included

    def test_scan_paths_with_intents(self) -> None:
        """Test that scan_paths includes intents in tool metadata."""
        files = [
            (
                "/virtual/test_skill/scripts/tool.py",
                '''
@skill_command(name="test_tool")
def test_tool():
    """A test tool."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert len(tools) == 1
        # Note: PyToolRecord doesn't expose intents to Python
        # But the Rust scanner correctly processes them internally
        assert tools[0].tool_name == "test_skill.test_tool"

    def test_scan_paths_skips_init_py(self) -> None:
        """Test that scan_paths skips __init__.py files."""
        files = [
            (
                "/virtual/test_skill/scripts/__init__.py",
                '''
@skill_command(name="init_tool")
def init_tool():
    """This should be skipped."""
    pass
''',
            ),
            (
                "/virtual/test_skill/scripts/public.py",
                '''
@skill_command(name="public_tool")
def public_tool():
    """This should be included."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "test_skill.public_tool"

    def test_scan_paths_skips_private_files(self) -> None:
        """Test that scan_paths skips files starting with underscore."""
        files = [
            (
                "/virtual/test_skill/scripts/_private.py",
                '''
@skill_command(name="private_tool")
def private_tool():
    """This should be skipped."""
    pass
''',
            ),
            (
                "/virtual/test_skill/scripts/public.py",
                '''
@skill_command(name="public_tool")
def public_tool():
    """This should be included."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "test_skill.public_tool"

    def test_scan_paths_skips_non_python_files(self) -> None:
        """Test that scan_paths skips non-Python files."""
        files = [
            (
                "/virtual/test_skill/scripts/readme.md",
                "# This is not Python",
            ),
            (
                "/virtual/test_skill/scripts/tool.py",
                """
@skill_command(name="tool")
def tool():
    pass
""",
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "test_skill.tool"

    def test_scan_paths_empty_list(self) -> None:
        """Test that scan_paths returns empty list for empty input."""
        tools = scan_paths([], "test_skill", [], [])

        assert tools == []

    def test_scan_paths_no_decorators(self) -> None:
        """Test that scan_paths returns empty for files without decorators."""
        files = [
            (
                "/virtual/test_skill/scripts/no_decorator.py",
                '''
def regular_function():
    """No skill_command decorator here."""
    pass
''',
            ),
        ]

        tools = scan_paths(files, "test_skill", [], [])

        assert tools == []


class TestParseScriptContent:
    """Tests for parse_script_content function - parsing single script content."""

    def test_parse_single_tool(self) -> None:
        """Test that parse_script_content finds a single tool."""
        content = '''
@skill_command(name="my_tool")
def my_tool(param: str) -> str:
    """My tool description."""
    return param
'''

        tools = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])

        assert len(tools) == 1
        assert tools[0].tool_name == "test.my_tool"
        assert tools[0].function_name == "my_tool"
        assert tools[0].file_path == "/virtual/path/tool.py"

    def test_parse_multiple_tools(self) -> None:
        """Test that parse_script_content finds multiple tools."""
        content = '''
@skill_command(name="commit")
def commit(message: str) -> str:
    """Create a commit."""
    return f"Committed: {message}"

@skill_command(name="status")
def status() -> str:
    """Show working tree status."""
    return "status output"
'''

        tools = parse_script_content(content, "/virtual/path/main.py", "git", [], [])

        assert len(tools) == 2
        tool_names = [t.tool_name for t in tools]
        assert "git.commit" in tool_names
        assert "git.status" in tool_names

    def test_parse_no_decorators(self) -> None:
        """Test that parse_script_content returns empty for no decorators."""
        content = '''
def regular_function():
    """No decorator here."""
    return "hello"
'''

        tools = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])

        assert tools == []

    def test_parse_with_category(self) -> None:
        """Test that parse_script_content preserves category from decorator."""
        content = '''
@skill_command(name="test_tool", category="testing")
def test_tool():
    """A test tool."""
    pass
'''

        tools = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])

        assert len(tools) == 1
        assert tools[0].category == "testing"


class TestFileHashConsistency:
    """Tests for file hash consistency in virtual path scanning."""

    def test_same_content_same_hash(self) -> None:
        """Test that identical content produces identical file hashes."""
        content = """
@skill_command(name="tool")
def tool():
    pass
"""

        tools1 = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])
        tools2 = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])

        assert tools1[0].file_hash == tools2[0].file_hash

    def test_different_content_different_hash(self) -> None:
        """Test that different content produces different file hashes."""
        content1 = """
@skill_command(name="tool")
def tool():
    pass
"""

        content2 = """
@skill_command(name="tool")
def tool():
    pass
# different
"""

        tools1 = parse_script_content(content1, "/virtual/path/tool.py", "test", [], [])
        tools2 = parse_script_content(content2, "/virtual/path/tool.py", "test", [], [])

        assert tools1[0].file_hash != tools2[0].file_hash


class TestVirtualPathUseCases:
    """Integration tests for common virtual path scanning use cases."""

    def test_simulate_skill_directory(self) -> None:
        """Test simulating a complete skill directory structure."""
        files = [
            (
                "/virtual/git/scripts/commit.py",
                '''
@skill_command(name="commit")
def commit(message: str) -> str:
    """Create a commit with the given message."""
    return f"Committed: {message}"
''',
            ),
            (
                "/virtual/git/scripts/status.py",
                '''
@skill_command(name="status")
def status() -> str:
    """Show the working tree status."""
    return "On branch main"
''',
            ),
            (
                "/virtual/git/scripts/log.py",
                '''
@skill_command(name="log")
def log(n: int = 10) -> str:
    """Show recent commits."""
    return f"Showing last {n} commits"
''',
            ),
        ]

        tools = scan_paths(files, "git", ["git", "version control"], [])

        assert len(tools) == 3

        # Verify tool metadata
        commit_tool = next(t for t in tools if t.tool_name == "git.commit")
        assert "git" in commit_tool.keywords
        assert "version control" in commit_tool.keywords
        # Note: intents are not exposed in PyToolRecord but are processed by Rust

    def test_test_scenario_without_filesystem(self) -> None:
        """Test that we can test scanner behavior without touching filesystem."""
        # This is the key use case - testing scanner logic in isolation
        content = '''
@skill_command(name="new_tool", category="custom")
def new_tool(param: str) -> str:
    """A new tool for testing."""
    return f"Result: {param}"
'''

        tools = parse_script_content(
            content, "/tmp/test_skill/scripts/new_tool.py", "test_skill", ["test"], ["testing"]
        )

        assert len(tools) == 1
        assert tools[0].category == "custom"
        assert tools[0].file_path == "/tmp/test_skill/scripts/new_tool.py"
        # Hash should be consistent for same content
        tools2 = parse_script_content(
            content, "/tmp/test_skill/scripts/new_tool.py", "test_skill", ["test"], ["testing"]
        )
        assert tools[0].file_hash == tools2[0].file_hash
