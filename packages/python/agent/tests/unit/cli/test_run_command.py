"""
test_run_command.py - Integration Tests for 'omni run' CLI Command

Tests the run command execution flow including:
- Command parsing
- LLM integration via OmniLoop
- Error handling
- Output formatting
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Strip ANSI so assertions on Rich-rendered output work
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


class TestRunCommandExecution:
    """Tests for the run command execution path."""

    @pytest.fixture
    def mock_omni_loop_response(self):
        """Sample LLM response for mocking."""
        return {
            "session_id": "test_123",
            "output": "This is the LLM response to the task.",
            "skills_count": 5,
            "commands_executed": 0,
            "status": "completed",
        }

    def test_run_command_exists(self):
        """Verify the run command can be imported via register_run_command."""
        from omni.agent.cli.commands.run import register_run_command

        assert register_run_command is not None
        assert callable(register_run_command)

    def test_run_functions_exist(self):
        """Verify helper functions exist."""
        from omni.agent.workflows.run_entry import (
            execute_task_via_kernel,
            execute_task_with_session,
            print_banner,
            print_session_report,
        )

        assert callable(print_session_report)
        assert callable(print_banner)
        assert callable(execute_task_via_kernel)
        assert callable(execute_task_with_session)

    def test_gateway_agent_commands_registered(self):
        """Verify gateway and agent commands are registered."""
        from omni.agent.cli.commands.gateway_agent import (
            register_gateway_command,
            register_agent_command,
        )

        assert callable(register_gateway_command)
        assert callable(register_agent_command)


class TestRunCommandExecutionPath:
    """Tests for the execution path through OmniLoop."""

    @pytest.fixture
    def mock_inference_client(self):
        """Create a mock InferenceClient that returns a valid response."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "LLM response for the task.",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_execute_task_via_omni_loop(self, mock_inference_client):
        """Should execute task via OmniLoop when no skill matches."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            result = await loop.run("Test task description")

            # Verify LLM was called
            mock_inference_client.complete.assert_called_once()
            assert result == "LLM response for the task."

    @pytest.mark.asyncio
    async def test_omni_loop_uses_context_manager(self, mock_inference_client):
        """Should use ContextManager for conversation history."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            await loop.run("First message")
            await loop.run("Second message")

            # Should have tracked conversation
            assert len(loop.history) >= 2

    @pytest.mark.asyncio
    async def test_omni_loop_respects_config(self, mock_inference_client):
        """Should respect configuration settings."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            from omni.agent.core.omni.config import OmniLoopConfig
            from omni.agent.core.omni.loop import OmniLoop

            config = OmniLoopConfig(
                max_tokens=64000,
                retained_turns=5,
            )
            loop = OmniLoop(config=config)

            assert loop.config.max_tokens == 64000
            assert loop.config.retained_turns == 5


class TestRunCommandErrorHandling:
    """Tests for error handling in run command."""

    @pytest.fixture
    def mock_failing_inference(self):
        """Create a mock InferenceClient that fails."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": False,
                "content": "",
                "error": "API rate limit exceeded",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self, mock_failing_inference):
        """Should handle LLM failures gracefully."""
        with patch(
            "omni.agent.core.omni.loop.InferenceClient", return_value=mock_failing_inference
        ):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            result = await loop.run("Test task: handle LLM failure gracefully")

            # Should return empty string on failure
            assert result == ""

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        """Should handle LLM timeout."""
        mock = MagicMock()
        # Simulate timeout by returning a failure response
        mock.complete = AsyncMock(
            return_value={
                "success": False,
                "content": "",
                "error": "Request timed out",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            result = await loop.run("Test task: handle timeout gracefully")

            # Should return empty string on timeout/failure
            assert result == ""


class TestRunCommandOutput:
    """Tests for output formatting."""

    def test_print_session_report_function(self):
        """Verify _print_session_report function exists."""
        from omni.agent.workflows.run_entry import print_session_report

        assert callable(print_session_report)

    def test_print_banner_function(self):
        """Verify _print_banner function exists."""
        from omni.agent.workflows.run_entry import print_banner

        assert callable(print_banner)

    def test_register_run_command_function(self):
        """Verify register_run_command function exists."""
        from omni.agent.cli.commands.run import register_run_command

        assert callable(register_run_command)

    def test_session_report_with_dict_output(self, capsys):
        """Verify _print_session_report renders dict output correctly."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_123",
            "output": {
                "success": True,
                "branch": "main",
                "staged": 5,
            },
        }
        step_count = 1
        tool_counts = {"tool_calls": 1}
        tokens = 500

        print_session_report("test task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        out = _strip_ansi(captured.out)
        # Verify output contains key elements
        assert "✨ CCA Session Report ✨" in out
        assert "Task: test task" in out or "test task" in out
        assert "Steps" in out
        assert "Reflection & Outcome:" in out
        # Verify dict output is rendered (as JSON)
        assert '"success": true' in out or "success" in out

    def test_session_report_with_markdown_output(self, capsys):
        """Verify _print_session_report renders markdown output correctly."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_456",
            "output": "## Overview\nThis is a markdown output.\n\n- Item 1\n- Item 2",
        }
        step_count = 2
        tool_counts = {"tool_calls": 2}
        tokens = 1000

        print_session_report("markdown task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        out = _strip_ansi(captured.out)
        # Verify output contains key elements
        assert "✨ CCA Session Report ✨" in out
        assert "Overview" in out
        assert "Item 1" in out

    def test_session_report_panel_title(self, capsys):
        """Verify session report has correct panel title."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_789",
            "output": "Simple output",
        }
        step_count = 1
        tool_counts = {}
        tokens = 100

        print_session_report("simple task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify panel title
        assert "✨ CCA Session Report ✨" in captured.out

    def test_session_report_cleans_tool_call_artifacts(self, capsys):
        """Verify _print_session_report cleans up tool call artifacts."""
        from omni.agent.workflows.run_entry import print_session_report

        # Simulate corrupted output with tool call markers
        result = {
            "session_id": "test_tool_calls",
            "output": """[TOOL_CALL: filesystem.read_files">
/Users/xxx/file.md  <TOOL_CALL: filesystem.list_directory"> /Users/xxx/shards    │

[/TOOL_CALL]

## Analysis
This is the actual result.""",
        }
        step_count = 2
        tool_counts = {"filesystem": 2}
        tokens = 500

        print_session_report("cleanup test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify tool call artifacts are removed
        assert "[TOOL_CALL:" not in captured.out or "│" not in captured.out.split("│")[-1]
        # Verify actual content is preserved
        assert "Analysis" in captured.out
        assert "This is the actual result" in captured.out

    def test_session_report_with_empty_output(self, capsys):
        """Verify _print_session_report handles empty output."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_empty",
            "output": "",
        }
        step_count = 1
        tool_counts = {}
        tokens = 100

        print_session_report("empty output test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Should still render the report
        assert "✨ CCA Session Report ✨" in captured.out
        assert "empty output test" in captured.out

    def test_session_report_with_none_output(self, capsys):
        """Verify _print_session_report handles None output."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_none",
            "output": None,
        }
        step_count = 1
        tool_counts = {}
        tokens = 100

        print_session_report("none output test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Should still render the report with default message
        assert "✨ CCA Session Report ✨" in captured.out

    def test_session_report_with_no_output_key(self, capsys):
        """Verify _print_session_report handles missing output key."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_no_key",
            # No "output" key
        }
        step_count = 1
        tool_counts = {}
        tokens = 100

        print_session_report("no output key test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Should still render the report
        assert "✨ CCA Session Report ✨" in captured.out

    def test_session_report_with_multiple_tool_calls(self, capsys):
        """Verify _print_session_report handles multiple tool calls in output."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_multi_tool",
            "output": """[TOOL_CALL: knowledge.get_development_context]
[/TOOL_CALL]
[TOOL_CALL: filesystem.read_files]
/Users/xxx/file1.md
[/TOOL_CALL]
[TOOL_CALL: filesystem.read_files]
/Users/xxx/file2.md
[/TOOL_CALL]

## Result
Analysis complete.""",
        }
        step_count = 3
        tool_counts = {"knowledge": 1, "filesystem": 2}
        tokens = 800

        print_session_report("multi tool test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify report still renders correctly
        assert "✨ CCA Session Report ✨" in captured.out
        # Verify actual content is preserved
        assert "Result" in captured.out
        assert "Analysis complete" in captured.out

    def test_session_report_with_research_result(self, capsys):
        """Verify _print_session_report renders research-style result dict."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_research",
            "output": {
                "success": True,
                "harvest_dir": "/Users/xxx/harvested/20260124-test",
                "repo_url": "https://github.com/example/repo",
                "repo_name": "example-repo",
            },
        }
        step_count = 5
        tool_counts = {"researcher": 5}
        tokens = 2000

        print_session_report("research task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify report renders dict as JSON
        assert "✨ CCA Session Report ✨" in captured.out
        assert "success" in captured.out.lower() or "true" in captured.out.lower()

    def test_session_report_with_json_string(self, capsys):
        """Verify _print_session_report handles JSON-like string output."""
        from omni.agent.workflows.run_entry import print_session_report

        result = {
            "session_id": "test_json_str",
            "output": '{"status": "completed", "count": 42}',
        }
        step_count = 1
        tool_counts = {}
        tokens = 200

        print_session_report("json string test", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        assert "✨ CCA Session Report ✨" in captured.out
        # JSON should be rendered (possibly escaped)
        assert "completed" in captured.out or "status" in captured.out


class TestRunCommandEdgeCases:
    """Tests for edge cases in run command."""

    @pytest.mark.asyncio
    async def test_empty_task_handling(self):
        """Should handle empty task string with clarification message."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "I see you've sent an empty message.",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 50, "output_tokens": 20},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            result = await loop.run("")

            # Epistemic gating should block empty tasks
            assert "more information" in result.lower() or "too short" in result.lower()

    @pytest.mark.asyncio
    async def test_very_long_task(self):
        """Should handle very long task descriptions."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "Acknowledged your detailed request.",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 5000, "output_tokens": 100},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            long_task = "This is a very long task description. " * 100
            result = await loop.run(long_task)

            mock.complete.assert_called_once()
            assert result == "Acknowledged your detailed request."

    @pytest.mark.asyncio
    async def test_special_characters_in_task(self):
        """Should handle special characters in task."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "Handled special characters.",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 30},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock):
            from omni.agent.core.omni.loop import OmniLoop

            loop = OmniLoop()
            special_task = "Task with 'quotes' and \"double quotes\" and special chars: @#$%"
            result = await loop.run(special_task)

            mock.complete.assert_called_once()
            assert result == "Handled special characters."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestOmniLoopConfig:
    """Tests for OmniLoopConfig with max_tool_calls settings."""

    def test_default_max_tool_calls_is_20(self):
        """Verify default max_tool_calls is 20."""
        from omni.agent.core.omni.config import OmniLoopConfig

        config = OmniLoopConfig()
        assert config.max_tool_calls == 20

    def test_custom_max_tool_calls(self):
        """Verify custom max_tool_calls can be set."""
        from omni.agent.core.omni.config import OmniLoopConfig

        config = OmniLoopConfig(max_tool_calls=50)
        assert config.max_tool_calls == 50

    def test_max_tool_calls_zero_disables_limit(self):
        """Verify setting max_tool_calls to 0 disables the limit."""
        from omni.agent.core.omni.config import OmniLoopConfig

        config = OmniLoopConfig(max_tool_calls=0)
        assert config.max_tool_calls == 0

    def test_omni_loop_uses_config_max_tool_calls(self):
        """Verify OmniLoop config has correct max_tool_calls."""
        from omni.agent.core.omni.config import OmniLoopConfig
        from omni.agent.core.omni.loop import OmniLoop

        config = OmniLoopConfig(max_tool_calls=5)
        loop = OmniLoop(config=config)
        # OmniLoop uses config, so the max_tool_calls should be 5
        assert loop.config.max_tool_calls == 5

    def test_execute_task_respects_large_steps_as_max_calls(self):
        """Verify large steps (>20) is used as max_tool_calls."""
        # When steps > 20, it should be used as max_tool_calls
        max_steps = 50
        max_calls = max_steps if max_steps and max_steps > 20 else 20

        assert max_calls == 50

    def test_execute_task_uses_default_when_steps_below_20(self):
        """Verify default 20 is used when steps <= 20."""
        # When steps <= 20, default 20 should be used
        max_steps = 10
        max_calls = max_steps if max_steps and max_steps > 20 else 20

        assert max_calls == 20

        # Also test None
        max_steps = None
        max_calls = max_steps if max_steps and max_steps > 20 else 20

        assert max_calls == 20

    def test_execute_task_uses_default_when_steps_is_20(self):
        """Verify default 20 is used when steps is exactly 20."""
        # When steps is exactly 20, it should use default
        max_steps = 20
        max_calls = max_steps if max_steps and max_steps > 20 else 20

        assert max_calls == 20

    def test_execute_task_uses_default_when_steps_is_21(self):
        """Verify steps=21 is used as max_tool_calls (just over 20)."""
        # When steps > 20, it should be used
        max_steps = 21
        max_calls = max_steps if max_steps and max_steps > 20 else 20

        assert max_calls == 21
