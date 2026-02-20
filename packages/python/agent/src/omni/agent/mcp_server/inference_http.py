# mcp_server/inference_http.py
"""
OpenAI-compatible /v1/chat/completions over the project's LLM provider (LiteLLM).

When `omni mcp --transport sse --port 3002` runs, the same process exposes:
- MCP: /sse, /mcp, /messages/
- Inference: POST /v1/chat/completions (uses settings inference.*, no separate LiteLLM proxy)

Clients (e.g. Rust agent) can set LITELLM_PROXY_URL=http://127.0.0.1:3002/v1/chat/completions
and use the single MCP process for both tools and chat.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("omni.agent.mcp_server.inference_http")


async def handle_chat_completions(request: Request) -> JSONResponse:
    """Handle POST /v1/chat/completions (OpenAI-compatible) using project LLM provider."""
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Invalid JSON body: %s", e)
        return JSONResponse(
            {"error": {"message": "Invalid JSON", "type": "invalid_request_error"}},
            status_code=400,
        )

    messages = body.get("messages")
    if not messages:
        return JSONResponse(
            {"error": {"message": "messages is required", "type": "invalid_request_error"}},
            status_code=400,
        )

    model = body.get("model") or ""
    max_tokens = body.get("max_tokens")
    tools = body.get("tools")
    tool_choice = body.get("tool_choice")
    stream = body.get("stream", False)

    if stream:
        return JSONResponse(
            {"error": {"message": "Streaming not implemented", "type": "invalid_request_error"}},
            status_code=400,
        )

    system_prompt = ""
    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0].get("content") or ""
        messages = messages[1:]

    try:
        from omni.foundation.services.llm import get_llm_provider

        provider = get_llm_provider()
        if not provider.is_available():
            return JSONResponse(
                {
                    "error": {
                        "message": "LLM not configured (set API key in settings / env)",
                        "type": "invalid_request_error",
                    }
                },
                status_code=503,
            )

        response = await provider.complete(
            system_prompt=system_prompt,
            user_query="",
            model=model or None,
            max_tokens=max_tokens,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    except Exception as e:
        logger.exception("LLM request failed")
        return JSONResponse(
            {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                }
            },
            status_code=500,
        )

    if not response.success:
        return JSONResponse(
            {
                "error": {
                    "message": response.error or "Completion failed",
                    "type": "server_error",
                }
            },
            status_code=500,
        )

    # Build OpenAI-format tool_calls
    openai_tool_calls: list[dict[str, Any]] = []
    for i, tc in enumerate(response.tool_calls or []):
        name = tc.get("name", "")
        inp = tc.get("input") if isinstance(tc.get("input"), dict) else {}
        openai_tool_calls.append(
            {
                "id": tc.get("id") or f"call_{i}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(inp),
                },
            }
        )

    choice: dict[str, Any] = {
        "index": 0,
        "message": {
            "role": "assistant",
            "content": response.content or None,
        },
        "finish_reason": "tool_calls" if openai_tool_calls else "stop",
    }
    if openai_tool_calls:
        choice["message"]["tool_calls"] = openai_tool_calls

    out = {
        "id": "omni-chat-1",
        "object": "chat.completion",
        "model": response.model or model,
        "choices": [choice],
    }
    if response.usage:
        out["usage"] = {
            "prompt_tokens": response.usage.get("input_tokens", 0),
            "completion_tokens": response.usage.get("output_tokens", 0),
            "total_tokens": response.usage.get("input_tokens", 0)
            + response.usage.get("output_tokens", 0),
        }

    return JSONResponse(out)
