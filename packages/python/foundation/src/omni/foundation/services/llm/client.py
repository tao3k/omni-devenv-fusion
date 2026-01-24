# inference/client.py
"""
Inference Client - LLM API client.

Modularized for testability.
Configuration-driven from settings.yaml (inference section).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from omni.foundation.api.api_key import get_anthropic_api_key
from omni.foundation.config.settings import get_setting

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
        # Read directly from settings.yaml
        self.api_key = api_key or get_anthropic_api_key()
        self.base_url = base_url or get_setting("inference.base_url", "https://api.anthropic.com")
        self.model = model or get_setting("inference.model", "claude-sonnet-4-20250514")
        self.timeout = timeout or get_setting("inference.timeout", 120)
        self.max_tokens = max_tokens or get_setting("inference.max_tokens", 4096)

        if not self.api_key:
            log.warning(
                "inference.no_api_key",
                configured_env=get_setting("inference.api_key_env", "ANTHROPIC_API_KEY"),
            )

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
        messages: list[dict] = None,
        tools: list[dict] = None,
    ) -> dict[str, Any]:
        """Make a non-streaming LLM call with optional tool support."""
        actual_model = model or self.model
        actual_max_tokens = max_tokens or self.max_tokens
        actual_timeout = timeout or self.timeout

        message_list = messages or [{"role": "user", "content": user_query}]

        log.debug(
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

            # Fallback: Parse tool calls from text content (for MiniMax compatibility)
            # Looks for patterns like: [TOOL_CALL: skill.command] or tool_use XML tags
            if not tool_calls and content:
                import re

                # Match [TOOL_CALL: filesystem.read_file]
                pattern = r"\[TOOL_CALL:\s*([^\]]+)\]"
                matches = re.findall(pattern, content)
                for i, tool_name in enumerate(matches):
                    tool_calls.append(
                        {
                            "id": f"call_{i}",
                            "name": tool_name.strip(),
                            "input": {},
                        }
                    )
                    # Also try to extract parameters from XML-like tags
                    param_pattern = r"<parameter\s+name=\"(\w+)\">([^<]+)</parameter>"
                    params = re.findall(param_pattern, content)
                    if params:
                        last_call = tool_calls[-1]
                        last_call["input"] = {k: v for k, v in params}

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

            log.debug(
                "inference.success",
                model=actual_model,
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
            )

            return result

        except TimeoutError:
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

    def get_tool_schema(self, skill_names: list[str] = None) -> list[dict]:
        """Get tool definitions from skill_index.json.

        Reads from .cache/skill_index.json which is populated by the Rust scanner.
        This provides dynamic tool discovery without hardcoded schemas.

        Args:
            skill_names: Optional list of skill names to filter (e.g., ["filesystem", "git"])

        Returns:
            List of tool schemas in Anthropic format with 'skill.command' naming convention.

        Raises:
            FileNotFoundError: If skill_index.json is not found
            json.JSONDecodeError: If skill_index.json is invalid JSON
        """
        import json

        from omni.foundation.config.dirs import get_skill_index_path

        skill_index_path = get_skill_index_path()

        if not skill_index_path.exists():
            raise FileNotFoundError(
                f"Skill index not found at {skill_index_path}. "
                "Run 'just build-rust' to generate the skill index."
            )

        tool_schemas = []
        skill_index = json.loads(skill_index_path.read_text())

        for skill_entry in skill_index:
            skill_name = skill_entry.get("name", "")
            if skill_names and skill_name not in skill_names:
                continue

            tools = skill_entry.get("tools", [])
            for tool in tools:
                tool_name = tool.get("name", "")
                tool_desc = tool.get("description", "")

                # Generate input schema from description (basic approach)
                input_schema = self._generate_input_schema_from_description(tool_name, tool_desc)

                tool_schemas.append({
                    "name": tool_name,
                    "description": tool_desc,
                    "input_schema": input_schema,
                })

        return tool_schemas

    def _generate_input_schema_from_description(self, tool_name: str, description: str) -> dict:
        """Generate basic input schema from tool name and description.

        This is a best-effort schema generation. For full accuracy, use the
        skill context which extracts schemas from actual function signatures.
        """
        # Extract common parameters based on tool naming patterns
        properties = {}
        required = []

        # Common patterns
        if "path" in tool_name or "file" in tool_name:
            properties["path"] = {
                "type": "string",
                "description": "Path to file or directory"
            }
            required.append("path")

        if "content" in tool_name:
            properties["content"] = {
                "type": "string",
                "description": "Content to write or process"
            }
            required.append("content")

        if "query" in tool_name or "search" in tool_name:
            properties["query"] = {
                "type": "string",
                "description": "Search query or question"
            }
            required.append("query")

        if "message" in tool_name:
            properties["message"] = {
                "type": "string",
                "description": "Message content"
            }
            required.append("message")

        if "cmd" in tool_name or "command" in tool_name:
            properties["cmd"] = {
                "type": "string",
                "description": "Command to execute"
            }
            required.append("cmd")

        if "args" in tool_name:
            properties["args"] = {
                "type": "array",
                "description": "Command arguments"
            }

        # Fallback: single "input" parameter for unknown tools
        if not properties:
            properties["input"] = {
                "type": "string",
                "description": "Input for the tool"
            }

        return {
            "type": "object",
            "properties": properties,
            "required": required if required else [],
        }

    async def stream_complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str = None,
        max_tokens: int = None,
    ) -> AsyncIterator[dict[str, Any]]:
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
    ) -> dict[str, Any]:
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
