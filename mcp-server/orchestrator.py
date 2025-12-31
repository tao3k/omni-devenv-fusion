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

This server uses mcp_core shared library for:
- execution: SafeExecutor for command execution
- memory: ProjectMemory for persistence
- inference: InferenceClient and personas
- utils: Logging and path checking
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Import shared modules from mcp_core
from mcp_core import (
    setup_logging,
    log_decision,
    is_safe_path,
    SafeExecutor,
    ProjectMemory,
    InferenceClient,
    PERSONAS,
    build_persona_prompt,
)

# =============================================================================
# Configuration
# =============================================================================

LOG_LEVEL = os.environ.get("ORCHESTRATOR_LOG_LEVEL", "INFO").upper()
logger = setup_logging(level=LOG_LEVEL, server_name="orchestrator")

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")
REQUEST_TIMEOUT = float(os.environ.get("ORCHESTRATOR_TIMEOUT", "30"))

mcp = FastMCP("orchestrator-tools")

sys.stderr.write(f"🚀 Orchestrator Server starting... PID: {os.getpid()}\n")

if not API_KEY:
    sys.stderr.write("⚠️ Warning: ANTHROPIC_API_KEY not found in environment.\n")

# Initialize shared clients
inference_client = InferenceClient(api_key=API_KEY, base_url=BASE_URL)
project_memory = ProjectMemory()


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
        log_decision("get_codebase_context.security_block", {"target_dir": target_dir}, logger)
        return error_msg

    # Use .cache/ directory for repomix output (following numtide/prj-spec)
    cache_dir = Path(target_dir) / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_path = str(cache_dir / "repomix-output.xml")

    log_decision("get_codebase_context.request", {"target_dir": target_dir, "temp_path": temp_path}, logger)

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

        log_decision("get_codebase_context.success", {"length": len(content)}, logger)
        return f"--- Codebase Context ({target_dir}) ---\n{content}"

    except FileNotFoundError:
        return "Error: 'repomix' command not found. Please ensure it is installed."
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        log_decision("get_codebase_context.exception", {"error": str(e)}, logger)
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
        log_decision("list_directory_structure.security_block", {"root_dir": root_dir}, logger)
        return error_msg

    target_path = Path(root_dir)

    if not target_path.exists():
        return f"Error: Directory '{root_dir}' does not exist."
    if not target_path.is_dir():
        return f"Error: '{root_dir}' is not a directory."

    try:
        log_decision("list_directory_structure.request", {"root_dir": root_dir}, logger)

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
                log_decision("list_directory_structure.success", {"method": "tree"}, logger)
                return f"--- Directory Structure ({root_dir}) ---\n{result}"
        except FileNotFoundError:
            pass

        # Fallback to Python implementation
        tree_output = _build_directory_tree(root_dir, max_depth=3)
        log_decision("list_directory_structure.success", {"method": "python"}, logger)

        if not tree_output.strip():
            return f"--- Directory Structure ({root_dir}) ---\n[Empty directory]"

        return f"--- Directory Structure ({root_dir}) ---\n{tree_output}"

    except Exception as e:
        log_decision("list_directory_structure.exception", {"error": str(e)}, logger)
        return f"Error listing directory structure: {str(e)}"


# =============================================================================
# Persona Routing (Orchestration)
# =============================================================================

@mcp.tool()
async def list_personas() -> str:
    """List available expert personas for consultation."""
    persona_list = [
        {
            "id": role,
            "name": details.get("name"),
            "description": details.get("description"),
            "when_to_use": details.get("when_to_use"),
            "context_hints": details.get("context_hints", []),
        }
        for role, details in PERSONAS.items()
    ]
    log_decision("list_personas", {"count": len(persona_list)}, logger)
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

    system_prompt = build_persona_prompt(role)
    log_decision("consult_specialist.request", {"role": role}, logger)

    try:
        response = await asyncio.wait_for(
            inference_client.complete(system_prompt, query),
            timeout=REQUEST_TIMEOUT
        )

        if response["success"]:
            log_decision("consult_specialist.success", {"role": role}, logger)
            return f"--- 🤖 Expert Opinion: {role.upper()} ---\n{response['content']}"
        else:
            log_decision("consult_specialist.error", {"role": role, "error": response["error"]}, logger)
            return f"Error: {response['error']}"

    except asyncio.TimeoutError:
        log_decision("consult_specialist.timeout", {"role": role}, logger)
        return f"Request timed out after {REQUEST_TIMEOUT} seconds."
    except Exception as exc:
        log_decision("consult_specialist.error", {"role": role, "error": str(exc)}, logger)
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
    log_decision("delegate_to_coder.request", {"task_type": task_type, "details": details[:200]}, logger)

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
    log_decision("community_proxy.request", {"mcp_name": mcp_name, "query": query[:200]}, logger)

    if mcp_name not in _SUPPORTED_COMMUNITY_MCPS:
        available = ", ".join(_SUPPORTED_COMMUNITY_MCPS.keys())
        return f"Error: Unknown MCP '{mcp_name}'. Supported: {available}"

    mcp_config = _SUPPORTED_COMMUNITY_MCPS[mcp_name]
    cmd = mcp_config["command"]
    args = mcp_config["args"]

    try:
        process = await asyncio.create_subprocess_exec(
            cmd, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
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
# Safe Sandbox (uses mcp_core.execution.SafeExecutor)
# =============================================================================

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

    log_decision("safe_sandbox.request", {"command": command, "timeout": timeout, "read_only": read_only}, logger)

    result = await SafeExecutor.run_sandbox(
        command=command,
        args=args,
        timeout=timeout,
        read_only=read_only,
    )

    return SafeExecutor.format_result(result, command, args)


# =============================================================================
# Memory Persistence (uses mcp_core.memory.ProjectMemory)
# =============================================================================

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
    log_decision("memory_garden.request", {"operation": operation, "title": title}, logger)

    if operation == "read_decisions":
        return project_memory.format_decisions_list()

    elif operation == "add_decision":
        result = project_memory.add_decision(title=title, content=content)
        if result["success"]:
            return f"✅ Decision saved: {result['file']}"
        return f"Error: {result['error']}"

    elif operation == "list_tasks":
        return project_memory.format_tasks_list()

    elif operation == "add_task":
        result = project_memory.add_task(title=title, content=content)
        if result["success"]:
            return f"✅ Task saved: {result['file']}"
        return f"Error: {result['error']}"

    elif operation == "save_context":
        result = project_memory.save_context()
        if result["success"]:
            return f"✅ Context saved: {result['file']}"
        return f"Error: {result['error']}"

    elif operation == "read_context":
        context = project_memory.get_latest_context()
        if context:
            return f"--- Latest Context ---\n{json.dumps(context, indent=2)}"
        return "No context snapshots available."

    return f"Error: Unknown operation '{operation}'. Use: read_decisions, add_decision, list_tasks, add_task, save_context, read_context"


# =============================================================================
# Execution Management (uses mcp_core.execution.SafeExecutor)
# =============================================================================

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

    log_decision("run_task.request", {"command": command, "args": args}, logger)

    result = await SafeExecutor.run(command=command, args=args)

    return SafeExecutor.format_result(result, command, args)


if __name__ == "__main__":
    mcp.run()
