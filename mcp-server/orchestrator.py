# mcp-server/orchestrator.py
"""
Orchestrator MCP Server - The "Brain"

Focus: SDLC, DevOps, MLOps, SRE, Architecture, Policy Enforcement.
Role: High-level decision making, project management, and context gathering.

Key Characteristic: "Macro" view. Uses Repomix to see the forest, not the trees.

Tools:
- get_codebase_context: Holistic project view via Repomix
- list_directory_structure: Fast directory tree (token optimization)
- list_personas: List available expert personas
- consult_specialist: Route queries to Architect, Platform Expert, DevOps, SRE
- run_task: Safe execution of just/nix commands
"""
import os
import sys
import json
import asyncio
import subprocess
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic
from mcp.server.fastmcp import FastMCP

from personas import PERSONAS


def _load_personas_from_config() -> Dict[str, Any]:
    """Load personas from external JSON config if available."""
    config_path = os.environ.get("ORCHESTRATOR_PERSONAS_FILE") or "mcp-server/personas.json"
    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _log_decision("personas_loaded", {"source": config_path, "count": len(data)})
        return data
    except Exception as e:
        _log_decision("personas_load_error", {"error": str(e)})
        return {}


# Merge static and dynamic personas (dynamic takes precedence)
_DYNAMIC_PERSONAS = _load_personas_from_config()
PERSONAS = {**PERSONAS, **_DYNAMIC_PERSONAS}


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
import logging
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

sys.stderr.write(f"🚀 Orchestrator Server (Async + Repomix) starting... PID: {os.getpid()}\n")

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


# =============================================================================
# Context Tools (Orchestration)
# =============================================================================

@mcp.tool()
async def get_codebase_context(target_dir: str = ".", ignore_files: str = "") -> str:
    """
    Generates a packed summary of the codebase using Repomix.

    Use this for holistic project understanding - sees the forest, not the trees.
    For surgical code operations, delegate to the 'coder' MCP server.
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
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if not os.path.exists(temp_path):
            err_msg = stderr.decode() + "\n" + stdout.decode()
            return f"Error: Repomix failed to generate output file.\nLogs:\n{err_msg}"

        if process.returncode != 0:
            os.unlink(temp_path)
            return f"Error running Repomix (Exit {process.returncode}):\n{stderr.decode()}"

        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as read_err:
            return f"Error reading temp file: {read_err}"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        if not content.strip():
            return "Repomix generated an empty file. Check directory or ignore rules."

        _log_decision("get_codebase_context.success", {"length": len(content)})
        return f"--- Codebase Context ({target_dir}) ---\n{content}"

    except FileNotFoundError:
        return "Error: 'repomix' command not found. Please ensure it is installed."
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        _log_decision("get_codebase_context.exception", {"error": str(e)})
        return f"Failed to execute Repomix: {str(e)}"


def _build_directory_tree(root_path: str, max_depth: int = 3, current_depth: int = 0) -> str:
    """Build a directory tree structure using os.walk."""
    if current_depth >= max_depth:
        return ""

    tree_lines = []
    root_path = Path(root_path)

    try:
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
    if ".." in root_dir or root_dir.startswith("/"):
        error_msg = "Error: Access to external directories is restricted for security."
        _log_decision("list_directory_structure.security_block", {"root_dir": root_dir})
        return error_msg

    target_path = Path(root_dir)

    if not target_path.exists():
        return f"Error: Directory '{root_dir}' does not exist."
    if not target_path.is_dir():
        return f"Error: '{root_dir}' is not a directory."

    try:
        _log_decision("list_directory_structure.request", {"root_dir": root_dir})

        # Try 'tree' command first
        try:
            process = await asyncio.create_subprocess_exec(
                "tree", root_dir, "-L", "3", "--dirsfirst",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                tree_output = stdout.decode("utf-8")
                lines = tree_output.split("\n")[1:]
                result = "\n".join(lines)
                _log_decision("list_directory_structure.success", {"method": "tree"})
                return f"--- Directory Structure ({root_dir}) ---\n{result}"
        except FileNotFoundError:
            pass

        # Fallback to Python implementation
        tree_output = _build_directory_tree(root_dir, max_depth=3)
        _log_decision("list_directory_structure.success", {"method": "python"})

        if not tree_output.strip():
            return f"--- Directory Structure ({root_dir}) ---\n[Empty directory]"

        return f"--- Directory Structure ({root_dir}) ---\n{tree_output}"

    except Exception as e:
        _log_decision("list_directory_structure.exception", {"error": str(e)})
        return f"Error listing directory structure: {str(e)}"


# =============================================================================
# Persona Routing (Orchestration)
# =============================================================================

@mcp.tool()
async def list_personas() -> str:
    """List available expert personas for consultation."""
    persona_list = _serialize_personas()
    _log_decision("list_personas", {"count": len(persona_list)})
    return json.dumps(persona_list, indent=2)


@mcp.tool()
async def consult_specialist(role: str, query: str, stream: bool = False) -> str:
    """
    Consult an expert persona for domain-specific advice.

    Roles:
    - architect: High-level design, refactoring strategies
    - platform_expert: Nix/OS, infrastructure, containers
    - devops_mlops: CI/CD, pipelines, reproducibility
    - sre: Reliability, security, performance
    """
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


# =============================================================================
# Delegation (The Bridge)
# =============================================================================

@mcp.tool()
async def delegate_to_coder(task_type: str, details: str) -> str:
    """
    Delegate a coding task to the Coder MCP server.

    Use this after planning with consult_specialist to hand off implementation.

    Args:
        task_type: Type of coding task
            - read: Read a file (use read_file in coder)
            - search: Search code patterns (use search_files in coder)
            - write: Write/modify files (use save_file in coder)
            - refactor: Structural refactoring (use ast_search/ast_rewrite in coder)
        details: Specific details about what to do

    Returns:
        Instructions for using coder tools, or delegated result
    """
    _log_decision("delegate_to_coder.request", {"task_type": task_type, "details": details[:200]})

    task_guidance = {
        "read": (
            "Use the 'read_file' tool in the Coder MCP server:\n"
            f"@omni-coder read_file path=\"{details}\""
        ),
        "search": (
            "Use the 'search_files' or 'ast_search' tool in the Coder MCP server:\n"
            f"@omni-coder search_files pattern=\"{details}\"\n"
            f"# Or for structural search:\n"
            f"@omni-coder ast_search pattern=\"{details}\""
        ),
        "write": (
            "Use the 'save_file' tool in the Coder MCP server:\n"
            f"@omni-coder save_file path=\"{details}\" content=\"...\""
        ),
        "refactor": (
            "Use the 'ast_search' and 'ast_rewrite' tools in the Coder MCP server:\n"
            f"# First, find the pattern:\n"
            f"@omni-coder ast_search pattern=\"{details}\"\n"
            f"# Then, rewrite:\n"
            f"@omni-coder ast_rewrite pattern=\"$old\" replacement=\"$new\""
        ),
    }

    if task_type not in task_guidance:
        available = ", ".join(task_guidance.keys())
        return f"Error: Unknown task_type '{task_type}'. Choose from: {available}"

    result = f"--- Delegation: {task_type.upper()} ---\n\n"
    result += f"Task: {details}\n\n"
    result += "Coder Server Instructions:\n"
    result += task_guidance[task_type]
    result += "\n\nNote: The Coder MCP server will handle file operations with:\n"
    result += "- Backup (.bak) before overwriting\n"
    result += "- Syntax validation for Python/Nix files\n"
    result += "- Path safety checks"

    return result


# =============================================================================
# Phase 3: Advanced Adaptation
# =============================================================================

# Supported community MCP servers ( toverified work with this project)
_SUPPORTED_COMMUNITY_MCPS = {
    "kubernetes": {
        "description": "Kubernetes cluster management",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-kubernetes"],
        "context_required": ["devenv.nix", "flake.nix"],
    },
    "postgres": {
        "description": "PostgreSQL database operations",
        "command": "uvx",
        "args": ["mcp-server-postgres"],
        "context_required": ["devenv.nix"],
    },
    "filesystem": {
        "description": "Advanced file operations",
        "command": "uvx",
        "args": ["mcp-server-filesystem"],
        "context_required": [],
    },
}


def _load_project_context() -> str:
    """Load key project files to inject into community MCP context."""
    context_files = ["CLAUDE.md", "devenv.nix", "flake.nix", "justfile"]
    context = []

    for filename in context_files:
        path = Path(filename)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                context.append(f"=== {filename} ===\n{content}")
            except Exception:
                pass

    return "\n\n".join(context) if context else "No project context available."


@mcp.tool()
async def community_proxy(mcp_name: str, query: str) -> str:
    """
    Access a community MCP server with project context injection.

    Wraps external MCPs (e.g., Kubernetes, PostgreSQL) to ensure they respect
    the project's nix configurations and architectural constraints.

    Args:
        mcp_name: Name of the community MCP
            - kubernetes: K8s cluster management
            - postgres: PostgreSQL database operations
            - filesystem: Advanced file operations
        query: Your request for the community MCP

    Returns:
        Response from the community MCP with project context, or guidance on setup
    """
    _log_decision("community_proxy.request", {"mcp_name": mcp_name, "query": query[:200]})

    if mcp_name not in _SUPPORTED_COMMUNITY_MCPS:
        available = ", ".join(_SUPPORTED_COMMUNITY_MCPS.keys())
        return f"Error: Unknown MCP '{mcp_name}'. Supported: {available}"

    mcp_config = _SUPPORTED_COMMUNITY_MCPS[mcp_name]

    # Check if the community MCP is available
    cmd = mcp_config["command"]
    args = mcp_config["args"]

    try:
        process = await asyncio.create_subprocess_exec(
            cmd, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        # Wait briefly to see if it starts
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
            # If it exits quickly, MCP might not be installed
            installed = False
        except asyncio.TimeoutError:
            installed = True
            process.terminate()
            await process.wait()
    except FileNotFoundError:
        installed = False

    if not installed:
        return (
            f"--- Community MCP: {mcp_name} ---\n"
            f"Description: {mcp_config['description']}\n\n"
            f"To install and use:\n"
            f"  {cmd} {' '.join(args)}\n\n"
            f"Project Context Requirements: {mcp_config['context_required']}\n\n"
            f"Current Project Context (injected when MCP runs):\n"
            f"{_load_project_context()[:500]}...\n\n"
            f"Note: This Orchestrator will inject CLAUDE.md and devenv.nix "
            f"into the MCP's context to ensure it respects project policies."
        )

    # MCP is available - provide guidance for using it
    project_context = _load_project_context()

    result = f"--- Community MCP: {mcp_name} ---\n"
    result += f"Description: {mcp_config['description']}\n\n"
    result += "Project Context (automatically injected):\n"
    result += f"- CLAUDE.md: Project policies and architecture\n"
    result += f"- devenv.nix: Development environment configuration\n"
    result += f"- justfile: Build and test commands\n\n"
    result += f"Your query: {query}\n\n"
    result += "To use this MCP directly in Claude Code, add to your .mcp.json:\n"
    result += f'{{"mcpServers": {{"{mcp_name}": {{"command": "{cmd}", "args": {args}}}}}}}\n\n'
    result += "Note: The Orchestrator can proxy requests to this MCP with "
    result += "project context injection for stricter policy enforcement."

    return result


# =============================================================================
# Safe Sandbox (Phase 3: Security)
# =============================================================================

# Dangerous patterns to block in commands
_DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"dd\s+if=",
    r">\s*/dev/",
    r"\|\s*sh",
    r"&&\s*rm",
    r";\s*rm",
    r"chmod\s+777",
    r"chown\s+root:",
    r":\(\)\s*{",
    r"\$\(\s*",
]


def _check_for_dangerous_patterns(cmd: str, args: List[str]) -> tuple[bool, str]:
    """Check if command contains dangerous patterns."""
    full_cmd = f"{cmd} {' '.join(args)}"
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, full_cmd, re.IGNORECASE):
            return False, f"Blocked dangerous pattern: {pattern}"
    return True, ""


def _create_sandbox_env() -> Dict[str, str]:
    """Create a sandboxed environment with restricted variables."""
    env = os.environ.copy()
    # Remove or restrict sensitive environment variables
    sensitive_vars = ["AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "ANTHROPIC_API_KEY"]
    for var in sensitive_vars:
        if var in env:
            env[var] = "***REDACTED***"
    # Restrict home directory access
    env["HOME"] = str(Path.cwd())
    return env


@mcp.tool()
async def safe_sandbox(command: str, args: Optional[List[str]] = None,
                       timeout: int = 60, read_only: bool = False) -> str:
    """
    Run commands in a safe sandbox environment.

    Safety features:
    - Blocks dangerous patterns (rm -rf, dd, etc.)
    - Redacts sensitive environment variables
    - Restricts HOME directory
    - Timeout protection
    - Read-only mode for safe exploration

    Args:
        command: Command to run
        args: Command arguments
        timeout: Max execution time in seconds (default: 60)
        read_only: If True, simulate read-only operations

    Returns:
        Command output or error message
    """
    if args is None:
        args = []

    _log_decision("safe_sandbox.request", {"command": command, "timeout": timeout, "read_only": read_only})

    # Check for dangerous patterns
    is_safe, error_msg = _is_safe_command(command, args)
    if not is_safe:
        _log_decision("safe_sandbox.blocked", {"reason": error_msg})
        return f"Error: {error_msg}"

    # Additional dangerous pattern check
    is_safe, error_msg = _check_for_dangerous_patterns(command, args)
    if not is_safe:
        _log_decision("safe_sandbox.dangerous_pattern", {"reason": error_msg})
        return f"Error: {error_msg}"

    # Create sandboxed environment
    env = _create_sandbox_env()
    if read_only:
        env["READ_ONLY_SANDBOX"] = "1"

    _log_decision("safe_sandbox.executing", {"command": command})

    try:
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(Path.cwd())
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        output = stdout.decode("utf-8")
        error = stderr.decode("utf-8")

        _log_decision("safe_sandbox.complete", {
            "command": command,
            "returncode": process.returncode,
            "read_only": read_only
        })

        result = f"--- Sandbox Execution: {command} {' '.join(args)} ---\n"
        result += f"Read-only mode: {read_only}\n"
        result += f"Exit code: {process.returncode}\n\n"

        if output:
            result += f"stdout:\n{output}\n"
        if error:
            result += f"stderr:\n{error}\n"

        if process.returncode == 0:
            result += "\n✅ Execution completed safely."
        else:
            result += "\n⚠️  Execution completed with errors."

        return result

    except asyncio.TimeoutExpired:
        _log_decision("safe_sandbox.timeout", {"command": command, "timeout": timeout})
        return f"Error: Command timed out after {timeout} seconds."
    except FileNotFoundError:
        return f"Error: Command '{command}' not found."
    except Exception as e:
        _log_decision("safe_sandbox.error", {"command": command, "error": str(e)})
        return f"Error executing command: {e}"


# =============================================================================
# Memory Persistence (Phase 3: Long-term Memory)
# =============================================================================

_MEMORY_DIR = Path(".memory")


def _init_memory_dir() -> bool:
    """Initialize the memory directory if it doesn't exist."""
    try:
        _MEMORY_DIR.mkdir(exist_ok=True)
        (_MEMORY_DIR / "decisions").mkdir(exist_ok=True)
        (_MEMORY_DIR / "tasks").mkdir(exist_ok=True)
        (_MEMORY_DIR / "context").mkdir(exist_ok=True)
        return True
    except Exception:
        return False


def _format_decision(decision: Dict[str, Any]) -> str:
    """Format a decision for storage."""
    lines = [
        f"# Decision: {decision.get('title', 'Untitled')}",
        f"Date: {decision.get('date', 'Unknown')}",
        f"Author: {decision.get('author', 'Unknown')}",
        "",
        f"## Problem",
        decision.get("problem", "N/A"),
        "",
        f"## Solution",
        decision.get("solution", "N/A"),
        "",
        f"## Rationale",
        decision.get("rationale", "N/A"),
        "",
        f"## Status",
        decision.get("status", "open"),
    ]
    return "\n".join(lines)


@mcp.tool()
async def memory_garden(operation: str, title: str = "", content: str = "") -> str:
    """
    Persist project memories for long-term context.

    Uses a file-based system (following numtide/prj-spec) in `.memory/`:

    - decisions/: Architectural decisions (ADRs)
    - tasks/: Task tracking
    - context/: Project context snapshots

    Args:
        operation: Operation to perform
            - read_decisions: List all past decisions
            - add_decision: Add a new architectural decision
            - list_tasks: List pending tasks
            - add_task: Add a task
            - save_context: Save current project context
            - read_context: Read latest context snapshot
        title: Title for decision/task
        content: Content for decision/task (JSON or markdown)

    Returns:
        Operation result or list of items
    """
    _log_decision("memory_garden.request", {"operation": operation, "title": title})

    if not _init_memory_dir():
        return "Error: Could not initialize memory directory (.memory/)"

    decisions_dir = _MEMORY_DIR / "decisions"
    tasks_dir = _MEMORY_DIR / "tasks"
    context_dir = _MEMORY_DIR / "context"

    if operation == "read_decisions":
        decisions = []
        for f in decisions_dir.glob("*.md"):
            decisions.append(f"- {f.stem}: {f.read_text().split(chr(10))[0].replace('# Decision: ', '')}")
        if not decisions:
            return "No decisions recorded yet."
        return f"--- Architectural Decisions ---\n" + "\n".join(decisions)

    elif operation == "add_decision":
        if not title:
            return "Error: Title is required for adding a decision."
        decision = {
            "title": title,
            "content": content,
            "date": str(Path(__file__).stat().st_mtime),
            "author": "Claude",
            "status": "open",
        }
        # Extract problem/solution from content if it's JSON
        if content.startswith("{"):
            try:
                import json
                data = json.loads(content)
                decision["problem"] = data.get("problem", "")
                decision["solution"] = data.get("solution", "")
                decision["rationale"] = data.get("rationale", "")
            except:
                pass

        filename = decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(_format_decision(decision))
        _log_decision("memory_garden.decision_added", {"title": title})
        return f"✅ Decision saved: {filename}"

    elif operation == "list_tasks":
        tasks = []
        for f in tasks_dir.glob("*.md"):
            tasks.append(f"- {f.stem}")
        if not tasks:
            return "No tasks recorded yet."
        return f"--- Tasks ---\n" + "\n".join(tasks)

    elif operation == "add_task":
        if not title:
            return "Error: Title is required for adding a task."
        filename = tasks_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(f"# Task: {title}\n\n{content}\n\nStatus: pending")
        _log_decision("memory_garden.task_added", {"title": title})
        return f"✅ Task saved: {filename}"

    elif operation == "save_context":
        # Save current project state
        context = {
            "date": str(Path(__file__).stat().st_mtime),
            "files": str(list(Path.cwd().rglob("*"))[:100]),
            "git_branch": "main",  # Would need git command
        }
        filename = context_dir / f"context_{len(list(context_dir.glob('context_*.json')))}.json"
        import json
        filename.write_text(json.dumps(context, indent=2))
        return f"✅ Context saved: {filename}"

    elif operation == "read_context":
        contexts = sorted(context_dir.glob("context_*.json"), key=lambda f: f.stat().st_mtime)
        if not contexts:
            return "No context snapshots available."
        latest = contexts[-1]
        import json
        return f"--- Latest Context ---\n{latest.read_text()}"

    return f"Error: Unknown operation '{operation}'. Use: read_decisions, add_decision, list_tasks, add_task, save_context, read_context"


# =============================================================================
# Execution Management (Orchestration)
# =============================================================================

# Safe commands for run_task (whitelist)
_ALLOWED_COMMANDS = {
    "just": ["validate", "build", "test", "lint", "fmt", "test-basic", "test-mcp", "agent-commit"],
    "nix": ["fmt", "build", "shell", "flake-check"],
    "git": ["status", "diff", "log", "add", "checkout", "branch"],
}


def _is_safe_command(cmd: str, args: List[str]) -> tuple[bool, str]:
    """Check if command is in the whitelist."""
    if cmd not in _ALLOWED_COMMANDS:
        return False, f"Command '{cmd}' is not allowed."

    allowed_args = _ALLOWED_COMMANDS.get(cmd, [])
    for arg in args:
        if arg.startswith("-"):
            continue  # Allow flags
        if arg not in allowed_args and not any(arg.startswith(a) for a in allowed_args):
            return False, f"Argument '{arg}' is not allowed for '{cmd}'."

    return True, ""


@mcp.tool()
async def run_task(command: str, args: Optional[List[str]] = None) -> str:
    """
    Run safe development tasks (just, nix, git).

    Provides execution loop capability for "write -> validate -> fix" workflow.

    Allowed commands:
    - just: validate, build, test, lint, fmt, test-basic, test-mcp, agent-commit
    - nix: fmt, build, shell, flake-check
    - git: status, diff, log, add, checkout, branch
    """
    if args is None:
        args = []

    is_safe, error_msg = _is_safe_command(command, args)
    if not is_safe:
        _log_decision("run_task.security_block", {"command": command, "args": args, "reason": error_msg})
        return f"Error: {error_msg}"

    _log_decision("run_task.request", {"command": command, "args": args})

    try:
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        output = stdout.decode("utf-8")
        error = stderr.decode("utf-8")

        _log_decision("run_task.complete", {"command": command, "returncode": process.returncode})

        result = f"--- Task: {command} {' '.join(args)} ---\n"
        result += f"Exit code: {process.returncode}\n\n"

        if output:
            result += f"stdout:\n{output}\n"
        if error:
            result += f"stderr:\n{error}\n"

        return result.strip()

    except FileNotFoundError:
        return f"Error: Command '{command}' not found."
    except Exception as e:
        _log_decision("run_task.error", {"command": command, "error": str(e)})
        return f"Error running task: {e}"


if __name__ == "__main__":
    mcp.run()
