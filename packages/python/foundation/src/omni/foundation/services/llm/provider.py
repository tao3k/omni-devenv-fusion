# provider.py
"""
LLM Provider API - Unified LLM Access via LiteLLM

Unified interface for 100+ LLM providers (OpenAI, Anthropic, Azure, Google, etc.)
using litellm library.

Usage:
    from omni.foundation.services.llm import get_llm_provider

    provider = get_llm_provider()
    result = await provider.complete("You are an expert.", "Extract entities from this text.")
    embeddings = provider.embed(["text1", "text2"])
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger("llm.provider")


@dataclass
class LLMConfig:
    """LLM Configuration."""

    provider: str = "anthropic"  # openai, anthropic, azure, google, etc.
    model: str = "sonnet"
    base_url: str | None = None
    api_key_env: str = "ANTHROPIC_API_KEY"
    timeout: int = 60
    max_tokens: int = 4096
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1024


@dataclass
class LLMResponse:
    """LLM Response wrapper."""

    content: str
    success: bool
    error: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Make a non-streaming LLM call."""
        pass

    @abstractmethod
    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Make a non-streaming LLM call, returning just the content string."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if LLM is properly configured."""
        pass

    @abstractmethod
    def get_config(self) -> LLMConfig:
        """Get current configuration."""
        pass


class LiteLLMProvider(LLMProvider):
    """LiteLLM-based unified LLM provider.

    Supports 100+ LLM providers including:
    - OpenAI (gpt-4, gpt-4o, gpt-3.5-turbo)
    - Anthropic (claude-3-5-sonnet, claude-3-opus, claude-3-haiku)
    - Azure OpenAI
    - Google Vertex AI (gemini-pro, gemini-1.5)
    - AWS Bedrock (Claude, Llama, Titan)
    - Groq
    - Ollama (local models)
    - And many more...
    """

    def __init__(self, config: LLMConfig | None = None):
        import litellm

        self.config = config or self._load_config()
        self._litellm = litellm
        self._available = self._check_availability()

    def _load_config(self) -> LLMConfig:
        from omni.foundation.config.settings import get_setting

        return LLMConfig(
            provider=get_setting("inference.provider"),
            model=get_setting("inference.model"),
            base_url=get_setting("inference.base_url"),
            api_key_env=get_setting("inference.api_key_env"),
            timeout=int(get_setting("inference.timeout")),
            max_tokens=int(get_setting("inference.max_tokens")),
        )

    def _check_availability(self) -> bool:
        """Check if any LLM API is configured and accessible."""
        import os

        # Check the configured api_key_env first
        if self.config.api_key_env and os.getenv(self.config.api_key_env):
            return True

        # Check for common API keys (fallback)
        api_keys = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "AZURE_API_KEY",
            "GOOGLE_API_KEY",
            "GROQ_API_KEY",
        ]

        for key in api_keys:
            if os.getenv(key):
                return True

        # Check for local/ollama
        return self.config.provider == "ollama"

    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Make a non-streaming LLM call using litellm."""
        if not self._available:
            return LLMResponse(
                content="",
                success=False,
                error="No LLM API key configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.",
            )

        try:
            actual_model = model or self.config.model
            actual_max_tokens = max_tokens or self.config.max_tokens
            actual_timeout = int(kwargs.get("timeout", self.config.timeout))

            # Prepare model string for litellm
            # MiniMax uses 'minimax/MiniMax-M2.1' format
            if self.config.provider == "minimax":
                litellm_model = f"minimax/{actual_model}"
            else:
                litellm_model = f"{self.config.provider}/{actual_model}"

            # Prepare kwargs for litellm
            api_key = self._get_api_key()
            litellm_kwargs = {
                "model": litellm_model,
                "max_tokens": actual_max_tokens,
                "api_key": api_key,
                "timeout": actual_timeout,
            }
            tools = kwargs.get("tools")
            tool_choice = kwargs.get("tool_choice")
            response_format = kwargs.get("response_format")
            messages = kwargs.get("messages")
            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            stop = kwargs.get("stop")

            # Add base_url for MiniMax (required for LiteLLM)
            if self.config.provider == "minimax":
                litellm_kwargs["api_base"] = "https://api.minimax.io/v1"
                # MiniMax requires Authorization header explicitly
                litellm_kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
            elif self.config.base_url:
                litellm_kwargs["api_base"] = self.config.base_url

            # Add system prompt (LiteLLM handles this for all providers)
            if system_prompt:
                litellm_kwargs["system_prompt"] = system_prompt

            if tools:
                litellm_kwargs["tools"] = tools
            if tool_choice is not None:
                litellm_kwargs["tool_choice"] = tool_choice
            if response_format is not None:
                litellm_kwargs["response_format"] = response_format
            if temperature is not None:
                litellm_kwargs["temperature"] = temperature
            if top_p is not None:
                litellm_kwargs["top_p"] = top_p
            if stop is not None:
                litellm_kwargs["stop"] = stop

            # Make the call
            if messages:
                response = await self._litellm.acompletion(
                    **litellm_kwargs,
                    messages=messages,
                )
            elif user_query:
                response = await self._litellm.acompletion(
                    **litellm_kwargs,
                    messages=[{"role": "user", "content": user_query}],
                )
            else:
                response = await self._litellm.acompletion(
                    **litellm_kwargs,
                    messages=[{"role": "user", "content": system_prompt}],
                )

            # Extract content - MiniMax via LiteLLM returns content in reasoning_content
            content = ""
            tool_calls: list[dict[str, Any]] = []
            try:
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if hasattr(choice, "message"):
                        msg = choice.message
                        # Prefer assistant content for structured outputs; fall back to reasoning text.
                        raw_content = getattr(msg, "content", None)
                        reasoning = getattr(msg, "reasoning_content", None)

                        if raw_content and isinstance(raw_content, str) and raw_content.strip():
                            content = raw_content
                        elif raw_content and isinstance(raw_content, list):
                            # Handle content array format
                            content = ""
                            for block in raw_content:
                                if hasattr(block, "text"):
                                    content += block.text
                        elif reasoning and reasoning.strip():
                            content = reasoning

                        raw_tool_calls = getattr(msg, "tool_calls", None)
                        if raw_tool_calls:
                            for tc in raw_tool_calls:
                                fn = getattr(tc, "function", None)
                                name = getattr(fn, "name", "")
                                arguments = getattr(fn, "arguments", {})
                                if isinstance(arguments, str):
                                    try:
                                        arguments = json.loads(arguments)
                                    except Exception:
                                        arguments = {"raw": arguments}
                                tool_calls.append(
                                    {
                                        "id": getattr(tc, "id", ""),
                                        "name": name,
                                        "input": arguments if isinstance(arguments, dict) else {},
                                    }
                                )
            except Exception as e:
                logger.warning("Failed to extract content", error=str(e))

            # Extract usage
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                }

            return LLMResponse(
                content=content,
                success=True,
                usage=usage,
                model=actual_model,
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.error("LiteLLM complete failed", error=str(e))
            return LLMResponse(content="", success=False, error=str(e))

    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Make a non-streaming LLM call, returning just the content string."""
        response = await self.complete(system_prompt, user_query, model, max_tokens, **kwargs)
        return response.content if response.success else ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using unified embedding service.

        Delegates to omni.foundation.services.embedding for consistent behavior.
        Falls back to zero vectors if embedding service fails.
        """
        if not texts:
            return []

        # Import from unified embedding service
        try:
            from omni.foundation.services.embedding import embed_batch

            # Run sync embed_batch in thread pool (it's fast for local models)
            loop = asyncio.get_running_loop()
            vectors = await loop.run_in_executor(None, lambda: embed_batch(texts))
            return vectors

        except Exception as e:
            logger.debug("Embedding service failed, using zero vectors", error=str(e))

        # Fallback: return zero vectors
        dim = self.config.embedding_dim
        return [[0.0] * dim for _ in texts]

    def is_available(self) -> bool:
        """Check if LLM is properly configured."""
        return self._available

    def get_config(self) -> LLMConfig:
        """Get current configuration."""
        return self.config

    def _get_api_key(self) -> str | None:
        """Get API key from environment."""
        import os

        api_key_env = self.config.api_key_env
        return (
            os.getenv(api_key_env) or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        )


class NoOpProvider(LLMProvider):
    """No-op provider when LLM is not configured."""

    def __init__(self):
        self.config = LLMConfig()

    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        return LLMResponse(
            content="",
            success=False,
            error="LLM not configured - set ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.",
        )

    async def complete_async(
        self,
        system_prompt: str,
        user_query: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Return empty string when LLM is not configured."""
        return ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return zero vectors via unified embedding interface."""
        from omni.foundation.services.embedding import embed_batch

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: embed_batch(texts))
        except Exception:
            dim = 2560  # Use unified embedding dimension
            return [[0.0] * dim for _ in texts]

    def is_available(self) -> bool:
        return False

    def get_config(self) -> LLMConfig:
        return LLMConfig()


# Provider registry
_PROVIDER_CACHE: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider (singleton).

    Returns the appropriate provider based on configuration.
    Falls back to NoOpProvider if LLM is not configured.

    Usage:
        from omni.foundation.services.llm import get_llm_provider

        provider = get_llm_provider()
        result = await provider.complete("You are helpful.", "What is 2+2?")
        print(result.content)  # "4"
    """
    global _PROVIDER_CACHE

    if _PROVIDER_CACHE is not None:
        return _PROVIDER_CACHE

    # Try to create LiteLLM provider
    try:
        provider = LiteLLMProvider()
        if provider.is_available():
            _PROVIDER_CACHE = provider
            logger.info("Using LiteLLMProvider", provider=provider.config.provider)
            return provider

        # Fall through to NoOpProvider
    except Exception as e:
        logger.warning("Failed to create LiteLLMProvider", error=str(e))

    # Use NoOpProvider
    _PROVIDER_CACHE = NoOpProvider()
    logger.info("Using NoOpProvider (LLM not configured)")
    return _PROVIDER_CACHE


def reset_provider() -> None:
    """Reset the provider cache (for testing)."""
    global _PROVIDER_CACHE
    _PROVIDER_CACHE = None


# Convenience function for quick access
async def complete(
    system_prompt: str,
    user_query: str = "",
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Quick LLM completion using default provider.

    Args:
        system_prompt: System prompt (or full prompt if user_query is empty).
        user_query: Optional user query.
        model: Optional model override.
        max_tokens: Optional max tokens.

    Returns:
        The LLM response content.
    """
    provider = get_llm_provider()
    return await provider.complete_async(system_prompt, user_query, model, max_tokens)


# Note: For embeddings, use the unified interface from embedding.py:
#   from omni.foundation.services.embedding import embed_text, embed_batch


__all__ = [
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    "LiteLLMProvider",
    "NoOpProvider",
    "complete",
    "get_llm_provider",
    "reset_provider",
]
