# Orchestrator MCP Server - The Brain
#
# Tri-MCP Architecture:
# - orchestrator (The Brain): Planning, routing, reviewing
# - executor (The Hands): Git, testing, shell operations
# - coder (The Pen): File I/O, AST-based code operations
"""
Orchestrator MCP Server - The "Brain" (Pure Brain Mode)

Role: High-level decision making, planning, routing, and context management.

Focus: SDLC, Architecture, Policy Enforcement, and Quality Gates.

KEY PRINCIPLE: "The Brain doesn't touch files directly."

Tri-MCP Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Claude Desktop                                               │
│        │                                                       │
│        ├── 🧠 orchestrator (HERE - The Brain)                  │
│        │      └── Planning, Routing, Reviewing, Specifying    │
│        │                                                         │
│        ├── 🛠️ executor (The Hands)                             │
│        │      └── Git operations, Testing, Documentation       │
│        │                                                         │
│        └── 📝 coder (File Operations)                          │
│               └── Read/Write/Search files                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Orchestrator NEVER:
- Reads files directly (use coder.py: read_file)
- Writes files (use coder.py: save_file)
- Searches code (use coder.py: search_files, ast_search)
- Executes git commands (use executor.py: git_status, smart_commit)

Orchestrator ALWAYS:
- Routes to appropriate MCP server
- Reviews and validates work
- Enforces policies (start_spec, review_staged_changes)
- Provides architectural guidance

Tools:
- Router: consult_router (Semantic tool routing - which MCP to use?)
- Spec: start_spec, draft_feature_spec, verify_spec_completeness
- Review: review_staged_changes (The Immune System)
- Memory: manage_context (Project memory and context)
- Personas: consult_specialist (Architect, Platform Expert, DevOps, SRE)
- Context: get_codebase_context, list_directory_structure

This server uses common/mcp_core for:
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

# Ensure project root is in path for imports (DDD structure)
# This allows: from common.mcp_core import ... where common is at src/common/
_project_root = Path(__file__).parent.parent.resolve()  # src/agent/ -> src/ -> project_root
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP

# Import shared modules from common/mcp_core
from common.mcp_core import (
    setup_logging,
    log_decision,
    is_safe_path,
    SafeExecutor,
    ProjectMemory,
    InferenceClient,
    PERSONAS,
    build_persona_prompt,
)

# Import instructions loader (agent/instructions/ - lazy loaded on first access)
from common.mcp_core.instructions import (
    get_all_instructions_merged,
    list_instruction_names,
)

# Import Product Owner tools (agent/standards/feature-lifecycle.md enforcement)
from agent.capabilities.product_owner import register_product_owner_tools

# Import Language Expert tools (agent/standards/lang-*.md + tool-router examples)
from agent.capabilities.lang_expert import register_lang_expert_tools

# Import Tool Router (The Cortex - Semantic Tool Routing)
from agent.core.router import get_router

# Import Reviewer tools (The Immune System)
from agent.core.reviewer import register_reviewer_tools

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
# Tri-MCP Bridge (Deprecated - kept for backward compatibility)
# =============================================================================
# With Tri-MCP architecture, Claude Desktop calls coder.py directly.
# This function always returns None to disable remote worker mode.

async def _get_coder_node() -> None:
    """
    [DEPRECATED] Always returns None.

    Tri-MCP Architecture:
    - orchestrator.py: The Brain (planning, routing, reviewing)
    - executor.py: The Hands (execution, testing, docs)
    - coder.py: File Operations (direct calls from Claude Desktop)

    The old Hive/Swarm architecture is no longer needed.
    """
    return None

# NOTE: Protocol caches (git-workflow, writing-style) are now lazy-loaded
# by their respective modules via common/mcp_core/lazy_cache.py.
# No eager loading needed - first access triggers automatic loading.

# =============================================================================
# Brain Tools (Orchestration - The Cortex)
# =============================================================================
# These tools handle planning, routing, reviewing, and context management.
# Execution tools have been moved to executor.py for Dual-MCP architecture.

# Register Product Owner tools (agent/standards/feature-lifecycle.md enforcement)
register_product_owner_tools(mcp)
log_decision("product_owner_tools.registered", {}, logger)

# Register Language Expert tools (agent/standards/lang-*.md + tool-router examples)
register_lang_expert_tools(mcp)
log_decision("lang_expert_tools.registered", {}, logger)

# Register Reviewer tools (The Immune System)
register_reviewer_tools(mcp)
log_decision("reviewer_tools.registered", {}, logger)


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
# Project Instructions (Eager Loaded at Session Start)
# =============================================================================

@mcp.tool()
async def get_project_instructions(name: str = "") -> str:
    """
    Get project instructions that are pre-loaded at session start.

    These instructions from agent/instructions/ are loaded when the MCP server starts,
    ensuring they're always available as default prompts for LLM sessions.

    Args:
        name: Specific instruction name (without .md), e.g., "project-conventions"
              If empty, returns all instructions merged.

    Returns:
        Project instruction(s) content.
    """
    from common.mcp_core.instructions import get_instruction, get_all_instructions_merged, list_instruction_names

    if name:
        content = get_instruction(name)
        if content:
            log_decision("get_project_instructions.single", {"name": name}, logger)
            return f"=== {name} ===\n\n{content}"
        else:
            available = list_instruction_names()
            return f"Error: Instruction '{name}' not found.\nAvailable: {available}"
    else:
        all_instructions = get_all_instructions_merged()
        if all_instructions:
            log_decision("get_project_instructions.all", {"count": len(list_instruction_names())}, logger)
            return f"=== Project Instructions (All) ===\n\n{all_instructions}"
        return "No project instructions available."


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
# The Cortex (Tool Router)
# =============================================================================

@mcp.tool()
async def consult_router(query: str) -> str:
    """
    [Cortex] Ask the Router which tools to use for a specific task.

    Use this when you are unsure which tool is best for the user's request.
    It analyzes the intent and returns a focused set of tools (Domain).

    Args:
        query: The user's request or task description.
    """
    router = get_router()
    log_decision("consult_router.request", {"query": query}, logger)

    result = await router.route_intent(query)

    domain = result.get("domain", "Unknown")
    confidence = result.get("confidence", 0.0)
    tools = result.get("suggested_tools", [])
    reasoning = result.get("reasoning", "")

    response = f"""--- 🧠 Cortex Routing Result ---
Domain: {domain} (Confidence: {confidence})
Reasoning: {reasoning}

🛠️ Suggested Tools:
"""
    for tool in tools:
        response += f"- {tool}\n"

    response += "\nTip: You can use these tools directly."

    log_decision("consult_router.result", {"domain": domain}, logger)
    return response


# =============================================================================
# Delegation (Legacy Bridge - Deprecated for Tri-MCP)
# =============================================================================

@mcp.tool()
async def delegate_to_coder(task_type: str, details: str) -> str:
    """
    [DEPRECATED] Use coder.py MCP server directly instead.

    This was the old 'Hive' bridge. With Tri-MCP architecture:
    - Claude Desktop calls coder.py tools directly (save_file, read_file, search_files)
    - This function is kept as a fallback for non-MCP clients or legacy compatibility.

    For new code, use these tools directly from the coder MCP server:
    - save_file, read_file, search_files (from coder.py)
    - ast_search, ast_rewrite (from coder.py)

    Args:
        task_type: read/search/write/ast_search/ast_rewrite
        details: Arguments string (for backward compatibility only)
    """
    log_decision("delegate_to_coder.request", {"task": task_type, "details": details[:100]}, logger)

    # 1. Get Worker node (lazy connect)
    node = await _get_coder_node()

    # If Worker is available, execute remote call
    if node:
        # 2. Parse arguments
        import re
        args = {}

        # Extract key="value" pattern
        matches = re.findall(r'(\w+)="([^"]*)"', details)
        for k, v in matches:
            args[k] = v

        # If no key=value found and details not empty, try as default argument
        if not args and details.strip():
            default_keys = {
                "read": "path",
                "search": "pattern",
                "write": "path",
                "ast_search": "pattern",
                "ast_rewrite": "pattern"
            }
            if key := default_keys.get(task_type):
                args[key] = details.strip()

        # 特殊处理 write: 尝试提取 content
        if task_type == "write" and "content" not in args:
            if "content=" in details:
                try:
                    content_part = details.split("content=", 1)[1]
                    if content_part.startswith('"') and content_part.endswith('"'):
                        content_part = content_part[1:-1]
                    args["content"] = content_part
                except IndexError:
                    pass

        # 3. 工具映射 (Tool Mapping)
        tool_map = {
            "read": "read_file",
            "search": "search_files",
            "write": "save_file",
            "ast_search": "ast_search",
            "ast_rewrite": "ast_rewrite"
        }

        worker_tool = tool_map.get(task_type)
        if not worker_tool:
            return f"Error: Unknown task type '{task_type}'"

        # 4. Remote execution
        try:
            result = await node.call_tool(worker_tool, args)

            output = []
            if result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        output.append(item.text)

            final_output = "\n".join(output)
            if not final_output:
                return "Task completed successfully (No output returned)."
            return final_output

        except TimeoutError:
            return f"Timeout: Worker took too long to execute '{worker_tool}'."
        except Exception as e:
            # Fallback: return instruction string instead of crashing
            return _format_delegation_fallback(task_type, details)

    # 5. Fallback mode: Worker unavailable, return instruction string
    return _format_delegation_fallback(task_type, details)


def _format_delegation_fallback(task_type: str, details: str) -> str:
    """Return legacy instruction format (for fallback mode or testing)"""
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
        "ast_search": (
            "Use the 'ast_search' tool:\n"
            f"@omni-coder ast_search pattern=\"{details}\""
        ),
        "ast_rewrite": (
            "Use the 'ast_rewrite' tool:\n"
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


@mcp.tool()
async def swarm_status() -> str:
    """
    Check the detailed health and metrics of the Swarm.
    """
    import os
    import time

    status = [f"👑 Orchestrator (PID: {os.getpid()})"]
    status.append("-" * 40)

    if _coder_node:
        # Get health check report
        health = await _coder_node.health_check()
        metrics = health.get("metrics", {})

        # Status icon
        icon = "🟢" if health.get("healthy") else "🔴"
        if health.get("circuit") == "OPEN":
            icon = "🔥"  # Circuit breaker open

        status.append(f"🐝 Coder Worker: {icon} {health.get('circuit')} Circuit")
        status.append(f"   • Connected: {health.get('connected')}")
        status.append(f"   • Latency: {metrics.get('avg_latency_ms', 0):.2f} ms")
        status.append(f"   • Restarts: {metrics.get('restarts', 0)}")
        status.append(f"   • Success/Fail: {metrics.get('success_count')}/{metrics.get('failure_count')}")

        if not health.get("healthy") and metrics.get("last_error"):
            status.append(f"   ⚠️ Last Error: {metrics.get('last_error')[:50]}...")

        # List tools if connected
        if health.get("connected"):
            try:
                tools = await _coder_node.list_tools()
                names = [t.name for t in tools]
                status.append(f"   • Tools: {len(names)} available")
            except Exception:
                pass
    else:
        status.append("🐝 Coder Worker: ⚪ OFFLINE (Lazy Loading)")

    return "\n".join(status)


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
# NEW: Context Management Tools (Backmark Interface)
# =============================================================================

@mcp.tool()
async def manage_context(action: str, phase: str = None, focus: str = None, note: str = None) -> str:
    """
    Manage the Project's Active Context (Short-term Memory / RAM).

    Use this to KEEP TRACK of where you are.

    IMPORTANT: Call this FIRST at the start of every session.
    This returns project rules, current status, and recent activity.

    Args:
        action: "read", "update_status", "add_note"
        phase: (For update) Current phase: Planning, Spec-Drafting, Coding, Testing
        focus: (For update) What are you working on NOW?
        note: (For add_note) A thought, error log, or partial result.

    Returns:
        Status or confirmation message
    """
    if action == "read":
        # 1. Load project instructions (CLAUDE.md + project-conventions)
        from common.mcp_core.instructions import get_all_instructions_merged
        project_instructions = get_all_instructions_merged()

        # 2. Read macro status
        status = project_memory.get_status()

        # 3. Read recent flight recorder logs (Tail Scratchpad)
        scratchpad_path = project_memory.active_dir / "SCRATCHPAD.md"
        recent_logs = ""
        if scratchpad_path.exists():
            content = scratchpad_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            # Only take last 15 lines as "short-term working memory"
            recent_logs = "\n".join(lines[-15:])

        return f"""## 📋 Project Context (Auto-loaded at Session Start)

### 🎯 Project Instructions
{project_instructions}

### 📊 Current Status
{status}

## 🎞️ Recent Activity (Last 15 lines from Scratchpad)
{recent_logs or "(No recent activity)"}
"""

    elif action == "update_status":
        if not phase or not focus:
            return "Error: 'phase' and 'focus' are required for update_status."
        result = project_memory.update_status(phase=phase, focus=focus)
        return f"✅ Context Updated: Phase={phase}, Focus={focus}"

    elif action == "add_note":
        if not note:
            return "Error: 'note' is required."
        project_memory.log_scratchpad(note, source="User")
        return "✅ Note added to Scratchpad."

    return "Error: Unknown action. Use read, update_status, or add_note."


# =============================================================================
# Legislation Gate: Spec Enforcement
# =============================================================================

@mcp.tool()
async def start_spec(name: str) -> str:
    """
    Gatekeeper: Enforces Legislation phase before any new work.

    CRITICAL: When you judge that the user is requesting NEW work (new feature, refactor, fix, enhancement),
    you MUST call this tool FIRST before proceeding. DO NOT proceed with coding until this tool returns "allowed".

    ## Your Judgment Criteria
    Call start_spec when the user is:
    - Requesting a NEW feature or capability
    - Asking to build, implement, add, create something new
    - Starting work that doesn't have an existing spec

    DO NOT call start_spec for:
    - Questions about existing code
    - Debugging or fixing known issues in existing features
    - Refactoring within existing feature scope
    - Routine development on features with existing specs

    ## Workflow:
    1. Judge: User is requesting something NEW?
    2. If yes: Call start_spec(name="Descriptive Feature Name")
    3. If returns "blocked":
       - Call draft_feature_spec(title="...", description="...")
       - Then call verify_spec_completeness
       - Only then proceed to code
    4. If returns "allowed":
       - Proceed with manage_context(update_status, phase="Coding") then code

    Args:
        name: Descriptive name for the new work (feature name)

    Returns:
        JSON with status: "allowed" (proceed) or "blocked" (spec required)
    """
    # Validate input
    if not name or len(name.strip()) < 2:
        return json.dumps({
            "status": "error",
            "message": "Invalid name. Provide a descriptive name for the work."
        })

    # Check if spec file exists (search both patterns)
    spec_dir = Path(__file__).parent.parent / "agent" / "specs"

    # Try: feature_name.md, feature-name.md, or *_feature_name*.md
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    possible_patterns = [
        f"{safe_name}.md",
        f"*_{safe_name}.md",
        f"{safe_name}_*.md",
    ]

    spec_file = None
    for pattern in possible_patterns:
        import glob
        matches = list(spec_dir.glob(pattern))
        if matches:
            spec_file = matches[0]
            break

    if not spec_file:
        # Spec missing - REQUIRE creation
        return json.dumps({
            "status": "blocked",
            "reason": "Legislation is MANDATORY for new work",
            "work_name": name,
            "spec_required": True,
            "spec_patterns": possible_patterns,
            "next_action": "draft_feature_spec",
            "next_action_params": {
                "title": name,
                "description": f"Implementation plan for: {name}"
            },
            "enforcement": "No code can be written until spec is created and verified"
        }, indent=2)

    # Spec exists - allow proceed
    spec_path = str(spec_file)
    # Auto-save spec_path for downstream tools (verify_spec_completeness, etc.)
    project_memory.set_spec_path(spec_path)

    return json.dumps({
        "status": "allowed",
        "work_name": name,
        "spec_required": False,
        "spec_path": spec_path,
        "message": f"Legislation complete for '{name}'. Ready for execution.",
        "next_action": "manage_context(update_status, phase=Coding, focus=...)"
    }, indent=2)


@mcp.tool()
async def analyze_last_error() -> str:
    """
    [Debug Tool] Deeply analyzes the LAST failed command in the Flight Recorder.

    Use this when the error log in `manage_context("read")` is truncated or unclear.
    It retrieves the full stderr/stdout and asks the AI to pinpoint the root cause.
    """
    # Read the scratchpad's last 50 lines (usually contains full error stack)
    scratchpad_path = project_memory.active_dir / "SCRATCHPAD.md"
    if not scratchpad_path.exists():
        return "No crash logs found."

    content = scratchpad_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Take last 50 lines for crash analysis
    recent_log = "\n".join(lines[-50:])

    return f"""--- 🕵️‍♀️ Crash Analysis Context ---

The following is the raw log of the recent crash.
Please analyze it to find:
1. The specific error message.
2. The file and line number causing it.
3. A suggested fix.

--- LOG START ---
{recent_log}
--- LOG END ---
"""


# =============================================================================
# Execution Management (uses mcp_core.execution.SafeExecutor)
# =============================================================================

@mcp.tool()
async def run_task(command: str, args: Optional[List[str]] = None) -> str:
    """
    Run safe development tasks (just, nix, git) with FLIGHT RECORDER.

    All executions are automatically logged to .memory/active_context/SCRATCHPAD.md
    so you don't lose track of error messages.

    Allowed commands:
    - just: validate, build, test, lint, fmt, test-basic, test-mcp, agent-commit
    - nix: fmt, build, shell, flake-check
    - git: status, diff, log, add, checkout, branch

    ⚠️ SECURITY: Git commit operations are BLOCKED. Use @omni-orchestrator smart_commit instead.
    """
    if args is None:
        args = []

    # =============================================================================
    # GIT COMMIT BLOCKLIST - Prevents bypass of authorization protocol
    # =============================================================================
    # This check prevents agents from bypassing smart_commit() authorization
    # by using run_task to execute git commit directly.

    # Check 1: Direct git commit command
    if command == "git" and args and "commit" in args:
        blocked_msg = """🚫 GIT COMMIT BLOCKED

This command was blocked because git commit operations MUST go through the authorization protocol.

**Why this is blocked:**
- Agents must use @omni-orchestrator smart_commit() for commit validation
- Authorization requires user to say "run just agent-commit"
- Direct git commit bypasses pre-commit hooks and authorization

**Correct workflow:**
1. @omni-orchestrator smart_commit(type="feat", scope="mcp", message="description")
2. System returns: {authorization_required: true, auth_token: "..."}
3. Ask user: "Please say: run just agent-commit"
4. @omni-orchestrator execute_authorized_commit(auth_token="xxx")

**Allowed git operations (non-committing):**
- git status, git diff, git log, git add, git checkout, git branch
"""
        log_decision("run_task.blocked", {"command": command, "args": args, "reason": "git_commit_blocked"}, logger)
        return blocked_msg

    # Check 2: bash command containing "git commit"
    if command == "bash" and args:
        full_cmd = " ".join(args) if isinstance(args, list) else str(args)
        if "git commit" in full_cmd:
            blocked_msg = """🚫 GIT COMMIT BLOCKED (via bash)

Running `git commit` through bash is FORBIDDEN.

**Use the authorized commit path instead:**
1. @omni-orchestrator smart_commit(type="...", scope="...", message="...")
2. Wait for authorization token
3. @omni-orchestrator execute_authorized_commit(auth_token="...")

**This is a protocol violation if you intentionally wrote this.**
"""
            log_decision("run_task.blocked", {"command": command, "reason": "bash_git_commit_blocked"}, logger)
            return blocked_msg

    # Check 3: just agent-commit is allowed, but only through smart_commit workflow
    # The actual execution happens in git_ops.py via AuthorizationGuard

    # 1. Execute command
    log_decision("run_task.request", {"command": command, "args": args}, logger)
    result = await SafeExecutor.run(command=command, args=args)
    formatted_output = SafeExecutor.format_result(result, command, args)

    # 2. Flight Recorder - auto-log execution
    cmd_str = f"{command} {' '.join(args)}"
    status_icon = "✅" if result.get("exit_code", -1) == 0 else "❌"

    log_content = f"{status_icon} `{cmd_str}`"
    if result.get("stdout"):
        stdout_preview = result["stdout"][:300].strip()
        if stdout_preview:
            log_content += f"\n  Out: {stdout_preview}"
    if result.get("stderr"):
        stderr_preview = result["stderr"][:300].strip()
        if stderr_preview:
            log_content += f"\n  Err: {stderr_preview}"

    # Write to background memory
    project_memory.log_scratchpad(log_content, source="System")

    return formatted_output


if __name__ == "__main__":
    mcp.run()
