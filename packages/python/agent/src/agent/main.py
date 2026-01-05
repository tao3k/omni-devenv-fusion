"""
src/agent/main.py
The Brain of the Omni-DevEnv.
Modular Interface: Configuration -> Registration -> Boot -> Run.

This file is a pure Composition Root - it only assembles modules and triggers boot sequence.
All business logic is delegated to atomic modules.

Phase 19: Supports --resume flag for session resumption.
"""

import os
import sys
import argparse
from mcp.server.fastmcp import FastMCP
import structlog

# 1. Core Infrastructure
from common.mcp_core import setup_logging, log_decision
from common.mcp_core.rich_utils import banner, section, tool_registered, tool_failed
from agent.core.context_loader import load_system_context
from agent.core.bootstrap import boot_core_skills, start_background_tasks

# 2. Capabilities (Domain Logic)
from agent.capabilities.product_owner import register_product_owner_tools
from agent.capabilities.librarian import register_librarian_tools
from agent.capabilities.harvester import register_harvester_tools
from agent.capabilities.skill_manager import register_skill_tools

# 3. Core Tools (Operational Logic)
from agent.tools.context import register_context_tools
from agent.tools.spec import register_spec_tools
from agent.tools.router import register_router_tools
from agent.tools.status import register_status_tool
from agent.tools.orchestrator import register_orchestrator_tools

# --- Initialization ---
# Enable headless mode for UXManager when running as MCP Server
os.environ["OMNI_UX_MODE"] = "headless"

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
_register("orchestrator", register_orchestrator_tools)

# Governance & Domain
_register("product_owner", register_product_owner_tools)
_register("librarian", register_librarian_tools)

# Evolution
_register("harvester", register_harvester_tools)
_register("skill_manager", register_skill_tools)


# --- Boot Sequence ---
def main():
    """Entry point for the orchestrator."""
    # Phase 19: Parse CLI arguments for session resumption
    parser = argparse.ArgumentParser(description="Omni Agentic OS - Orchestrator")
    parser.add_argument("--resume", type=str, help="Resume a specific session ID")
    parser.add_argument("--new", action="store_true", help="Force new session")
    parser.add_argument("--list-sessions", action="store_true", help="List all sessions")

    # Phase 20: Add dev subcommand
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    dev_parser = subparsers.add_parser("dev", help="Run Omni Dev Mode for feature development")
    dev_parser.add_argument("query", nargs="...", help="Feature request description")
    dev_parser.add_argument("--resume", type=str, help="Resume a specific session ID")

    args = parser.parse_args()

    # Handle session listing
    if args.list_sessions:
        from agent.core.session import SessionManager

        sessions = SessionManager.list_sessions()
        print("\n📼 Available Sessions:")
        for s in sessions:
            print(f"  - {s['session_id']} ({s['events']} events)")
        sys.exit(0)

    # Phase 20: Handle dev command
    if args.command == "dev":
        import asyncio
        from agent.core.workflows.dev_mode import create_dev_workflow

        # Build query from remaining args
        query = " ".join(args.query) if hasattr(args, "query") and args.query else ""

        if not query:
            print("Error: Please provide a feature request description")
            print("Usage: python -m agent.main dev 'Add a hello-world script'")
            sys.exit(1)

        # Initialize components
        session_id = args.resume
        workflow = create_dev_workflow()

        print(f"\n🚀 Starting Omni Dev Mode: {query}")

        # Run the workflow
        asyncio.run(workflow.run(query))
        sys.exit(0)

    from rich.console import Console

    console = Console(stderr=True)

    # Phase 19: Show session info
    session_id = args.resume
    if session_id:
        console.print(f"🔄 Resuming session: [bold]{session_id}[/bold]")
    else:
        console.print(banner("Orchestrator", "The Modular Brain", "🧠"))

    # 1. Boot Skills (Fixes 'Lobotomized Agent')
    section("Booting Kernel...")
    boot_core_skills(mcp)

    # 2. Register Dynamic Context Resource
    # This exposes all loaded skill prompts.md as an MCP Resource
    section("Registering Dynamic Context...")
    from agent.core.skill_registry import get_skill_registry

    @mcp.resource("omni://system/active_context")
    def get_active_context() -> str:
        """
        Returns the dynamic system prompts and routing rules for all active skills.
        READ THIS at the start of the session to understand your capabilities.
        """
        registry = get_skill_registry()
        return registry.get_combined_context()

    # 3. Start Background Tasks
    start_background_tasks()

    # 4. Run Server
    section("System Online")
    mcp.run()


# --- Interactive CLI Mode ---
async def run_cli_loop():
    """
    Interactive CLI loop with session support.

    Usage:
        python -m agent.main --cli
        python -m agent.main --cli --resume <session_id>
    """
    import asyncio
    from agent.core.orchestrator import Orchestrator
    from agent.core.session import SessionManager

    parser = argparse.ArgumentParser(description="Omni Agentic OS - Interactive Mode")
    parser.add_argument("--resume", type=str, help="Resume a specific session ID")
    parser.add_argument("--new", action="store_true", help="Force new session")
    args = parser.parse_args()

    console = Console()

    # Initialize orchestrator with session
    session_id = args.resume if args.resume else None
    orchestrator = Orchestrator(session_id=session_id)

    console.print(f"🤖 Omni Online | Session: [bold]{orchestrator.session.session_id}[/bold]")

    if session_id:
        history = orchestrator.session.get_history()
        console.print(f"🔄 Context Resumed ({len(history)} messages)")

    history = []

    while True:
        try:
            user_input = input("\n🎤 You: ")
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("👋 Goodbye!")
                console.print(
                    f"💰 Session cost: ${orchestrator.session.telemetry.total_usage.cost_usd:.4f}"
                )
                break

            response = await orchestrator.dispatch(user_input, history)
            console.print(f"\n🤖 Agent: {response}")

            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            # Keep history manageable
            if len(history) > 20:
                history = history[-20:]

        except KeyboardInterrupt:
            console.print("\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
