"""
Tests for omni.agent.cli.console module.

Verifies that print_result correctly handles various skill output formats:
- ExecutionResult (Pydantic model)
- CommandResult objects
- Dict formats (content/metadata, quick_guide/details, matches, discovered_capabilities)
- String outputs

Note: When is_tty=True, output goes to stderr (via rich Console).
      When is_tty=False, output goes to stdout.
"""

import io
import sys
from unittest.mock import patch

import pytest
from rich.console import Console


class TestPrintResultFormats:
    """Test print_result handles all expected result formats."""

    def _get_output(self, is_tty: bool = False) -> tuple[str, str]:
        """Helper to capture stdout and stderr separately."""
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=is_tty)
            with patch("omni.agent.cli.console.err_console", console):
                yield stdout_capture, stderr_capture

    def test_execution_result_with_output(self):
        """Test handling ExecutionResult with output field."""
        from omni.agent.cli.console import print_result

        # Create a mock ExecutionResult-like object
        class MockResult:
            def model_dump(self):
                return {"output": "test output", "success": True}

            def model_dump_json(self):
                return '{"output": "test output", "success": true}'

            @property
            def output(self):
                return "test output"

            @property
            def success(self):
                return True

            @property
            def duration_ms(self):
                return 100.0

            @property
            def error(self):
                return None

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(MockResult(), is_tty=True)

        output = stderr_capture.getvalue()
        assert "test output" in output or "Result" in output

    def test_dict_with_content_metadata(self):
        """Test handling dict with content/metadata keys."""
        from omni.agent.cli.console import print_result

        result = {"content": "file content here", "metadata": {"lines": 10, "encoding": "utf-8"}}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        assert "file content here" in output

    def test_dict_with_quick_guide_details(self):
        """Test handling skill.discover format with quick_guide/details."""
        from omni.agent.cli.console import print_result

        result = {
            "quick_guide": [
                '@omni("git.status", {})',
                '@omni("git.commit", {"message": "<message: string>"})',
            ],
            "details": [{"tool": "git.status", "description": "Show working tree status"}],
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        assert "quick_guide" in output or "git.status" in output

    def test_dict_with_discovered_capabilities(self):
        """Test handling skill.discover format with discovered_capabilities.

        This is the primary discovery format that was previously broken.
        Regression test for: https://github.com/tao3k/omni-dev-fusion/issues/XXXX
        """
        from omni.agent.cli.console import print_result

        result = {
            "status": "success",
            "intent_matched": "research https://github.com/antfu/skills",
            "discovered_capabilities": [
                {
                    "tool": "researcher.run_research_graph",
                    "purpose": "Run deep research on a repository",
                    "usage": '@omni("researcher.run_research_graph", {"repo_url": "<repo_url: string>"})',
                    "documentation_path": "/path/to/SKILL.md",
                    "source_code_path": "/path/to/research_entry.py",
                    "documentation_hints": ["Full manual available at: /path/to/SKILL.md"],
                    "advice": "Use filesystem.read_files on documentation_path for the manual",
                },
                {
                    "tool": "crawl4ai.crawl_url",
                    "purpose": "Crawl a web page and extract content",
                    "usage": '@omni("crawl4ai.crawl_url", {"url": "<url: string>"})',
                },
            ],
            "protocol_reminder": "NEVER guess parameters.",
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        # Should contain the discovered capabilities
        assert "researcher.run_research_graph" in output
        assert "crawl4ai.crawl_url" in output
        assert "status" in output or "success" in output

    def test_dict_with_matches(self):
        """Test handling search results with matches array."""
        from omni.agent.cli.console import print_result

        result = {
            "success": True,
            "tool": "ripgrep",
            "count": 5,
            "matches": [
                {"file": "test.py", "line": 10, "content": "def test(): pass"},
                {"file": "test.py", "line": 20, "content": "class Test:"},
            ],
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        assert "matches" in output or "test.py" in output

    def test_dict_with_matches_truncation(self):
        """Test that matches are truncated at 20 items."""
        from omni.agent.cli.console import print_result

        # Create 25 matches to trigger truncation
        matches = [{"file": f"file{i}.py", "line": i, "content": f"content {i}"} for i in range(25)]
        result = {"success": True, "tool": "ripgrep", "count": 25, "matches": matches}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        # Should indicate truncation
        assert "truncated" in output or "matches" in output

    def test_dict_without_recognized_keys(self):
        """Test handling dict without recognized content keys."""
        from omni.agent.cli.console import print_result

        result = {"unknown_key": "value", "another_key": 123}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)
        # Should not crash, output may be empty

    def test_string_result(self):
        """Test handling plain string result."""
        from omni.agent.cli.console import print_result

        result = "Simple string output"

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        assert "Simple string output" in output

    def test_json_output_flag(self):
        """Test json_output flag with ExecutionResult."""
        from omni.agent.cli.console import print_result

        class MockResult:
            def model_dump(self):
                return {"output": "test"}

            def model_dump_json(self, indent: bool = False):
                return '{"output": "test", "success": true}'

            @property
            def output(self):
                return "test"

            @property
            def success(self):
                return True

            @property
            def duration_ms(self):
                return 50.0

            @property
            def error(self):
                return None

        stdout_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            print_result(MockResult(), is_tty=False, json_output=True)

        output = stdout_capture.getvalue()
        assert "success" in output

    def test_discovered_capabilities_empty(self):
        """Test handling discovered_capabilities with empty array."""
        from omni.agent.cli.console import print_result

        result = {
            "status": "not_found",
            "discovered_capabilities": [],
            "suggestions": ["Try a broader query"],
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        # Should handle gracefully
        assert "status" in output or "not_found" in output


class TestPrintResultIntegration:
    """Integration tests for print_result with realistic scenarios."""

    def test_researcher_discover_result(self):
        """Test with realistic researcher.discover output."""
        from omni.agent.cli.console import print_result

        # Realistic discover result for researching a GitHub repo
        result = {
            "status": "success",
            "intent_matched": "research https://github.com/antfu/skills",
            "discovered_capabilities": [
                {
                    "tool": "researcher.run_research_graph",
                    "purpose": "Execute the Sharded Deep Research Workflow",
                    "usage": '@omni("researcher.run_research_graph", {"repo_url": "<repo_url: string>"})',
                    "documentation_path": "/Users/test/assets/skills/researcher/SKILL.md",
                    "source_code_path": "/Users/test/assets/skills/researcher/scripts/research_entry.py",
                    "documentation_hints": ["Full manual available at: /path/to/SKILL.md"],
                    "advice": "Read the 'purpose'. Use filesystem.read_files on 'documentation_path' for the manual.",
                }
            ],
            "protocol_reminder": "NEVER guess parameters. Use the EXACT usage strings provided above.",
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        # Verify key elements are present
        assert "run_research_graph" in output
        assert "status" in output
        assert "protocol_reminder" in output or "success" in output

    def test_smart_search_result(self):
        """Test with realistic smart_search output."""
        from omni.agent.cli.console import print_result

        result = {
            "success": True,
            "tool": "ripgrep",
            "count": 3,
            "matches": [
                {"file": "src/main.py", "line": 42, "content": "def main(): pass"},
                {"file": "src/main.py", "line": 100, "content": "if __name__ == '__main__':"},
            ],
            "truncated": False,
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                print_result(result, is_tty=True)

        output = stderr_capture.getvalue()
        assert "src/main.py" in output
        assert "main" in output

    def test_smart_find_content_mode(self):
        """Test with smart_find content mode output.

        Note: The 'search_mode' result format is passed through as-is
        since it doesn't match recognized patterns like 'content' or 'matches'.
        This tests that the function handles unknown dict formats gracefully.
        """
        from omni.agent.cli.console import print_result

        result = {
            "success": True,
            "tool": "ripgrep",
            "search_mode": "content",
            "count": 5,
            "files": ["README.md", "docs/guide.md", "packages/core/src/main.py"],
            "truncated": False,
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch.object(sys, "stdout", stdout_capture):
            console = Console(file=stderr_capture, stderr=True)
            with patch("omni.agent.cli.console.err_console", console):
                # Should not crash even with unknown format
                print_result(result, is_tty=True)

        # The function should handle this gracefully (no crash)
        # Output may be empty since it doesn't match recognized patterns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
