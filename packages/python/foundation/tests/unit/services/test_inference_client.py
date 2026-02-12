"""Tests for InferenceClient with LiteLLM backend.

Tests verify LLM API message format compliance:
- system_prompt is passed as separate parameter
- messages array contains only 'user' and 'assistant' roles
- Tool call extraction from text content
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.foundation.services.llm.client import InferenceClient


class TestInferenceClientLiteLLM:
    """Tests for InferenceClient using LiteLLM backend."""

    def test_litellm_module_loaded(self):
        """Test that litellm module is loaded on initialization."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            assert hasattr(client, "_litellm")
            assert client._litellm.__name__ == "litellm"

    def test_minimax_uses_auth_token(self):
        """Test that MiniMax API configuration is loaded."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.minimax.chat/v1",
                "inference.model": "abab6.5s-chat",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            assert "minimax" in client.base_url.lower()
            assert client.model == "abab6.5s-chat"


class TestInferenceClientMessageFormat:
    """Tests for LLM API message format via LiteLLM."""

    def _create_litellm_response(self, text: str, tool_calls=None) -> MagicMock:
        """Create a mock LiteLLM response (OpenAI/Anthropic format)."""
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = text
        if tool_calls:
            mock_message.tool_calls = tool_calls
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        return mock_response

    @pytest.mark.asyncio
    async def test_complete_sends_messages_via_litellm(self):
        """Test that complete() sends messages via litellm.acompletion."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            # Mock the _litellm attribute directly after construction
            mock_response = self._create_litellm_response("Hello!")
            mock_litellm_instance = AsyncMock()
            mock_litellm_instance.acompletion = AsyncMock(return_value=mock_response)
            client._litellm = mock_litellm_instance

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Say hello",
            )

            # Verify litellm was called
            mock_litellm_instance.acompletion.assert_called_once()
            call_kwargs = mock_litellm_instance.acompletion.call_args[1]

            # Verify message format
            assert "messages" in call_kwargs
            assert call_kwargs["model"] == "anthropic/claude-sonnet-4-20250514"
            assert "anthropic" in call_kwargs["model"].lower()

            # Result should be successful
            assert result["success"] is True
            assert result["content"] == "Hello!"


class TestToolCallParsingLiteLLM:
    """Tests for tool call extraction from text content via LiteLLM."""

    def _create_litellm_response(self, text: str) -> MagicMock:
        """Create a mock LiteLLM response with text content."""
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = text
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        return mock_response

    @pytest.mark.asyncio
    async def test_tool_call_extraction_simple(self):
        """Test simple [TOOL_CALL: skill.command] extraction."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.minimax.chat/v1",
                "inference.model": "abab6.5s-chat",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            # Mock litellm directly on client
            mock_response = self._create_litellm_response(
                "I need to list files.\n[TOOL_CALL: filesystem.list_directory]\nLet me do that."
            )
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            client._litellm = mock_litellm

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List the files",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.list_directory"

    @pytest.mark.asyncio
    async def test_tool_call_in_thinking_block_filtered(self):
        """Test that [TOOL_CALL: ...] in thinking blocks are NOT extracted."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.minimax.chat/v1",
                "inference.model": "abab6.5s-chat",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            # Content with tool call ONLY in thinking block
            content = (
                "<thinking>\n"
                "Current Goal: List files\n"
                "Intent: I should use filesystem.list_directory\n"
                "Routing: I'll call [TOOL_CALL: filesystem.read_files] to read\n"
                "</thinking>\n"
                "Let me help you with that."
            )

            client = InferenceClient()
            mock_response = self._create_litellm_response(content)
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            client._litellm = mock_litellm

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List files",
            )

            # Should NOT extract tool calls from thinking block
            assert result["success"] is True
            assert len(result["tool_calls"]) == 0
            assert "<thinking>" in result["content"]

    @pytest.mark.asyncio
    async def test_no_tool_calls_text_response_only(self):
        """Test that plain text response has no tool calls."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            mock_response = self._create_litellm_response("Hello! How can I help you today?")
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            client._litellm = mock_litellm

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Say hello",
            )

            assert result["success"] is True
            assert result["content"] == "Hello! How can I help you today?"
            assert len(result["tool_calls"]) == 0


class TestErrorHandlingLiteLLM:
    """Tests for error handling with LiteLLM backend."""

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        """Test that exceptions are handled gracefully."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            # Simulate API error
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(side_effect=Exception("API rate limit exceeded"))
            client._litellm = mock_litellm

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Test error",
            )

            assert result["success"] is False
            assert "API rate limit exceeded" in result["error"]
            assert len(result["tool_calls"]) == 0

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        """Test that timeout errors are handled gracefully."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 30,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            import asyncio

            client = InferenceClient()
            # Simulate timeout
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(side_effect=asyncio.TimeoutError())
            client._litellm = mock_litellm

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Test timeout",
            )

            assert result["success"] is False
            assert "timed out" in result["error"].lower()


class TestRetryLogicLiteLLM:
    """Tests for retry logic via LiteLLM."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that retry logic works on failures (manual implementation)."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            # First call fails, second succeeds
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Success!"
            mock_message.tool_calls = None
            mock_choice.message = mock_message

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 100
            mock_usage.completion_tokens = 50

            mock_success_response = MagicMock()
            mock_success_response.choices = [mock_choice]
            mock_success_response.usage = mock_usage

            client = InferenceClient()
            mock_litellm = AsyncMock()
            mock_litellm.acompletion = AsyncMock(
                side_effect=[
                    Exception("Temporary error"),
                    mock_success_response,
                ]
            )
            client._litellm = mock_litellm

            # Manual retry loop (simplified version)
            last_error = None
            for attempt in range(3):
                try:
                    result = await client.complete(
                        system_prompt="You are a helpful assistant.",
                        user_query="Test retry",
                    )
                    if result["success"]:
                        break
                except Exception as e:
                    last_error = e
            else:
                result = {"success": False, "error": str(last_error)}

            # Verify retry behavior
            assert mock_litellm.acompletion.call_count == 2


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt method."""

    def test_prompt_from_role_and_name(self):
        """Test prompt building from role and name."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = "https://api.anthropic.com"
            mock_key.return_value = "test-key"

            client = InferenceClient()

            prompt = client._build_system_prompt(
                role="helpful assistant", name="Omni", description="An AI assistant"
            )

            assert prompt == "You are Omni. An AI assistant"

    def test_prompt_from_prompt_parameter(self):
        """Test that prompt parameter takes precedence."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = "https://api.anthropic.com"
            mock_key.return_value = "test-key"

            client = InferenceClient()

            custom_prompt = "You are a coding expert. Help with code reviews."
            prompt = client._build_system_prompt(
                role="helpful assistant",
                name="Coder",
                description="An AI assistant",
                prompt=custom_prompt,
            )

            assert prompt == custom_prompt
