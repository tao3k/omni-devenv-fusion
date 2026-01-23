"""
test_run_command.py - Integration Tests for 'omni run' CLI Command

Tests the run command execution flow including:
- Command parsing
- LLM integration via OmniLoop
- Error handling
- Output formatting
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
        from omni.agent.cli.commands.run import (
            _print_session_report,
            _print_banner,
            _run_repl,
            _execute_task_via_kernel,
        )

        assert callable(_print_session_report)
        assert callable(_print_banner)
        assert callable(_run_repl)
        assert callable(_execute_task_via_kernel)


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
            from omni.agent.core.omni.loop import OmniLoop
            from omni.agent.core.omni.config import OmniLoopConfig

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
            result = await loop.run("Test task")

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
            result = await loop.run("Test task")

            # Should return empty string on timeout/failure
            assert result == ""


class TestRunCommandOutput:
    """Tests for output formatting."""

    def test_print_session_report_function(self):
        """Verify _print_session_report function exists."""
        from omni.agent.cli.commands.run import _print_session_report

        assert callable(_print_session_report)

    def test_print_banner_function(self):
        """Verify _print_banner function exists."""
        from omni.agent.cli.commands.run import _print_banner

        assert callable(_print_banner)

    def test_register_run_command_function(self):
        """Verify register_run_command function exists."""
        from omni.agent.cli.commands.run import register_run_command

        assert callable(register_run_command)

    def test_session_report_with_dict_output(self, capsys):
        """Verify _print_session_report renders dict output correctly."""
        from omni.agent.cli.commands.run import _print_session_report

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

        _print_session_report("test task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify output contains key elements
        assert "✨ CCA Session Report ✨" in captured.out
        assert "Task: test task" in captured.out
        assert "Steps" in captured.out
        assert "Reflection & Outcome:" in captured.out
        # Verify dict output is rendered (as JSON)
        assert '"success": true' in captured.out or "success" in captured.out

    def test_session_report_with_markdown_output(self, capsys):
        """Verify _print_session_report renders markdown output correctly."""
        from omni.agent.cli.commands.run import _print_session_report

        result = {
            "session_id": "test_456",
            "output": "## Overview\nThis is a markdown output.\n\n- Item 1\n- Item 2",
        }
        step_count = 2
        tool_counts = {"tool_calls": 2}
        tokens = 1000

        _print_session_report("markdown task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify output contains key elements
        assert "✨ CCA Session Report ✨" in captured.out
        assert "Overview" in captured.out
        assert "Item 1" in captured.out

    def test_session_report_panel_title(self, capsys):
        """Verify session report has correct panel title."""
        from omni.agent.cli.commands.run import _print_session_report

        result = {
            "session_id": "test_789",
            "output": "Simple output",
        }
        step_count = 1
        tool_counts = {}
        tokens = 100

        _print_session_report("simple task", result, step_count, tool_counts, tokens)

        captured = capsys.readouterr()
        # Verify panel title
        assert "✨ CCA Session Report ✨" in captured.out


class TestRunCommandEdgeCases:
    """Tests for edge cases in run command."""

    @pytest.mark.asyncio
    async def test_empty_task_handling(self):
        """Should handle empty task string."""
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

            mock.complete.assert_called_once()
            assert result == "I see you've sent an empty message."

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
