# mcp-server/orchestrator.py
import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List

from anthropic import AsyncAnthropic
from mcp.server.fastmcp import FastMCP

from personas import PERSONAS


def _load_env_from_file() -> Dict[str, str]:
    """
    Load environment values from a JSON file if present.
    Supports:
    - A flat JSON object of key/value pairs.
    - A .mcp.json-style file with `mcpServers.orchestrator.env`.
    """
    path = os.environ.get("ORCHESTRATOR_ENV_FILE") or os.path.join(os.getcwd(), ".mcp.json")
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"⚠️ Warning: failed to read env file {path}: {exc}\n")
        return {}

    # Most specific: orchestrator env inside mcpServers
    orchestrator_env = (
        data.get("mcpServers", {})
        .get("orchestrator", {})
        .get("env", {})
        if isinstance(data, dict)
        else {}
    )

    flat_env = data if isinstance(data, dict) else {}

    merged: Dict[str, str] = {}
    for source in (flat_env, orchestrator_env):
        for key, value in source.items():
            if isinstance(value, str):
                merged[key] = value
    return merged


_ENV_FILE_VALUES = _load_env_from_file()


def _env(key: str, default: str | None = None) -> str | None:
    """
    Resolve configuration with precedence:
    1) JSON file values (ORCHESTRATOR_ENV_FILE or .mcp.json)
    2) Process environment
    3) Provided default
    """
    return _ENV_FILE_VALUES.get(key) or os.environ.get(key) or default


LOG_LEVEL = os.environ.get("ORCHESTRATOR_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("orchestrator")


MODEL = _env("ORCHESTRATOR_MODEL") or _env("ANTHROPIC_MODEL", "MiniMax-M2.1")
BASE_URL = _env("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")
REQUEST_TIMEOUT = float(_env("ORCHESTRATOR_TIMEOUT", "30"))
MAX_TOKENS = int(_env("ORCHESTRATOR_MAX_TOKENS", "4096"))
ENABLE_STREAMING = (_env("ORCHESTRATOR_ENABLE_STREAMING", "false") or "false").lower() in (
    "1",
    "true",
    "yes",
)

API_KEY = _env("ANTHROPIC_API_KEY")

# Initialize MCP Server
mcp = FastMCP("orchestrator-tools")

# Startup logs
sys.stderr.write(f"🚀 Orchestrator Server (Async) starting... PID: {os.getpid()}\n")

if not API_KEY:
    sys.stderr.write("⚠️ Warning: ANTHROPIC_API_KEY not found in environment.\n")

client = AsyncAnthropic(api_key=API_KEY, base_url=BASE_URL)


def _build_system_prompt(role: str) -> str:
    persona = PERSONAS[role]
    hints_section = ""
    if persona.get("context_hints"):
        hints = "\n".join(f"- {hint}" for hint in persona["context_hints"])
        hints_section = f"\nContext hints:\n{hints}\n"
    description = persona.get("description", "")
    when_to_use = persona.get("when_to_use", "")
    return (
        f"You are {persona.get('name', role)}.\n"
        f"{description}\n"
        f"When to use: {when_to_use}\n"
        f"{hints_section}\n"
        f"{persona.get('prompt', '')}"
    )


def _serialize_personas() -> List[Dict[str, Any]]:
    return [
        {
            "id": role,
            "name": details.get("name"),
            "description": details.get("description"),
            "when_to_use": details.get("when_to_use"),
            "context_hints": details.get("context_hints", []),
        }
        for role, details in PERSONAS.items()
    ]


def _log_decision(event: str, payload: Dict[str, Any]) -> None:
    logger.info(json.dumps({"event": event, **payload}))


async def _call_model(system_prompt: str, query: str, stream: bool) -> str:
    messages = [{"role": "user", "content": query}]
    if stream or ENABLE_STREAMING:
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream_resp:
            chunks: List[str] = []
            async for event in stream_resp:
                if hasattr(event, "type") and event.type == "message_stop":
                    break
                if hasattr(event, "delta") and getattr(event.delta, "text", None):
                    chunks.append(event.delta.text)
            return "".join(chunks)

    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    final_text = []
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            final_text.append(block.text)
        elif hasattr(block, "text"):
            final_text.append(block.text)

    if not final_text:
        return "Error: Model returned content but no text block found."

    return "\n".join(final_text)


@mcp.tool()
async def list_personas() -> str:
    """
    List available personas and their recommended use cases.
    """
    persona_list = _serialize_personas()
    _log_decision("list_personas", {"count": len(persona_list)})
    return json.dumps(persona_list, indent=2)


@mcp.tool()
async def consult_specialist(role: str, query: str, stream: bool = False) -> str:
    """
    Consult a specialized AI expert for a specific domain task (Async Optimized).

    Args:
        role: The role to consult. Options: 'architect', 'platform_expert', 'devops_mlops', 'sre'.
        query: The specific question, code snippet, or design problem to analyze.
        stream: Whether to request a streaming response from the model.
    """
    # 1. Validate inputs
    if role not in PERSONAS:
        available = ", ".join(PERSONAS.keys())
        return (
            f"Invalid role '{role}'. Choose one of: {available}. "
            "You can call list_personas for details."
        )

    if not API_KEY:
        return (
            "Error: ANTHROPIC_API_KEY is missing. "
            "Set it in your environment to enable consult_specialist."
        )

    system_prompt = _build_system_prompt(role)
    _log_decision(
        "consult_specialist.request",
        {"role": role, "stream": stream or ENABLE_STREAMING, "model": MODEL},
    )

    try:
        response_text = await asyncio.wait_for(
            _call_model(system_prompt, query, stream=stream), timeout=REQUEST_TIMEOUT
        )
        _log_decision(
            "consult_specialist.success",
            {"role": role, "stream": stream or ENABLE_STREAMING},
        )
        return f"--- 🤖 Expert Opinion: {role.upper()} ---\n{response_text}"

    except asyncio.TimeoutError:
        _log_decision(
            "consult_specialist.timeout",
            {"role": role, "timeout_seconds": REQUEST_TIMEOUT},
        )
        return (
            f"Request timed out after {REQUEST_TIMEOUT} seconds. "
            "Try reducing the query size or increasing ORCHESTRATOR_TIMEOUT."
        )
    except Exception as exc:
        _log_decision(
            "consult_specialist.error",
            {"role": role, "error": str(exc)},
        )
        return f"Error consulting specialist: {exc}"


if __name__ == "__main__":
    mcp.run()
