"""
test_omni_loop.py - Unit Tests for OmniLoop Core Functionality

Tests the CCA Loop implementation with smart context management.
Ensures proper LLM integration and context handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.agent.core.context.manager import ContextManager
from omni.agent.core.omni.config import OmniLoopConfig
from omni.agent.core.omni.loop import OmniLoop


class TestOmniLoopConfig:
    """Tests for OmniLoopConfig basic settings."""

    def test_default_config_values(self):
        """Should have sensible default values."""
        config = OmniLoopConfig()

        assert config.max_tokens == 128000
        assert config.retained_turns == 10
        assert config.auto_summarize is False
        assert config.max_tool_calls == 20
        assert config.verbose is False
        assert config.suppress_atomic_tools is True
        assert config.max_tool_schemas == 20
        assert config.max_consecutive_errors == 3

    def test_custom_config_values(self):
        """Should respect custom configuration."""
        config = OmniLoopConfig(
            max_tokens=64000,
            retained_turns=5,
            auto_summarize=True,
            max_tool_calls=15,
            verbose=True,
            suppress_atomic_tools=False,
            max_tool_schemas=30,
            max_consecutive_errors=5,
        )

        assert config.max_tokens == 64000
        assert config.retained_turns == 5
        assert config.auto_summarize is True
        assert config.max_tool_calls == 15
        assert config.verbose is True
        assert config.suppress_atomic_tools is False
        assert config.max_tool_schemas == 30
        assert config.max_consecutive_errors == 5


class TestOmniLoopInitialization:
    """Tests for OmniLoop initialization."""

    def test_initialization_with_default_config(self):
        """Should initialize with default config."""
        loop = OmniLoop()

        assert loop.session_id is not None
        assert len(loop.session_id) == 8
        assert loop.context is not None
        assert loop.engine is not None
        assert loop.history == []

    def test_initialization_with_custom_config(self):
        """Should initialize with custom config."""
        config = OmniLoopConfig(max_tokens=64000, retained_turns=5)
        loop = OmniLoop(config=config)

        assert loop.config.max_tokens == 64000
        assert loop.config.retained_turns == 5

    def test_history_initialized_empty(self):
        """Should start with empty history."""
        loop = OmniLoop()
        assert loop.history == []

    def test_kernel_can_be_none(self):
        """Should work without kernel."""
        loop = OmniLoop(kernel=None)
        assert loop.kernel is None


class TestContextManager:
    """Tests for ContextManager basic operations."""

    def test_add_system_message(self):
        """Should add system messages correctly."""
        manager = ContextManager()
        manager.add_system_message("You are a helpful assistant.")

        assert len(manager.system_prompts) == 1
        assert manager.system_prompts[0]["role"] == "system"
        assert manager.system_prompts[0]["content"] == "You are a helpful assistant."

    def test_get_system_prompt(self):
        """Should return the first system prompt."""
        manager = ContextManager()
        manager.add_system_message("System prompt one")
        manager.add_system_message("System prompt two")

        result = manager.get_system_prompt()
        assert result == "System prompt one"

    def test_get_system_prompt_empty(self):
        """Should return None when no system prompts."""
        manager = ContextManager()

        result = manager.get_system_prompt()
        assert result is None

    def test_add_user_message(self):
        """Should add user messages as new turns."""
        manager = ContextManager()
        manager.add_user_message("Hello, world!")

        assert len(manager.turns) == 1
        assert manager.turns[0].user_message["content"] == "Hello, world!"
        assert manager.turns[0].user_message["role"] == "user"

    def test_update_last_assistant(self):
        """Should update assistant message in current turn."""
        manager = ContextManager()
        manager.add_user_message("Hello!")
        manager.update_last_assistant("Hi there!")

        assert manager.turns[0].assistant_message["content"] == "Hi there!"
        assert manager.turn_count == 1

    def test_get_active_context(self):
        """Should return only user/assistant messages (not system)."""
        manager = ContextManager()
        manager.add_system_message("System prompt")
        manager.add_user_message("User message")
        manager.update_last_assistant("Assistant response")

        messages = manager.get_active_context()

        # get_active_context returns only user/assistant messages
        # System prompts are handled separately via get_system_prompt()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_turn_count(self):
        """Should track turn count correctly."""
        manager = ContextManager()

        assert manager.turn_count == 0

        manager.add_user_message("User 1")
        manager.update_last_assistant("Assistant 1")
        assert manager.turn_count == 1

        manager.add_user_message("User 2")
        manager.update_last_assistant("Assistant 2")
        assert manager.turn_count == 2

    def test_snapshot_and_restore(self):
        """Should serialize and deserialize context correctly."""
        manager = ContextManager()
        manager.add_system_message("System")
        manager.add_user_message("User")
        manager.update_last_assistant("Assistant")

        snapshot = manager.snapshot()
        assert snapshot["system_prompts"][0]["content"] == "System"
        assert len(snapshot["turns"]) == 1
        assert snapshot["turn_count"] == 1

    def test_clear(self):
        """Should clear all context."""
        manager = ContextManager()
        manager.add_system_message("System")
        manager.add_user_message("User")
        manager.update_last_assistant("Assistant")

        manager.clear()

        assert len(manager.turns) == 0
        assert len(manager.system_prompts) == 0
        assert manager.turn_count == 0

    def test_stats(self):
        """Should return context statistics."""
        manager = ContextManager()
        manager.add_system_message("System")
        manager.add_user_message("User")
        manager.update_last_assistant("Assistant")

        stats = manager.stats()

        assert "turn_count" in stats
        assert "system_messages" in stats
        assert "total_messages" in stats
        assert "estimated_tokens" in stats
        assert "pruner_config" in stats
        assert "has_summary" in stats


class TestOmniLoopLLMIntegration:
    """Tests for OmniLoop LLM integration (mocked)."""

    @pytest.fixture
    def mock_inference_client(self):
        """Create a mock InferenceClient."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "This is a test response from the LLM.",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_run_calls_llm(self, mock_inference_client):
        """Should call the LLM when running a task."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()
            result = await loop.run("Test task: provide a simple greeting response")

            # Verify LLM was called
            mock_inference_client.complete.assert_called_once()
            assert "Test task" in str(mock_inference_client.complete.call_args)
            assert result == "This is a test response from the LLM."

    @pytest.mark.asyncio
    async def test_run_adds_context(self, mock_inference_client):
        """Should add user message to context."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()
            await loop.run("Test task: provide a simple greeting response")

            # Should have system prompt + user message
            context = loop.context.get_active_context()
            assert len(context) >= 2

    @pytest.mark.asyncio
    async def test_run_updates_history(self, mock_inference_client):
        """Should track conversation in history."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()
            await loop.run("Test task: provide a simple greeting response")

            assert len(loop.history) == 2
            assert loop.history[0]["role"] == "user"
            assert "Test task" in loop.history[0]["content"]
            assert loop.history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_run_with_empty_response(self, mock_inference_client):
        """Should handle empty LLM response."""
        mock_inference_client.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 50, "output_tokens": 0},
                "error": "",
            }
        )

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()
            result = await loop.run("Test task: respond with empty content")

            assert result == ""

    @pytest.mark.asyncio
    async def test_run_handles_llm_error(self, mock_inference_client):
        """Should handle LLM errors gracefully."""
        mock_inference_client.complete = AsyncMock(
            return_value={
                "success": False,
                "content": "",
                "error": "API rate limit exceeded",
            }
        )

        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()
            result = await loop.run("Test task: handle error gracefully")

            # Should return empty string on error
            assert result == ""


class TestOmniLoopStats:
    """Tests for OmniLoop statistics and reporting."""

    @pytest.fixture
    def loop_with_history(self):
        """Create loop with some history."""
        loop = OmniLoop()
        loop.context.add_system_message("System")
        loop.context.add_user_message("User 1")
        loop.context.update_last_assistant("Assistant 1")
        loop.context.add_user_message("User 2")
        loop.context.update_last_assistant("Assistant 2")
        return loop

    def test_get_stats(self, loop_with_history):
        """Should return valid statistics."""
        stats = loop_with_history.get_stats()

        assert "session_id" in stats
        assert "step_count" in stats
        assert "tool_calls" in stats
        assert "context_stats" in stats

    def test_snapshot(self, loop_with_history):
        """Should create valid snapshot."""
        snapshot = loop_with_history.snapshot()

        assert "session_id" in snapshot
        assert "context" in snapshot
        assert "history" in snapshot
        assert len(snapshot["history"]) >= 0


class TestOmniLoopMultiTurn:
    """Tests for multi-turn conversations."""

    @pytest.fixture
    def mock_inference_client(self):
        """Create a mock InferenceClient."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": "Assistant response",
                "tool_calls": [],
                "model": "sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "error": "",
            }
        )
        mock.get_tool_schema = MagicMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, mock_inference_client):
        """Should maintain context across turns."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()

            # First turn
            await loop.run("First message: please provide a greeting")

            # Second turn
            await loop.run("Second message: please provide a farewell")

            # Should have 4 messages: system + user1 + assistant1 + user2 (+ assistant2)
            context = loop.context.get_active_context()
            user_messages = [m for m in context if m["role"] == "user"]
            assert len(user_messages) == 2
            assert "First message" in user_messages[0]["content"]
            assert "Second message" in user_messages[1]["content"]

    @pytest.mark.asyncio
    async def test_turn_count_increments(self, mock_inference_client):
        """Should increment turn count after each response."""
        with patch("omni.agent.core.omni.loop.InferenceClient", return_value=mock_inference_client):
            loop = OmniLoop()

            assert loop.context.turn_count == 0

            await loop.run("First message for testing turn count")
            assert loop.context.turn_count == 1

            await loop.run("Second message for testing turn count")
            assert loop.context.turn_count == 2


class TestOmniLoopToolSchemas:
    """Tests for tool schema extraction with filter_commands."""

    @pytest.fixture
    def mock_kernel(self):
        """Create a mock kernel with skill_context."""
        mock = MagicMock()
        mock.skill_context.list_commands.return_value = [
            "skill.discover",
            "filesystem.read_files",
            "terminal.run_command",
            "filesystem.save_file",
        ]
        mock.skill_context.get_core_commands.return_value = [
            "skill.discover",
            "filesystem.save_file",
        ]
        mock.skill_context.get_dynamic_commands.return_value = [
            "filesystem.read_files",
            "terminal.run_command",
        ]
        return mock

    @pytest.mark.asyncio
    async def test_get_tool_schemas_returns_only_core_commands(self, mock_kernel):
        """Should return only core commands, excluding filtered (dynamic) commands.

        This test prevents regression of the bug where filter_commands were not
        applied because dynamic commands were incorrectly added back to the list.
        See: https://github.com/tao3k/omni-dev-fusion/issues/1234
        """
        loop = OmniLoop(kernel=mock_kernel)
        schemas = await loop._get_adaptive_tool_schemas()

        # Should only have 2 core commands
        assert len(schemas) == 2

        # Should NOT have filtered commands
        tool_names = [s["name"] for s in schemas]
        assert "filesystem.read_files" not in tool_names
        assert "terminal.run_command" not in tool_names

        # SHOULD have core commands
        assert "skill.discover" in tool_names
        assert "filesystem.save_file" in tool_names

    @pytest.mark.asyncio
    async def test_get_tool_schemas_skill_discover_first(self, mock_kernel):
        """Should ensure skill.discover is first in the list."""
        loop = OmniLoop(kernel=mock_kernel)
        schemas = await loop._get_adaptive_tool_schemas()

        assert len(schemas) >= 1
        assert schemas[0]["name"] == "skill.discover"

    @pytest.mark.asyncio
    async def test_get_tool_schemas_empty_when_no_kernel(self):
        """Should return empty list when no kernel is available."""
        loop = OmniLoop(kernel=None)
        schemas = await loop._get_adaptive_tool_schemas()

        assert schemas == []


class TestOmniLoopSession:
    """Tests for OmniLoop session management."""

    def test_session_id_is_uuid_prefix(self):
        """Should generate valid session ID."""
        loop = OmniLoop()
        # UUID prefix should be 8 characters
        assert len(loop.session_id) == 8
        # Should be hexadecimal
        all(hex_char in "0123456789abcdef" for hex_char in loop.session_id)

    def test_unique_session_ids(self):
        """Should generate unique session IDs."""
        loop1 = OmniLoop()
        loop2 = OmniLoop()
        assert loop1.session_id != loop2.session_id


class TestOmniLoopHarvesterIntegration:
    """Integration tests: OmniLoop evolution cycle must not fail on Harvester API.

    Prevents regression when Harvester.analyze_session or extract_lessons are
    missing or have incompatible signatures (e.g. 'Harvester' object has no
    attribute 'analyze_session').
    """

    @pytest.mark.asyncio
    async def test_trigger_harvester_completes_without_attribute_error(self):
        """_trigger_harvester must complete when Harvester has analyze_session and extract_lessons."""
        loop = OmniLoop()
        loop.history = [
            {"role": "user", "content": "List files in current directory"},
            {"role": "assistant", "content": "Here are the files: ..."},
        ]
        # Should not raise AttributeError or any exception
        await loop._trigger_harvester()

    @pytest.mark.asyncio
    async def test_trigger_harvester_with_empty_history_returns_early(self):
        """_trigger_harvester returns early when history is empty."""
        loop = OmniLoop()
        loop.history = []
        await loop._trigger_harvester()
        # No exception; Harvester is not invoked when history is empty
        assert loop.history == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
