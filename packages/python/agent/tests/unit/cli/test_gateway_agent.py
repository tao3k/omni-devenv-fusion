"""Unit tests for gateway and agent commands (stdio loop, session)."""

from unittest.mock import AsyncMock, patch

import pytest

from omni.agent.cli.commands.gateway_agent import STDIO_SESSION_ID, _stdio_loop


def _mock_kernel():
    """Kernel mock with async initialize/start/shutdown."""
    k = AsyncMock()
    k.initialize = AsyncMock(return_value=None)
    k.start = AsyncMock(return_value=None)
    k.shutdown = AsyncMock(return_value=None)
    return k


@patch("omni.core.kernel.engine.get_kernel")
class TestStdioLoop:
    """Tests for _stdio_loop with mocked input and execute_task_with_session."""

    @pytest.mark.asyncio
    async def test_stdio_loop_one_turn_then_exit(self, m_get_kernel):
        """One user message then exit: execute_task_with_session called once, output printed."""
        m_get_kernel.return_value = _mock_kernel()
        input_calls = ["hello", "exit"]
        with patch("builtins.input", side_effect=input_calls):
            with patch(
                "omni.agent.cli.commands.gateway_agent.execute_task_with_session",
                new_callable=AsyncMock,
                return_value={"output": "Hi there", "status": "completed"},
            ):
                with patch("omni.agent.cli.commands.gateway_agent.console") as m_console:
                    await _stdio_loop(STDIO_SESSION_ID)
                    assert m_console.print.call_count >= 1
                    calls = [str(c) for c in m_console.print.call_args_list]
                    assert any("Hi there" in c for c in calls)

    @pytest.mark.asyncio
    async def test_stdio_loop_empty_line_skipped(self, m_get_kernel):
        """Empty input is skipped, no call to execute_task_with_session."""
        m_get_kernel.return_value = _mock_kernel()
        input_calls = ["", "quit"]
        with patch("builtins.input", side_effect=input_calls):
            with patch(
                "omni.agent.cli.commands.gateway_agent.execute_task_with_session",
                new_callable=AsyncMock,
            ) as m_exec:
                await _stdio_loop(STDIO_SESSION_ID)
                m_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_stdio_loop_exit_prints_goodbye(self, m_get_kernel):
        """Typing 'exit' prints goodbye and does not call execute_task_with_session."""
        m_get_kernel.return_value = _mock_kernel()
        with patch("builtins.input", return_value="exit"):
            with patch(
                "omni.agent.cli.commands.gateway_agent.execute_task_with_session",
                new_callable=AsyncMock,
            ) as m_exec:
                with patch("omni.agent.cli.commands.gateway_agent.console") as m_console:
                    await _stdio_loop(STDIO_SESSION_ID)
                    m_exec.assert_not_called()
                    assert any("Goodbye" in str(c) for c in m_console.print.call_args_list)
