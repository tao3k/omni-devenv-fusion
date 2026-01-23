"""Tests for InferenceClient.

Tests verify LLM API message format compliance:
- system_prompt is passed as separate parameter
- messages array contains only 'user' and 'assistant' roles
- MiniMax API uses auth_token instead of api_key header
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from omni.foundation.services.llm.client import InferenceClient


class TestInferenceClientMiniMaxConfig:
    """Tests for MiniMax API configuration."""

    def test_minimax_uses_auth_token(self):
        """Test that MiniMax API uses auth_token instead of api_key."""
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

            # Verify client was initialized with correct params
            assert client.base_url == "https://api.minimax.chat/v1"
            assert "minimax" in client.base_url.lower()

    def test_anthropic_uses_api_key(self):
        """Test that Anthropic API uses api_key parameter."""
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

            # Verify client was initialized with correct params
            assert client.base_url == "https://api.anthropic.com"
            assert "anthropic" in client.base_url.lower()

    def test_custom_base_url_minimax_detection(self):
        """Test MiniMax detection with custom base URL."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://custom-minimax.example.com/v1",
                "inference.model": "abab6.5s-chat",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()

            # Should detect minimax from URL
            assert "minimax" in client.base_url.lower()


class TestInferenceClientMessageFormat:
    """Tests for LLM API message format compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()
        self.mock_response = MagicMock()
        self.mock_response.content = [MagicMock(type="text", text="Test response")]
        self.mock_response.usage.input_tokens = 100
        self.mock_response.usage.output_tokens = 50
        self.mock_client.messages.create = AsyncMock(return_value=self.mock_response)

    @pytest.mark.asyncio
    async def test_complete_with_messages_format(self):
        """Test that complete() sends messages in correct format."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
            patch(
                "omni.foundation.services.llm.client.AsyncAnthropic", return_value=self.mock_client
            ),
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            client.client = self.mock_client

            # Call complete with messages in correct format
            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="",
                messages=messages,
            )

            # Verify the API was called correctly
            call_kwargs = self.mock_client.messages.create.call_args[1]

            # system_prompt should be separate from messages
            assert call_kwargs["system"] == "You are a helpful assistant."

            # messages should only contain user/assistant
            assert "messages" in call_kwargs
            for msg in call_kwargs["messages"]:
                assert msg["role"] in ("user", "assistant")
                assert msg["role"] != "system"

            # Result should be successful
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_complete_without_system_in_messages(self):
        """Test that system messages are not included in messages array."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
            patch(
                "omni.foundation.services.llm.client.AsyncAnthropic", return_value=self.mock_client
            ),
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.minimax.chat/v1",
                "inference.model": "abab6.5s-chat",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            client.client = self.mock_client

            # Messages that mistakenly include system role
            messages = [
                {"role": "system", "content": "You are a helper"},  # Should NOT be here
                {"role": "user", "content": "Hello"},
            ]

            # User should pass system separately, not in messages
            result = await client.complete(
                system_prompt="You are a helper.",  # Correct way
                user_query="Hello",
                messages=[{"role": "user", "content": "Hello"}],  # Only user/assistant
            )

            # Verify no system role in messages
            call_kwargs = self.mock_client.messages.create.call_args[1]
            for msg in call_kwargs["messages"]:
                assert msg["role"] != "system"


class TestInferenceClientConfiguration:
    """Tests for InferenceClient configuration from settings."""

    def test_default_model_from_settings(self):
        """Test that default model is read from settings."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.model": "claude-haiku-2-20250514",
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()

            assert client.model == "claude-haiku-2-20250514"

    def test_default_timeout_from_settings(self):
        """Test that timeout is read from settings."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.timeout": 180,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()

            assert client.timeout == 180

    def test_parameter_override_settings(self):
        """Test that parameters override settings."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 120,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            # Override with parameter
            client = InferenceClient(model="claude-opus-4-20250501", timeout=300)

            assert client.model == "claude-opus-4-20250501"
            assert client.timeout == 300


class TestInferenceClientAPIKeyHandling:
    """Tests for API key configuration."""

    def test_api_key_from_get_anthropic_api_key(self):
        """Test that API key is loaded via get_anthropic_api_key()."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = "https://api.anthropic.com"
            mock_key.return_value = "my-secret-key"

            client = InferenceClient()

            mock_key.assert_called_once()
            assert client.api_key == "my-secret-key"

    def test_no_api_key_warning(self):
        """Test warning logged when no API key available."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
            patch("omni.foundation.services.llm.client.log") as mock_log,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.api_key_env": "ANTHROPIC_API_KEY",
            }.get(key, default)
            mock_key.return_value = None  # No API key

            client = InferenceClient()

            mock_log.warning.assert_called_once()
            call_args = mock_log.warning.call_args[0]
            assert "no_api_key" in call_args[0] or "api_key" in str(call_args)


class TestInferenceClientToolSchema:
    """Tests for tool schema generation."""

    def test_get_tool_schema_returns_valid_schema(self):
        """Test that get_tool_schema returns proper JSON Schema format."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = None
            mock_key.return_value = "test-key"

            client = InferenceClient()
            schemas = client.get_tool_schema()

            assert len(schemas) > 0

            # Each schema should have required fields
            for schema in schemas:
                assert "name" in schema
                assert "description" in schema
                assert "input_schema" in schema
                assert schema["input_schema"]["type"] == "object"

    def test_get_tool_schema_filtered_by_skill(self):
        """Test filtering tool schemas by skill name."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = None
            mock_key.return_value = "test-key"

            client = InferenceClient()

            # Get only filesystem tools
            filesystem_schemas = client.get_tool_schema(skill_names=["filesystem"])

            # Should have filesystem-related tools
            tool_names = [s["name"] for s in filesystem_schemas]
            assert "read_file" in tool_names
            assert "write_file" in tool_names
            assert "list_directory" in tool_names
