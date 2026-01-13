# inference/client.py
"""
Inference Client - LLM API client.

Phase 30: Modularized for testability.
Phase 37: Configuration-driven from settings.yaml.
"""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from anthropic import AsyncAnthropic

from .api import load_api_key, get_inference_config

log = structlog.get_logger("mcp-core.inference")


class InferenceClient:
    """Unified LLM inference client for MCP servers."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_tokens: int = None,
    ):
        """Initialize InferenceClient.

        Configuration is read from settings.yaml (inference section).
        Parameters passed here override settings.

        Args:
            api_key: API key (defaults to configured env var in settings.yaml)
            base_url: API base URL
            model: Default model name
            timeout: Request timeout in seconds
            max_tokens: Max tokens per response
        """
        config = get_inference_config()

        self.api_key = api_key or load_api_key()
        self.base_url = base_url or config["base_url"]
        self.model = model or config["model"]
        self.timeout = timeout or config["timeout"]
        self.max_tokens = max_tokens or config["max_tokens"]

        if not self.api_key:
            log.warning("inference.no_api_key", configured_env=config["api_key_env"])

        # MiniMax requires Authorization: Bearer header (auth_token) instead of x-api-key
        if self.base_url and "minimax" in self.base_url.lower():
            self.client = AsyncAnthropic(
                auth_token=self.api_key,
                base_url=self.base_url,
            )
        else:
            self.client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
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
        messages: List[Dict] = None,
        tools: List[Dict] = None,
    ) -> Dict[str, Any]:
        """Make a non-streaming LLM call with optional tool support."""
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        actual_timeout = timeout or self.timeout

        message_list = messages or [{"role": "user", "content": user_query}]

        log.info(
            "inference.request",
            model=actual_model,
            prompt_length=len(system_prompt),
            query_length=len(user_query),
            has_tools=tools is not None,
        )

        try:
            api_kwargs = {
                "model": actual_model,
                "max_tokens": actual_max_tokens,
                "system": system_prompt,
                "messages": message_list,
            }

            if tools:
                api_kwargs["tools"] = tools

            response = await asyncio.wait_for(
                self.client.messages.create(**api_kwargs),
                timeout=actual_timeout,
            )

            content = ""
            tool_calls = []

            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "text":
                        content += block.text if hasattr(block, "text") else ""
                    elif block.type == "tool_use":
                        tool_calls.append(
                            {
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )
                        content += f"[TOOL_CALL: {block.name}]\n"

            result = {
                "success": True,
                "content": content,
                "tool_calls": tool_calls,
                "model": actual_model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "error": "",
            }

            log.info(
                "inference.success",
                model=actual_model,
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
            )

            return result

        except asyncio.TimeoutError:
            log.warning("inference.timeout", model=actual_model)
            return {
                "success": False,
                "content": "",
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

    def get_tool_schema(self, skill_names: List[str] = None) -> List[Dict]:
        """Get tool definitions in JSON Schema format for ReAct loop."""
        tool_schemas = []

        if not skill_names or "filesystem" in skill_names:
            tool_schemas.extend(
                [
                    {
                        "name": "read_file",
                        "description": "Read the full content of a file (UTF-8)",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to file to read"}
                            },
                            "required": ["path"],
                        },
                    },
                    {
                        "name": "write_file",
                        "description": "Create or overwrite a file with new content",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to write"},
                                "content": {"type": "string", "description": "Content to write"},
                            },
                            "required": ["path", "content"],
                        },
                    },
                    {
                        "name": "list_directory",
                        "description": "List files and directories in a given path",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Directory path to list (default: '.')",
                                },
                            },
                            "required": [],
                        },
                    },
                    {
                        "name": "search",
                        "description": "Search for files matching a glob pattern",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "pattern": {
                                    "type": "string",
                                    "description": "Glob pattern (e.g., '**/*.py')",
                                },
                                "path": {
                                    "type": "string",
                                    "description": "Search directory (default: '.')",
                                },
                            },
                            "required": ["pattern"],
                        },
                    },
                    {
                        "name": "get_file_info",
                        "description": "Get metadata about a file (size, modified time, etc.)",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to file"},
                            },
                            "required": ["path"],
                        },
                    },
                    {
                        "name": "run_command",
                        "description": "Run a shell command and return output",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "Command to run"},
                            },
                            "required": ["command"],
                        },
                    },
                ]
            )

        return tool_schemas

    async def stream_complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Make a streaming LLM call."""
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens

        messages = [{"role": "user", "content": user_query}]

        log.info(
            "inference.stream_request",
            model=actual_model,
            prompt_length=len(system_prompt),
        )

        try:
            async with self.client.messages.stream(
                model=actual_model,
                max_tokens=actual_max_tokens,
                system=system_prompt,
                messages=messages,
            ) as stream:
                chunks = []
                async for event in stream:
                    if hasattr(event, "type") and event.type == "message_stop":
                        break
                    if hasattr(event, "delta") and getattr(event.delta, "text", None):
                        chunk = event.delta.text
                        chunks.append(chunk)
                        yield {"chunk": chunk, "done": False, "content": "".join(chunks)}

                yield {"chunk": "", "done": True, "content": "".join(chunks)}

        except Exception as e:
            log.warning("inference.stream_error", model=actual_model, error=str(e))
            yield {"chunk": "", "done": True, "content": "", "error": str(e)}

    async def complete_with_retry(
        self,
        system_prompt: str,
        user_query: str,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make an LLM call with automatic retry on failure."""
        last_error = ""

        for attempt in range(max_retries):
            result = await self.complete(system_prompt, user_query, **kwargs)

            if result["success"]:
                return result

            last_error = result["error"]
            log.warning(
                "inference.retry",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=last_error,
            )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_factor * (2**attempt))

        return {
            "success": False,
            "content": "",
            "error": f"Failed after {max_retries} attempts: {last_error}",
            "usage": {},
        }


__all__ = [
    "InferenceClient",
]
