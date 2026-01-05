"""
src/agent/tools/orchestrator.py
MCP Interface for the Orchestrator.
Allows the LLM to delegate complex tasks to the internal Agentic OS.
"""

from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP, Context
from agent.core.orchestrator import Orchestrator

# Global instance for state retention
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get or create the global Orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        # Initialize with Sidecar/Headless support enabled by default in Server mode
        _orchestrator = Orchestrator()
    return _orchestrator


def register_orchestrator_tools(mcp: FastMCP):
    """Register Orchestrator capabilities as MCP tools."""

    @mcp.tool("delegate_mission")
    async def delegate_mission(
        query: str,
        context_files: List[str] = None,
        history: List[Dict[str, Any]] = None,
        ctx: Context = None,
    ) -> str:
        """
        DELEGATE a complex multi-step task to the Omni-Agentic OS.

        USE THIS TOOL WHEN:
        - The task requires multiple steps (e.g., edit file, then run test, then fix).
        - You want to use specialized agents (Coder, Reviewer).
        - You need 'Smart Mode' with self-correction.
        - You want real-time TUI visualization of progress.

        DO NOT USE THIS for simple single-file reads.

        Args:
            query: The mission description (e.g., "Fix the threading bug in main.py")
            context_files: Optional list of files relevant to the task
            history: Optional conversation history
        """
        orchestrator = get_orchestrator()

        # Build context dict
        context = {"relevant_files": context_files or []}

        # Dispatch! This triggers the whole Phase 18 TUI flow internally
        result = await orchestrator.dispatch(
            user_query=query, history=history or [], context=context
        )

        return result


__all__ = ["register_orchestrator_tools", "get_orchestrator"]
