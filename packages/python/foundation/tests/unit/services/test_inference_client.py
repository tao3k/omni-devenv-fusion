"""Tests for InferenceClient.

Tests verify LLM API message format compliance:
- system_prompt is passed as separate parameter
- messages array contains only 'user' and 'assistant' roles
- MiniMax API uses auth_token instead of api_key header
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestToolCallParsing:
    """Tests for tool call extraction from text content (MiniMax compatibility)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()
        self.mock_response = MagicMock()
        self.mock_response.content = []
        self.mock_response.usage.input_tokens = 100
        self.mock_response.usage.output_tokens = 50
        self.mock_client.messages.create = AsyncMock(return_value=self.mock_response)

    def _create_text_response(self, text: str) -> MagicMock:
        """Create a mock response with text content only."""
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = text
        response = MagicMock()
        response.content = [mock_block]
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        return response

    @pytest.mark.asyncio
    async def test_tool_call_extraction_simple(self):
        """Test simple [TOOL_CALL: skill.command] extraction."""
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

            # Simulate MiniMax response with [TOOL_CALL: ...] pattern
            self.mock_response.content = []
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(
                    "I need to list files.\n[TOOL_CALL: filesystem.list_directory]\nLet me do that."
                )
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List the files",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.list_directory"

    @pytest.mark.asyncio
    async def test_tool_call_extraction_multiple(self):
        """Test extraction of multiple tool calls."""
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

            content = (
                "First, I'll read the file.\n"
                "[TOOL_CALL: filesystem.read_files]\n"
                "Then I'll search for patterns.\n"
                "[TOOL_CALL: advanced_tools.smart_search]\n"
                "Finally, I'll write the results."
            )
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Analyze the codebase",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 2
            assert result["tool_calls"][0]["name"] == "filesystem.read_files"
            assert result["tool_calls"][1]["name"] == "advanced_tools.smart_search"

    @pytest.mark.asyncio
    async def test_tool_call_in_thinking_block_filtered(self):
        """Test that [TOOL_CALL: ...] in thinking blocks are NOT extracted."""
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

            # Content with tool call ONLY in thinking block
            content = (
                "<thinking>\n"
                "Current Goal: List files\n"
                "Intent: I should use filesystem.list_directory\n"
                "Routing: I'll call [TOOL_CALL: filesystem.read_files] to read\n"
                "</thinking>\n"
                "Let me help you with that."
            )
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List files",
            )

            # Should NOT extract tool calls from thinking block
            assert result["success"] is True
            assert len(result["tool_calls"]) == 0
            # But the thinking block should still be in content
            assert "<thinking>" in result["content"]

    @pytest.mark.asyncio
    async def test_tool_call_outside_thinking_block_extracted(self):
        """Test that [TOOL_CALL: ...] OUTSIDE thinking blocks ARE extracted."""
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

            # Content with tool call OUTSIDE thinking block
            content = (
                "<thinking>\n"
                "The user wants to list files. I'll use filesystem.list_directory.\n"
                "</thinking>\n"
                "[TOOL_CALL: filesystem.list_directory]\n"
                "Here are the files:"
            )
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List files",
            )

            # Should extract tool call from outside thinking block
            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.list_directory"

    @pytest.mark.asyncio
    async def test_parameter_extraction_xml_tags(self):
        """Test parameter extraction from XML-like <parameter> tags."""
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

            content = (
                "[TOOL_CALL: filesystem.read_files]\n"
                '<parameter name="paths">["/test/file.txt"]</parameter>\n'
                '<parameter name="encoding">utf-8</parameter>'
            )
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Read a file",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.read_files"
            assert result["tool_calls"][0]["input"]["paths"] == '["/test/file.txt"]'
            assert result["tool_calls"][0]["input"]["encoding"] == "utf-8"

    @pytest.mark.asyncio
    async def test_tool_call_with_json_args(self):
        """Test tool call with JSON format args: [TOOL_CALL: name]({"key": "value"})."""
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

            # JSON format: [TOOL_CALL: name]({"paths": [...], "encoding": "..."})
            content = '[TOOL_CALL: filesystem.read_files]({"paths": ["/test/file.txt"], "encoding": "utf-8"})'
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Read a file",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.read_files"
            assert result["tool_calls"][0]["input"]["paths"] == ["/test/file.txt"]
            assert result["tool_calls"][0]["input"]["encoding"] == "utf-8"

    @pytest.mark.asyncio
    async def test_tool_call_with_simple_args(self):
        """Test tool call with simple key=value format: [TOOL_CALL: name](key=value)."""
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

            # Simple format: [TOOL_CALL: name](path="/test/file.txt", encoding="utf-8")
            content = (
                "[TOOL_CALL: filesystem.save_file]"
                '({"path": "/test/output.txt", "content": "hello world"})'
            )
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Save a file",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.save_file"
            assert result["tool_calls"][0]["input"]["path"] == "/test/output.txt"
            assert result["tool_calls"][0]["input"]["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_tool_call_multiline_args(self):
        """Test tool call with multiline args."""
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

            content = '[TOOL_CALL: filesystem.list_directory]\n({"path": "/Users/test"})'
            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response(content)
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="List directory",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "filesystem.list_directory"
            assert result["tool_calls"][0]["input"]["path"] == "/Users/test"

    @pytest.mark.asyncio
    async def test_no_tool_calls_text_response_only(self):
        """Test that plain text response has no tool calls."""
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

            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_text_response("Hello! How can I help you today?")
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Say hello",
            )

            assert result["success"] is True
            assert result["content"] == "Hello! How can I help you today?"
            assert len(result["tool_calls"]) == 0


class TestAnthropicToolUseBlock:
    """Tests for native Anthropic tool_use block parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()

    def _create_tool_use_response(self, tool_name: str, tool_input: dict) -> MagicMock:
        """Create a mock response with tool_use block."""
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_123"
        mock_tool_block.name = tool_name
        mock_tool_block.input = tool_input

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = f"[TOOL_CALL: {tool_name}]"

        response = MagicMock()
        response.content = [mock_text_block, mock_tool_block]
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        return response

    @pytest.mark.asyncio
    async def test_native_tool_use_parsed(self):
        """Test that native Anthropic tool_use blocks are parsed correctly."""
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

            self.mock_client.messages.create = AsyncMock(
                return_value=self._create_tool_use_response(
                    "researcher.run_research_graph",
                    {"repo_url": "https://github.com/test/repo", "request": "Analyze"},
                )
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Research this repo",
            )

            assert result["success"] is True
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "researcher.run_research_graph"
            assert result["tool_calls"][0]["id"] == "call_123"
            assert result["tool_calls"][0]["input"]["repo_url"] == "https://github.com/test/repo"


class TestErrorHandling:
    """Tests for error handling in InferenceClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        """Test that timeout errors are handled gracefully."""
        import asyncio

        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
            patch(
                "omni.foundation.services.llm.client.AsyncAnthropic", return_value=self.mock_client
            ),
            patch("omni.foundation.services.llm.client.asyncio.wait_for") as mock_wait,
        ):
            mock_get.side_effect = lambda key, default=None: {
                "inference.base_url": "https://api.anthropic.com",
                "inference.model": "claude-sonnet-4-20250514",
                "inference.timeout": 30,
                "inference.max_tokens": 4096,
            }.get(key, default)
            mock_key.return_value = "test-api-key"

            client = InferenceClient()
            client.client = self.mock_client

            # Simulate timeout
            mock_wait.side_effect = asyncio.TimeoutError()

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Test timeout",
            )

            assert result["success"] is False
            assert "timed out" in result["error"].lower()
            assert result["model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        """Test that exceptions are handled gracefully."""
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

            # Simulate API error
            self.mock_client.messages.create = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )

            result = await client.complete(
                system_prompt="You are a helpful assistant.",
                user_query="Test error",
            )

            assert result["success"] is False
            assert "API rate limit exceeded" in result["error"]
            assert len(result["tool_calls"]) == 0


class TestRetryLogic:
    """Tests for complete_with_retry method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that retry logic works on failures."""
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

            # First call fails, second succeeds
            mock_text_block = MagicMock()
            mock_text_block.type = "text"
            mock_text_block.text = "Success!"

            self.mock_client.messages.create = AsyncMock(
                side_effect=[
                    Exception("Temporary error"),
                    MagicMock(
                        content=[mock_text_block],
                        usage=MagicMock(input_tokens=100, output_tokens=50),
                    ),
                ]
            )

            result = await client.complete_with_retry(
                system_prompt="You are a helpful assistant.",
                user_query="Test retry",
                max_retries=3,
                backoff_factor=0.01,
            )

            assert result["success"] is True
            assert result["content"] == "Success!"
            assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_all_fail(self):
        """Test that all retries failing returns error."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
            patch(
                "omni.foundation.services.llm.client.AsyncAnthropic", return_value=self.mock_client
            ),
            patch(
                "omni.foundation.services.llm.client.asyncio.sleep", new_callable=AsyncMock
            ) as _mock_sleep,
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

            # All calls fail
            self.mock_client.messages.create = AsyncMock(side_effect=Exception("Persistent error"))

            result = await client.complete_with_retry(
                system_prompt="You are a helpful assistant.",
                user_query="Test retry",
                max_retries=3,
                backoff_factor=0.01,
            )

            assert result["success"] is False
            assert "Failed after 3 attempts" in result["error"]
            assert self.mock_client.messages.create.call_count == 3


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

    def test_prompt_with_only_role(self):
        """Test prompt building with only role parameter."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = "https://api.anthropic.com"
            mock_key.return_value = "test-key"

            client = InferenceClient()

            prompt = client._build_system_prompt(role="helpful assistant")

            assert prompt == "You are helpful assistant. "

    def test_prompt_with_none_values(self):
        """Test prompt building with None optional parameters."""
        with (
            patch("omni.foundation.services.llm.client.get_setting") as mock_get,
            patch("omni.foundation.services.llm.client.get_anthropic_api_key") as mock_key,
        ):
            mock_get.return_value = "https://api.anthropic.com"
            mock_key.return_value = "test-key"

            client = InferenceClient()

            prompt = client._build_system_prompt(role="assistant", name=None, description=None)

            assert prompt == "You are assistant. "
