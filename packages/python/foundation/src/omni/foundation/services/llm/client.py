# inference/client.py
"""
Inference Client - LLM API client.

Modularized for testability.
Configuration-driven from settings.yaml (inference section).
"""

import asyncio
import json
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

                # Extract thinking block content for fallback parameter extraction
                # The thinking block contains the LLM's reasoning and often file paths
                thinking_match = re.search(r"<thinking>(.*?)</thinking>", content, flags=re.DOTALL)
                thinking_content = thinking_match.group(1) if thinking_match else ""

                # Remove thinking block content to avoid false positives from [TOOL_CALL: ...] in thinking
                content_for_parsing = re.sub(
                    r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL
                )

                # Match [TOOL_CALL: filesystem.read_files]
                pattern = r"\[TOOL_CALL:\s*([^\]]+)\]"
                matches = re.findall(pattern, content_for_parsing)

                for i, tool_call_match in enumerate(matches):
                    tool_name = tool_call_match.strip()
                    tool_input = {}

                    # Method 1: Full JSON format: [TOOL_CALL: name]({"paths": [...], ...})
                    json_parens_pattern = (
                        rf"\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(\s*(\{{[^}}]*\}})\s*\)"
                    )
                    json_match = re.search(json_parens_pattern, content_for_parsing)
                    if json_match:
                        args_json = json_match.group(1)
                        try:
                            parsed_args = json.loads(args_json)
                            tool_input = parsed_args
                        except json.JSONDecodeError:
                            pass

                    # Method 1b: Shorthand array format: [TOOL_CALL: name](paths=["a", "b"])
                    # Handles LLM output like: paths=["file1.md", "file2.md"]
                    if not tool_input:
                        shorthand_match = re.search(
                            rf"\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(([^)]+)\)",
                            content_for_parsing,
                        )
                        if shorthand_match:
                            args_str = shorthand_match.group(1)
                            # Check if it looks like key=[...] format
                            array_match = re.match(r"(\w+)=\[([^\]]*)\]", args_str)
                            if array_match:
                                key = array_match.group(1)
                                values_str = array_match.group(2)
                                # Extract quoted strings from array
                                values = re.findall(r'"([^"]*)"', values_str)
                                if values:
                                    tool_input = {key: values}

                    # Method 2: Simple key=value format (non-array)
                    if not tool_input:
                        simple_parens_pattern = (
                            rf"\[TOOL_CALL:\s*{re.escape(tool_name)}\]\s*\(([^)]+)\)"
                        )
                        simple_match = re.search(simple_parens_pattern, content_for_parsing)
                        if simple_match:
                            args_str = simple_match.group(1)
                            # Skip if it looks like an array (contains [)
                            if "[" not in args_str:
                                for match in re.finditer(
                                    r'(\w+)=("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,]+)',
                                    args_str,
                                ):
                                    key = match.group(1)
                                    value = match.group(2)
                                    if value.startswith('"') and value.endswith('"'):
                                        value = value[1:-1]
                                    elif value.startswith("'") and value.endswith("'"):
                                        value = value[1:-1]
                                    tool_input[key] = value.strip()

                    # Method 3: Extract parameters from XML-like tags
                    param_pattern = r"<parameter\s+name=\"(\w+)\">([^<]+)</parameter>"
                    params = re.findall(param_pattern, content_for_parsing)
                    if params:
                        for k, v in params:
                            tool_input[k] = v.strip()

                    # Method 4: Fallback - extract file paths from thinking block for read_files
                    # This handles cases where LLM says "让我读取 `file.md`" but doesn't include args
                    if not tool_input and tool_name == "filesystem.read_files":
                        # Look for file paths in backticks: `file.md` or `path/to/file.md`
                        file_paths = re.findall(r"`([^`\n]+\.md)`", thinking_content)
                        if not file_paths:
                            # Look for any quoted strings that look like paths
                            file_paths = re.findall(r'["\']([^"\']+\.md)["\']', thinking_content)
                        if file_paths:
                            tool_input["paths"] = file_paths

                    # Method 5: Fallback for list_directory - extract directory from thinking
                    if not tool_input and tool_name == "filesystem.list_directory":
                        # Look for directory paths in backticks or quotes
                        dir_paths = re.findall(r"`([^`\n]+)`", thinking_content)
                        if not dir_paths:
                            dir_paths = re.findall(r'["\']([^"\']+)["\']', thinking_content)
                        # Filter for likely directory paths (not ending with .md, etc.)
                        dir_paths = [
                            p for p in dir_paths if not p.endswith((".md", ".txt", ".py", ".json"))
                        ]
                        if dir_paths:
                            tool_input["path"] = dir_paths[0]

                    # Method 6: Handle malformed output like [TOOL_CALL: name]({"key">content...)
                    # This catches cases where LLM outputs HTML-like malformed JSON
                    if not tool_input and tool_name.startswith("filesystem."):
                        # Simpler approach: match content after >
                        escaped_tool_name = re.escape(tool_name)
                        pattern = rf"\[TOOL_CALL:\s*{escaped_tool_name}\]\s*\(\s*[^)]*>\s*(.*)"
                        match = re.search(pattern, content_for_parsing, re.DOTALL)
                        if match:
                            full_content = match.group(1).strip()
                            if full_content:
                                # Try to extract the key name from the malformed JSON
                                key_match = re.search(
                                    r'["\']?(\w+)["\']?\s*[:=]\s*>', content_for_parsing
                                )
                                if key_match:
                                    key = key_match.group(1)
                                    tool_input[key] = full_content

                                # For save_file/write_file, also try to find path from thinking or context
                                if tool_name in ("filesystem.save_file", "filesystem.write_file"):
                                    # Look for path in thinking block or common patterns
                                    # Pattern: path="..." or path: "..." or `path`
                                    path_patterns = [
                                        r'path\s*[:=]\s*"([^"]+)"',
                                        r"path\s*[:=]\s*\'([^\']+)\'",
                                        r"`([^`]+\.md)`",
                                        r"`([^`]+\.txt)`",
                                    ]
                                    for p in path_patterns:
                                        path_match = re.search(p, thinking_content)
                                        if path_match:
                                            tool_input["path"] = path_match.group(1)
                                            break

                    # Always add tool call (let the tool itself handle missing required args)
                    tool_calls.append(
                        {
                            "id": f"call_{i}",
                            "name": tool_name,
                            "input": tool_input,
                        }
                    )

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
