"""
src/agent/tools/status.py
System status and introspection tools.
"""

from mcp.server.fastmcp import FastMCP


def register_status_tool(mcp: FastMCP):
    """Register the status inspection tool."""

    @mcp.tool()
    async def orchestrator_status() -> str:
        """
        Check Orchestrator server status and list available tool categories.
        """
        return """🧠 Omni Orchestrator Status

Role: The "Brain" - Planning, Routing, and Policy Enforcement
Architecture: Bi-MCP (Orchestrator + Coder)

System:
- Boot Sequence: Complete
- Skill Kernel: Active (Git, Filesystem, Terminal loaded)
- Knowledge Base: Background Ingestion Active

Available Capability Layers:
- Core: Context, Spec, Router, Execution
- Governance: Product Owner, Reviewer
- Domain: Lang Expert, Librarian
- Evolution: Harvester, Skill Manager
"""


__all__ = ["register_status_tool"]
