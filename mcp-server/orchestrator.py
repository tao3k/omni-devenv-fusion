# mcp-server/orchestrator.py
import os
import sys
import json
import asyncio
import logging
import subprocess
from pathlib import Path
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

    # Use .cache/ directory for repomix output (following numtide/prj-spec)
    cache_dir = Path(target_dir) / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_path = str(cache_dir / "repomix-output.xml")

    _log_decision("get_codebase_context.request", {"target_dir": target_dir, "temp_path": temp_path})

    # Use temp file as output
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
        # Execute Repomix (stdout/stderr only contains logs, not content)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        # Check if file was generated
        if not os.path.exists(temp_path):
            err_msg = stderr.decode() + "\n" + stdout.decode()
            return f"Error: Repomix failed to generate output file.\nLogs:\n{err_msg}"

        # Even if Repomix returns non-zero, if file was generated with content, we try to read it
        if process.returncode != 0:
            os.unlink(temp_path) # Cleanup
            return f"Error running Repomix (Exit {process.returncode}):\n{stderr.decode()}"

        # Read clean content
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as read_err:
            return f"Error reading temp file: {read_err}"
        finally:
            # Must cleanup temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        if not content.strip():
            return "Repomix generated an empty file. Check directory or ignore rules."

        _log_decision("get_codebase_context.success", {"length": len(content)})
        return f"--- Codebase Context ({target_dir}) ---\n{content}"

    except FileNotFoundError:
        return "Error: 'repomix' command not found. Please ensure it is installed."
    except Exception as e:
        # Ensure cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        _log_decision("get_codebase_context.exception", {"error": str(e)})
        return f"Failed to execute Repomix: {str(e)}"


def _build_directory_tree(root_path: str, max_depth: int = 3, current_depth: int = 0) -> str:
    """
    Build a directory tree structure using os.walk.
    Returns a tree-like representation without file content.
    """
    if current_depth >= max_depth:
        return ""

    tree_lines = []
    root_path = Path(root_path)

    try:
        # Sort directories and files separately
        items = sorted(root_path.iterdir(), key=lambda x: (x.is_file(), x.name))

        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            prefix = "└── " if is_last else "├── "
            connector = "    " if is_last else "│   "

            if item.is_dir():
                tree_lines.append(f"{prefix}{item.name}/")
                if current_depth < max_depth - 1:
                    sub_tree = _build_directory_tree(
                        str(item), max_depth, current_depth + 1
                    )
                    for line in sub_tree.split("\n"):
                        if line:
                            tree_lines.append(f"{connector}{line}")
            else:
                tree_lines.append(f"{prefix}{item.name}")
    except PermissionError:
        tree_lines.append(f"[Permission Denied]")

    return "\n".join(tree_lines)


@mcp.tool()
async def list_directory_structure(root_dir: str = ".") -> str:
    """
    Fast & Cheap: Lists the file tree WITHOUT content.

    Use this FIRST to explore the project structure before calling get_codebase_context.
    This tool consumes < 1k tokens and helps you understand the codebase layout.
    """
    # Security check: prevent access to external directories
    if ".." in root_dir or root_dir.startswith("/"):
        error_msg = "Error: Access to external directories is restricted for security."
        _log_decision("list_directory_structure.security_block", {"root_dir": root_dir})
        return error_msg

    target_path = Path(root_dir)

    # Verify directory exists
    if not target_path.exists():
        return f"Error: Directory '{root_dir}' does not exist."

    if not target_path.is_dir():
        return f"Error: '{root_dir}' is not a directory."

    try:
        _log_decision("list_directory_structure.request", {"root_dir": root_dir})

        # Try to use 'tree' command if available (more beautiful output)
        try:
            process = await asyncio.create_subprocess_exec(
                "tree", root_dir, "-L", "3", "--dirsfirst",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                tree_output = stdout.decode("utf-8")
                # Remove the first line (root_dir path) for cleaner output
                lines = tree_output.split("\n")[1:]
                result = "\n".join(lines)
                _log_decision("list_directory_structure.success", {"method": "tree"})
                return f"--- Directory Structure ({root_dir}) ---\n{result}"
        except FileNotFoundError:
            pass  # Fall back to Python implementation

        # Fallback: Use Python os.walk implementation
        tree_output = _build_directory_tree(root_dir, max_depth=3)
        _log_decision("list_directory_structure.success", {"method": "python"})

        if not tree_output.strip():
            return f"--- Directory Structure ({root_dir}) ---\n[Empty directory]"

        return f"--- Directory Structure ({root_dir}) ---\n{tree_output}"

    except Exception as e:
        _log_decision("list_directory_structure.exception", {"error": str(e)})
        return f"Error listing directory structure: {str(e)}"


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


# Files that should never be overwritten
_BLOCKED_PATHS = {
    "/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/",
    ".bashrc", ".bash_profile", ".zshrc", ".profile",
    "known_hosts", "authorized_keys",
}


def _is_safe_path(path: str) -> tuple[bool, str]:
    """
    Check if the path is safe to write within the project directory.
    Returns (is_safe, error_message).
    """
    # Block absolute paths outside project
    if path.startswith("/"):
        return False, "Absolute paths are not allowed."

    # Block parent directory traversal
    if ".." in path:
        return False, "Parent directory traversal is not allowed."

    # Block hidden system files at root
    filename = Path(path).name
    if filename.startswith(".") and filename not in {".gitignore", ".clang-format", ".prettierrc"}:
        # Allow known safe hidden files
        safe_hidden = {".gitignore", ".clang-format", ".prettierrc", ".markdownlintrc"}
        if filename not in safe_hidden:
            return False, f"Hidden file '{filename}' is not allowed."

    # Block known dangerous paths
    for blocked in _BLOCKED_PATHS:
        if path.startswith(blocked):
            return False, f"Blocked path: {blocked}"

    return True, ""


@mcp.tool()
async def save_file(path: str, content: str) -> str:
    """
    Write content to a file within the project directory.

    CAUTION: This tool can overwrite existing files. Use with caution.

    Args:
        path: Relative path from project root (e.g., "CLAUDE.md", "modules/new.nix")
        content: The content to write to the file

    Returns:
        Success message or error description
    """
    # Security check
    is_safe, error_msg = _is_safe_path(path)
    if not is_safe:
        _log_decision("save_file.security_block", {"path": path, "reason": error_msg})
        return f"Error: {error_msg}"

    project_root = Path.cwd()
    full_path = project_root / path

    # Ensure path is within project
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            _log_decision("save_file.security_block", {"path": path, "reason": "Outside project"})
            return "Error: Path is outside the project directory."
    except Exception as e:
        _log_decision("save_file.error", {"path": path, "error": str(e)})
        return f"Error resolving path: {e}"

    # Create parent directories if needed
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _log_decision("save_file.error", {"path": path, "error": str(e)})
        return f"Error creating directory: {e}"

    # Write file
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        _log_decision("save_file.success", {"path": path, "size": len(content)})
        return f"Successfully wrote {len(content)} bytes to '{path}'"
    except Exception as e:
        _log_decision("save_file.error", {"path": path, "error": str(e)})
        return f"Error writing file: {e}"


if __name__ == "__main__":
    mcp.run()
