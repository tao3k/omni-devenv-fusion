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

This server uses common/mcp_core for:
- memory: ProjectMemory for persistence
- inference: InferenceClient and personas
- utils: Logging and path checking
"""
import asyncio
from mcp.server.fastmcp import FastMCP
import structlog

# Import shared modules from common/mcp_core
from common.mcp_core import (
    setup_logging,
    log_decision,
    ProjectMemory,
    PERSONAS,
    build_persona_prompt,
)

# Phase 13.8: Configuration-Driven Context
from agent.core.context_loader import load_system_context

# GitOps - Project root detection (single source of truth)
from common.mcp_core.gitops import get_project_root

# Rich utilities for beautiful terminal output
from common.mcp_core.rich_utils import banner, section, tool_registered, tool_failed

# Import capabilities (tool registration modules)
from agent.capabilities.product_owner import register_product_owner_tools
from agent.capabilities.lang_expert import register_lang_expert_tools
from agent.core.reviewer import register_reviewer_tools
from agent.capabilities.librarian import register_librarian_tools
from agent.capabilities.harvester import register_harvester_tools  # Phase 12
from agent.capabilities.skill_manager import register_skill_tools  # Phase 13: Dynamic Skills

# Import tool modules (structured tools)
from agent.tools.context import register_context_tools
from agent.tools.spec import register_spec_tools
from agent.tools.router import register_router_tools
from agent.tools.commit import register_commit_tools
from agent.tools.execution import register_execution_tools

# Initialize logging
setup_logging()
logger = structlog.get_logger(__name__)

# Phase 13.8: Load system context from configuration files
system_prompt = load_system_context()

# Initialize MCP Server with dynamic system prompt
mcp = FastMCP(
    "omni-orchestrator",
    instructions=system_prompt
)

# Initialize project memory
project_memory = ProjectMemory()


def _register_tool_module(module_name: str, register_func):
    """Helper to register tools with error handling."""
    try:
        register_func(mcp)
        log_decision(f"{module_name}.registered", {}, logger)
        tool_registered(module_name, 0)  # Count would require introspection
        return True
    except Exception as e:
        log_decision(f"{module_name}.registration_failed", {"error": str(e)}, logger)
        tool_failed(module_name, str(e))
        return False


# =============================================================================
# Tool Registration - Modular Architecture
# =============================================================================

# 1. Core Context Tools
_register_tool_module("context", register_context_tools)

# 2. Spec Management Tools
_register_tool_module("spec", register_spec_tools)

# 3. Router Tools
_register_tool_module("router", register_router_tools)

# 4. Commit Workflow Tools
_register_tool_module("commit", register_commit_tools)

# 5. Execution Tools
_register_tool_module("execution", register_execution_tools)

# 6. Product Owner (Standards Enforcement)
_register_tool_module("product_owner", register_product_owner_tools)

# 7. Language Expert (Language Standards)
_register_tool_module("lang_expert", register_lang_expert_tools)

# 8. Reviewer (The Immune System)
_register_tool_module("reviewer", register_reviewer_tools)

# 9. Librarian (Knowledge Base / RAG)
_register_tool_module("librarian", register_librarian_tools)

# 10. Harvester (Phase 12: The Cycle of Evolution)
_register_tool_module("harvester", register_harvester_tools)

# 11. Skill Manager (Phase 13: Dynamic Skills)
_register_tool_module("skill_manager", register_skill_tools)


# =============================================================================
# Knowledge Base Auto-Bootstrap (Background)
# =============================================================================

def _init_knowledge_base():
    """Initialize knowledge base with project documentation."""
    try:
        from agent.capabilities.knowledge_ingestor import ingest_all_knowledge
        from agent.capabilities.librarian import bootstrap_knowledge as _bootstrap_knowledge

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _bootstrap():
            try:
                # Ingest project knowledge files
                ingest_result = await ingest_all_knowledge()
                log_decision("knowledge_base.ingested", {
                    "files": ingest_result.get("total_ingested", 0),
                }, logger)

                # Bootstrap core knowledge
                await _bootstrap_knowledge()
                log_decision("knowledge_base.bootstrapped", {}, logger)
            except Exception as e:
                log_decision("knowledge_base.init_failed", {"error": str(e)}, logger)

        loop.run_until_complete(_bootstrap())
        loop.close()
    except Exception:
        pass  # Ignore initialization errors


import threading
thread = threading.Thread(target=_init_knowledge_base, daemon=True)
thread.start()


# =============================================================================
# Orchestrator Self-Description
# =============================================================================

@mcp.tool()
async def orchestrator_status() -> str:
    """Check Orchestrator server status and list available tools."""
    return f"""🧠 Omni Orchestrator Status

Role: The "Brain" - Planning, Routing, and Policy Enforcement
Architecture: Tri-MCP (Orchestrator + Executor + Coder)

Available Tool Categories:
- Context: manage_context, get_project_instructions
- Spec: start_spec, draft_feature_spec, verify_spec_completeness, archive_spec_to_doc
- Router: consult_router, swarm_status, community_proxy
- Commit: spec_aware_commit (generates message, client confirms)
- Execution: run_task, analyze_last_error
- Product Owner: start_spec enforcement, complexity assessment
- Language Expert: consult_language_expert, get_language_standards
- Reviewer: review_staged_changes
- Librarian: consult_knowledge_base, ingest_knowledge, bootstrap_knowledge
- Skills: list_available_skills, load_skill, get_active_skills

Note: This server handles PLANNING and ROUTING only.
      Execution is handled by the Executor.
      File operations are handled by the Coder.
"""


if __name__ == "__main__":
    # Print Rich-styled startup banner
    from rich.console import Console
    console = Console(stderr=True)
    console.print(banner(
        "Orchestrator MCP Server",
        "The Brain - Planning without execution",
        "🧠"
    ))
    section("Initializing Tools...")
    mcp.run()
