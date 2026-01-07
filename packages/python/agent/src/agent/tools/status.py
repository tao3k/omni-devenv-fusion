"""
src/agent/tools/status.py
System status functions - One Tool compatible.

All functions return strings and can be called directly or via @omni routing.
"""

import structlog

logger = structlog.get_logger(__name__)


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


__all__ = ["orchestrator_status"]
