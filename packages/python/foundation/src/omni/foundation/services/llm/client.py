# inference/client.py
"""
Inference Client - Unified LLM API client via LiteLLM

Modularized for testability.
Configuration-driven from settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml; inference section).
Supports 100+ LLM providers (Anthropic, OpenAI, MiniMax, etc.) via litellm.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import structlog

from omni.foundation.api.api_key import get_anthropic_api_key
from omni.foundation.config.settings import get_setting

log = structlog.get_logger("mcp-core.inference")


class InferenceClient:
    """Unified LLM inference client for MCP servers via LiteLLM."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_tokens: int = None,
        provider: str = None,
    ):
        """Initialize InferenceClient via LiteLLM.

        Configuration is read from settings (system + user layer, inference section).

        Args:
            api_key: API key (defaults to configured env var)
            base_url: API base URL
            model: Default model name
            timeout: Request timeout in seconds
            max_tokens: Max tokens per response
            provider: Provider name (anthropic, openai, etc.)
        """
        import litellm

        self._litellm = litellm

        self.api_key = api_key or get_anthropic_api_key()
        self.base_url = base_url or get_setting("inference.base_url")
        self.model = model or get_setting("inference.model")
        self.timeout = timeout or get_setting("inference.timeout")
        self.max_tokens = max_tokens or get_setting("inference.max_tokens")
        self.provider = provider or get_setting("inference.provider")

        if not self.api_key:
            log.warning(
                "inference.no_api_key",
                configured_env=get_setting("inference.api_key_env"),
            )

    def _build_system_prompt(
        self, role: str, name: str = None, description: str = None, prompt: str = None
    ) -> str:
        """Build system prompt from persona configuration."""
        if prompt:
            return prompt
        return f"You are {name or role}. {description or ''}"

    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
        timeout: int = None,
        messages: list[dict] = None,
        tools: list[dict] = None,
    ) -> dict[str, Any]:
        """Make a non-streaming LLM call via LiteLLM."""
        import time

        _start = time.time()

        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        actual_timeout = timeout or self.timeout

        message_list = messages or [{"role": "user", "content": user_query}]

        log.info(
            f"[LLM] Starting inference with {actual_model}...",
        )

        log.debug(
            "inference.request",
            model=actual_model,
            provider=self.provider,
            prompt_length=len(system_prompt),
            query_length=len(user_query),
            has_tools=tools is not None,
        )

        try:
            # Build model string for litellm
            # MiniMax uses 'minimax/MiniMax-M2.1' format
            if self.provider == "minimax":
                model_id = f"minimax/{actual_model}"
            else:
                model_id = f"{self.provider}/{actual_model}"

            # Prepare kwargs for litellm
            litellm_kwargs = {
                "model": model_id,
                "max_tokens": actual_max_tokens,
                "timeout": actual_timeout,
                "system": system_prompt if system_prompt else None,
                "messages": message_list,
            }

            # Add API key
            if self.api_key:
                litellm_kwargs["api_key"] = self.api_key

            # Add base_url only for non-minimax providers
            # LiteLLM handles MiniMax internally with correct endpoint
            if self.provider != "minimax" and self.base_url:
                litellm_kwargs["api_base"] = self.base_url

            # Add tools if provided (skip for MiniMax - doesn't support tools properly)
            if tools and self.provider != "minimax":
                litellm_kwargs["tools"] = tools

            # Make the call via litellm
            response = await self._litellm.acompletion(**litellm_kwargs)

            # Extract content - handle both OpenAI and Anthropic/MiniMax formats
            content = ""
            tool_calls = []

            # Try OpenAI format first
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    content = getattr(choice.message, "content", "") or ""
                    # Check for tool calls
                    if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                        for tc in choice.message.tool_calls:
                            tool_calls.append(
                                {
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "input": json.loads(tc.function.arguments)
                                    if isinstance(tc.function.arguments, str)
                                    else tc.function.arguments,
                                }
                            )

            # Try Anthropic/MiniMax format (content array)
            elif hasattr(response, "content") and isinstance(response.content, list):
                for block in response.content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            content += getattr(block, "text", "") or ""
                        elif block.type == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.id,
                                    "name": block.name,
                                    "input": getattr(block, "input", {}),
                                }
                            )

            # Fallback: Parse tool calls from text content (for MiniMax compatibility)
            if not tool_calls and content:
                content_for_parsing = re.sub(
                    r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL
                )

                pattern = r"\[TOOL_CALL:\s*([^\]]+)\]"
                matches = re.findall(pattern, content_for_parsing)

                for i, tool_call_match in enumerate(matches):
                    tool_name = tool_call_match.strip()
                    tool_input = {}
                    tool_calls.append(
                        {
                            "id": f"call_{i}",
                            "name": tool_name,
                            "input": tool_input,
                        }
                    )

            # Extract usage
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                }

            _elapsed = time.time() - _start
            log.info(
                f"[LLM] Inference complete in {_elapsed:.1f}s, content_length={len(content)}",
            )

            return {
                "success": True,
                "content": content,
                "tool_calls": tool_calls,
                "model": actual_model,
                "usage": usage,
                "error": "",
            }

        except TimeoutError:
            log.warning("inference.timeout", model=actual_model)
            return {
                "success": False,
                "content": "",
                "tool_calls": [],
                "error": f"Request timed out after {actual_timeout}s",
                "model": actual_model,
                "usage": {},
            }

        except Exception as e:
            log.warning("inference.error", model=actual_model, error=str(e))
            return {
                "success": False,
                "content": "",
                "tool_calls": [],
                "error": str(e),
                "model": actual_model,
                "usage": {},
            }

    async def stream_complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Make a streaming LLM call via LiteLLM."""
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens

        messages = [{"role": "user", "content": user_query}]

        log.info(
            "inference.stream_request",
            model=actual_model,
            provider=self.provider,
            prompt_length=len(system_prompt),
        )

        try:
            model_id = f"{self.provider}/{actual_model}"
            litellm_kwargs = {
                "model": model_id,
                "max_tokens": actual_max_tokens,
                "messages": messages,
            }

            if self.api_key:
                litellm_kwargs["api_key"] = self.api_key
            if self.base_url:
                litellm_kwargs["api_base"] = self.base_url

            async for chunk in self._litellm.acompletion_stream(**litellm_kwargs):
                content = ""
                if hasattr(chunk, "choices") and chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                        content = choice.delta.content

                yield {"chunk": content, "done": False}

        except Exception as e:
            log.warning("inference.stream_error", model=actual_model, error=str(e))
            yield {"chunk": "", "done": True, "error": str(e)}


__all__ = [
    "InferenceClient",
]
