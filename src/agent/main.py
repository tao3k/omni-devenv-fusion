"""
src/agent/main.py
The Brain of the Omni-DevEnv.
Modular Interface: Configuration -> Registration -> Boot -> Run.

This file is a pure Composition Root - it only assembles modules and triggers boot sequence.
All business logic is delegated to atomic modules.
"""
from mcp.server.fastmcp import FastMCP
import structlog

# 1. Core Infrastructure
from common.mcp_core import setup_logging, log_decision
from common.mcp_core.rich_utils import banner, section, tool_registered, tool_failed
from agent.core.context_loader import load_system_context
from agent.core.bootstrap import boot_core_skills, start_background_tasks

# 2. Capabilities (Domain Logic)
from agent.capabilities.product_owner import register_product_owner_tools
from agent.capabilities.lang_expert import register_lang_expert_tools
from agent.capabilities.librarian import register_librarian_tools
from agent.capabilities.harvester import register_harvester_tools
from agent.capabilities.skill_manager import register_skill_tools
from agent.core.reviewer import register_reviewer_tools

# 3. Core Tools (Operational Logic)
from agent.tools.context import register_context_tools
from agent.tools.spec import register_spec_tools
from agent.tools.router import register_router_tools
from agent.tools.status import register_status_tool

# --- Initialization ---
setup_logging()
logger = structlog.get_logger(__name__)

# Load System Prompt (from settings.yaml via context_loader)
system_prompt = load_system_context()

# Initialize Server
mcp = FastMCP("omni-orchestrator", instructions=system_prompt)

# --- Helper ---
def _register(module_name: str, register_func):
    """Standardized registration interface."""
    try:
        register_func(mcp)
        tool_registered(module_name, 0)
    except Exception as e:
        tool_failed(module_name, str(e))
        logger.error(f"Failed to register {module_name}", error=str(e))

# --- Module Registration (The Interface) ---

# Core
_register("context", register_context_tools)
_register("spec", register_spec_tools)
_register("router", register_router_tools)
_register("status", register_status_tool)

# Governance & Domain
_register("product_owner", register_product_owner_tools)
_register("reviewer", register_reviewer_tools)
_register("lang_expert", register_lang_expert_tools)
_register("librarian", register_librarian_tools)

# Evolution
_register("harvester", register_harvester_tools)
_register("skill_manager", register_skill_tools)

# --- Boot Sequence ---
if __name__ == "__main__":
    from rich.console import Console
    console = Console(stderr=True)
    console.print(banner("Orchestrator", "The Modular Brain", "🧠"))

    # 1. Boot Skills (Fixes 'Lobotomized Agent')
    section("Booting Kernel...")
    boot_core_skills(mcp)

    # 2. Start Background Tasks
    start_background_tasks()

    # 3. Run Server
    section("System Online")
    mcp.run()
