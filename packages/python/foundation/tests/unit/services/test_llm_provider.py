"""Tests for LLM Provider.

Tests verify LLM provider functionality:
- LiteLLMProvider initialization
- NoOpProvider fallback
- Provider configuration
- Graceful degradation when API key is missing
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from omni.foundation.config.settings import get_setting
from omni.foundation.services.llm.provider import (
    LLMConfig,
    LiteLLMProvider,
    NoOpProvider,
    get_llm_provider,
    reset_provider,
    _minimax_model_casing,
)


# Get the default model from settings for use in tests
DEFAULT_MODEL = get_setting("inference.model", "MiniMax-M2.1")


class TestMinimaxModelCasing:
    """Tests for MiniMax model name normalization (2013 fix)."""

    def test_lowercased_minimax_model_is_fixed(self):
        assert _minimax_model_casing("minimax-m2.1-highspeed") == "MiniMax-M2.1-lightning"
        assert _minimax_model_casing("minimax-m2.5") == "MiniMax-M2.5"

    def test_highspeed_mapped_to_lightning(self):
        # Platform docs say highspeed; v1 API expects lightning (LiteLLM Supported Models)
        assert _minimax_model_casing("MiniMax-M2.1-highspeed") == "MiniMax-M2.1-lightning"
        assert _minimax_model_casing("minimax-m2.1-highspeed") == "MiniMax-M2.1-lightning"

    def test_correct_casing_unchanged(self):
        assert _minimax_model_casing("MiniMax-M2.1-lightning") == "MiniMax-M2.1-lightning"
        assert _minimax_model_casing("MiniMax-M2.5") == "MiniMax-M2.5"

    def test_non_minimax_unchanged(self):
        assert _minimax_model_casing("gpt-4") == "gpt-4"
        assert _minimax_model_casing("") == ""


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_config(self):
        """Test default LLM configuration values."""
        config = LLMConfig()
        assert config.provider == "anthropic"
        assert config.model == "sonnet"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.timeout == 60
        assert config.max_tokens == 4096

    def test_custom_config(self):
        """Test custom LLM configuration."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            timeout=120,
            max_tokens=8192,
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.base_url == "https://api.openai.com/v1"


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider with MiniMax/Anthropic compatible APIs."""

    def test_provider_without_api_key(self):
        """Test LiteLLMProvider handles missing API key gracefully."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)

            provider = LiteLLMProvider()
            assert not provider.is_available()

    def test_provider_with_api_key(self):
        """Test LiteLLMProvider initializes with API key."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",  # Use checked key
                "inference.timeout": 60,
                "inference.max_tokens": 4096,
            }.get(key, default)

            # Set ANTHROPIC_API_KEY (which is_available() checks for)
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-api-key"}):
                provider = LiteLLMProvider()
                assert provider.is_available()
                assert provider.config.api_key_env == "ANTHROPIC_API_KEY"

    def test_provider_minimax_base_url(self):
        """Test LiteLLMProvider uses MiniMax Anthropic-compatible base_url."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": DEFAULT_MODEL,
                "inference.base_url": "https://api.minimax.io/anthropic",
                "inference.api_key_env": "MINIMAX_API_KEY",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)

            with patch.dict("os.environ", {"MINIMAX_API_KEY": "test-key"}):
                provider = LiteLLMProvider()
                # Verify MiniMax detection works
                assert "minimax" in provider.config.base_url.lower()
                assert provider.config.model == DEFAULT_MODEL

    def test_provider_custom_settings(self):
        """Test LiteLLMProvider loads custom settings."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "claude-opus-4-20250514",
                "inference.base_url": "https://api.anthropic.com",
                "inference.api_key_env": "ANTHROPIC_API_KEY",
                "inference.timeout": 180,
                "inference.max_tokens": 8192,
            }.get(key, default)

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                provider = LiteLLMProvider()
                assert provider.config.model == "claude-opus-4-20250514"
                assert provider.config.timeout == 180
                assert provider.config.max_tokens == 8192

    def test_litellm_passes_api_key_to_completion(self):
        """Test LiteLLMProvider passes API key correctly to litellm."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": DEFAULT_MODEL,
                "inference.base_url": "https://api.minimax.io/anthropic",
                "inference.api_key_env": "MINIMAX_API_KEY",
                "inference.timeout": 60,
                "inference.max_tokens": 4096,
            }.get(key, default)

            with patch.dict("os.environ", {"MINIMAX_API_KEY": "secret-key"}):
                provider = LiteLLMProvider()
                assert provider._get_api_key() == "secret-key"

    @pytest.mark.asyncio
    async def test_minimax_passes_cased_model_to_litellm(self):
        """MiniMax uses LiteLLM; model is normalised with _minimax_model_casing before call."""
        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "minimax",
                "inference.model": "MiniMax-M2.1",
                "inference.base_url": None,
                "inference.api_key_env": "MINIMAX_API_KEY",
                "inference.timeout": 60,
                "inference.max_tokens": 4096,
            }.get(key, default)

            with patch.dict("os.environ", {"MINIMAX_API_KEY": "test-key"}):
                provider = LiteLLMProvider()
                mock_resp = type("R", (), {"choices": [], "usage": None})()
                mock_resp.choices = [
                    type("C", (), {"message": type("M", (), {"content": "ok"})()})()
                ]
                mock_acompletion = AsyncMock(return_value=mock_resp)
                provider._litellm.acompletion = mock_acompletion
                await provider.complete("sys", "user")
                call_kwargs = mock_acompletion.call_args.kwargs
                assert call_kwargs["model"] == "MiniMax-M2.1"
                assert call_kwargs.get("custom_llm_provider") == "minimax"


class TestNoOpProvider:
    """Tests for NoOpProvider fallback."""

    @pytest.mark.asyncio
    async def test_noop_returns_empty_response(self):
        """Test NoOpProvider returns empty response on complete."""
        provider = NoOpProvider()
        response = await provider.complete("system", "user query")

        assert response.success is False
        assert response.content == ""
        assert "not configured" in response.error.lower()

    @pytest.mark.asyncio
    async def test_noop_complete_async_returns_empty(self):
        """Test NoOpProvider.complete_async returns empty string."""
        provider = NoOpProvider()
        result = await provider.complete_async("system", "user query")

        assert result == ""

    def test_noop_embed_returns_zero_vectors_on_error(self):
        """Test NoOpProvider.embed returns zero vectors when embedding fails."""
        provider = NoOpProvider()

        async def run_test():
            # Mock embed_batch to raise exception to trigger fallback
            with patch(
                "omni.foundation.services.embedding.embed_batch",
                side_effect=Exception("Embedding failed"),
            ):
                return await provider.embed(["text1", "text2"])

        result = asyncio.run(run_test())

        assert len(result) == 2
        assert all(len(v) == 2560 for v in result)  # Fallback uses dimension 2560
        assert all(v[0] == 0.0 for v in result)

    def test_noop_is_available(self):
        """Test NoOpProvider.is_available returns False."""
        provider = NoOpProvider()
        assert provider.is_available() is False


class TestProviderRegistry:
    """Tests for provider singleton and caching."""

    def test_get_llm_provider_returns_litellm_when_configured(self):
        """Test get_llm_provider returns LiteLLMProvider when API key is set."""
        reset_provider()  # Clear cache

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-api-key"}):
                provider = get_llm_provider()
                assert isinstance(provider, LiteLLMProvider)
                assert provider.is_available()

    def test_get_llm_provider_returns_noop_when_no_api_key(self):
        """Test get_llm_provider returns NoOpProvider when API key is missing."""
        reset_provider()  # Clear cache

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
                "inference.timeout": 120,
                "inference.max_tokens": 4096,
            }.get(key, default)

            provider = get_llm_provider()
            assert isinstance(provider, NoOpProvider)
            assert not provider.is_available()

    def test_provider_is_cached(self):
        """Test that provider is cached after first call."""
        reset_provider()  # Clear cache

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
            }.get(key, default)

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-api-key"}):
                provider1 = get_llm_provider()
                provider2 = get_llm_provider()

                assert provider1 is provider2

    def test_reset_provider_clears_cache(self):
        """Test that reset_provider clears the cache."""
        reset_provider()  # Clear cache

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "sonnet",
                "inference.base_url": None,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
            }.get(key, default)

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-api-key"}):
                provider1 = get_llm_provider()
                reset_provider()
                provider2 = get_llm_provider()

                # After reset, should create new provider
                assert provider1 is not provider2


class TestProviderConfig:
    """Tests for provider configuration loading."""

    def test_config_from_settings(self):
        """Test that config is loaded from settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml)."""
        reset_provider()

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "inference.provider": "anthropic",
                "inference.model": "claude-opus-4-20250514",
                "inference.base_url": "https://api.anthropic.com",
                "inference.timeout": 180,
                "inference.max_tokens": 8192,
                "inference.api_key_env": "ANTHROPIC_API_KEY",
            }.get(key, default)

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                provider = LiteLLMProvider()
                assert provider.config.model == "claude-opus-4-20250514"
                assert provider.config.timeout == 180
                assert provider.config.max_tokens == 8192

    def test_custom_config_override(self):
        """Test that custom config overrides settings."""
        custom_config = LLMConfig(
            model="claude-haiku-4-20250514",
            timeout=30,
        )

        with patch("omni.foundation.config.settings.get_setting") as mock_setting:
            mock_setting.return_value = "claude-sonnet-4-20250514"  # Different from custom

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                provider = LiteLLMProvider(config=custom_config)
                # Custom config should override settings
                assert provider.config.model == "claude-haiku-4-20250514"
                assert provider.config.timeout == 30
