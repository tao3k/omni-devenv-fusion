# mcp-server/orchestrator.py
import os
import sys
import json
import asyncio
import logging
import subprocess
import tempfile  # [新增] 用于创建临时文件
from typing import Any, Dict, List

from anthropic import AsyncAnthropic
from mcp.server.fastmcp import FastMCP

from personas import PERSONAS


def _load_env_from_file() -> Dict[str, str]:
    path = os.environ.get("ORCHESTRATOR_ENV_FILE") or os.path.join(os.getcwd(), ".mcp.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

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

mcp = FastMCP("orchestrator-tools")

sys.stderr.write(f"🚀 Orchestrator Server (Async + Repomix TempFile) starting... PID: {os.getpid()}\n")

if not API_KEY:
    sys.stderr.write("⚠️ Warning: ANTHROPIC_API_KEY not found in environment.\n")

client = AsyncAnthropic(api_key=API_KEY, base_url=BASE_URL)


def _build_system_prompt(role: str) -> str:
    persona = PERSONAS[role]
    hints_section = ""
    if persona.get("context_hints"):
        hints = "\n".join(f"- {hint}" for hint in persona["context_hints"])
        hints_section = f"\nContext hints:\n{hints}\n"
    return (
        f"You are {persona.get('name', role)}.\n"
        f"{persona.get('description', '')}\n"
        f"When to use: {persona.get('when_to_use', '')}\n"
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
async def get_codebase_context(target_dir: str = ".", ignore_files: str = "") -> str:
    """
    Generates a packed summary of the codebase using Repomix (Temp File Mode).
    """
    if ".." in target_dir or target_dir.startswith("/"):
        error_msg = "Error: Access to external directories is restricted for security."
        _log_decision("get_codebase_context.security_block", {"target_dir": target_dir})
        return error_msg

    # 创建一个临时文件路径
    # delete=False 因为我们需要关闭它后让 repomix 写入，然后再读取
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        temp_path = tmp.name

    _log_decision("get_codebase_context.request", {"target_dir": target_dir, "temp_path": temp_path})

    # 使用临时文件作为 output
    command = [
        "repomix",
        target_dir,
        "--style", "xml",
        "--output", temp_path,
        "--no-security-check"
    ]
    
    if ignore_files:
        command.extend(["--ignore", ignore_files])

    try:
        # 执行 Repomix (stdout/stderr 此时只包含日志，不包含内容)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # 检查是否生成了文件
        if not os.path.exists(temp_path):
            err_msg = stderr.decode() + "\n" + stdout.decode()
            return f"Error: Repomix failed to generate output file.\nLogs:\n{err_msg}"
            
        # 即使 Repomix 报错(非0)，只要文件生成了且有内容，我们也可以尝试读取
        # 但通常 returncode != 0 意味着失败
        if process.returncode != 0:
            os.unlink(temp_path) # 清理
            return f"Error running Repomix (Exit {process.returncode}):\n{stderr.decode()}"

        # 读取纯净内容
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as read_err:
            return f"Error reading temp file: {read_err}"
        finally:
            # 务必清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        if not content.strip():
            return "Repomix generated an empty file. Check directory or ignore rules."

        _log_decision("get_codebase_context.success", {"length": len(content)})
        return f"--- Codebase Context ({target_dir}) ---\n{content}"

    except FileNotFoundError:
        return "Error: 'repomix' command not found. Please ensure it is installed."
    except Exception as e:
        # 确保清理
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        _log_decision("get_codebase_context.exception", {"error": str(e)})
        return f"Failed to execute Repomix: {str(e)}"


@mcp.tool()
async def list_personas() -> str:
    persona_list = _serialize_personas()
    _log_decision("list_personas", {"count": len(persona_list)})
    return json.dumps(persona_list, indent=2)


@mcp.tool()
async def consult_specialist(role: str, query: str, stream: bool = False) -> str:
    if role not in PERSONAS:
        available = ", ".join(PERSONAS.keys())
        return f"Invalid role '{role}'. Choose one of: {available}."

    if not API_KEY:
        return "Error: ANTHROPIC_API_KEY is missing."

    system_prompt = _build_system_prompt(role)
    _log_decision("consult_specialist.request", {"role": role})

    try:
        response_text = await asyncio.wait_for(
            _call_model(system_prompt, query, stream=stream), timeout=REQUEST_TIMEOUT
        )
        _log_decision("consult_specialist.success", {"role": role})
        return f"--- 🤖 Expert Opinion: {role.upper()} ---\n{response_text}"

    except asyncio.TimeoutError:
        _log_decision("consult_specialist.timeout", {"role": role})
        return f"Request timed out after {REQUEST_TIMEOUT} seconds."
    except Exception as exc:
        _log_decision("consult_specialist.error", {"role": role, "error": str(exc)})
        return f"Error consulting specialist: {exc}"


if __name__ == "__main__":
    mcp.run()
