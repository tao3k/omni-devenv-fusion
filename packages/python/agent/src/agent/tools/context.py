# agent/tools/context.py
"""
Context Management Tools

Provides project memory and context management for the orchestrator.

Tools:
- manage_context: Read/update project context
- get_project_instructions: Get project instructions
"""
import asyncio
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from common.mcp_core import (
    ProjectMemory,
    get_all_instructions_merged,
    list_instruction_names,
)
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Initialize project memory (singleton)
project_memory = ProjectMemory()

# For log_decision calls
def log_decision(event: str, data: Dict[str, Any], _logger) -> None:
    """Log a decision for audit trail."""
    _logger.info(event, **data)


def register_context_tools(mcp: FastMCP) -> None:
    """Register all context management tools."""

    @mcp.tool()
    async def manage_context(
        action: str,
        phase: Optional[str] = None,
        focus: Optional[str] = None,
        note: Optional[str] = None,
    ) -> str:
        """
        Manage the Project's Active Context (Short-term Memory / RAM).

        IMPORTANT: Call this FIRST at the start of every session.
        This returns project rules, current status, and recent activity.

        Args:
            action: "read", "update_status", "add_note"
            phase: Current phase (for update): Planning, Spec-Drafting, Coding, Testing
            focus: What are you working on NOW? (for update)
            note: A thought, error log, or partial result (for add_note)

        Returns:
            Status or confirmation message

        Examples:
            # At session start
            manage_context(action="read")

            # When starting a new task
            manage_context(action="update_status", phase="Coding", focus="Implement feature X")

            # When you encounter an error
            manage_context(action="add_note", note="Error: Connection timeout in module Y")
        """
        if action == "read":
            # 1. Read instructions (cached by mcp_core.instructions module)
            from common.mcp_core.instructions import get_instruction

            instructions = get_all_instructions_merged()

            # 2. Read macro status
            status = project_memory.get_status()

            logger.info("context.read")

            # 3. Read recent flight recorder logs (Tail Scratchpad)
            scratchpad_path = project_memory.active_dir / "SCRATCHPAD.md"
            recent_logs = ""
            if scratchpad_path.exists():
                content = scratchpad_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                # Show last 30 lines for context
                recent_logs = "\n".join(lines[-30:])
                if recent_logs:
                    recent_logs = f"\n\nRecent Activity (last 30 lines of SCRATCHPAD.md):\n{recent_logs}"

            return f"""=== 📋 Omni-DevEnv Fusion - Active Context ===

🎯 Current Mission:
{status.get('mission', 'No active mission')}

📍 Phase: {status.get('phase', 'Unknown')}
🔍 Focus: {status.get('focus', 'Not specified')}

📋 Backlog: {status.get('backlog', 'Empty')}

{recent_logs}

=== 📜 Project Instructions (from agent/instructions/) ===

{instructions}

=== 📝 Quick Reference ===

- Commit: Use @omni-orchestrator smart_commit (NOT git commit)
- Test: Use @omni-orchestrator smart_test_runner
- Route: Use @omni-orchestrator consult_router
- Review: Use @omni-orchestrator review_staged_changes
- Plan: Use @omni-orchestrator start_spec
"""

        elif action == "update_status":
            if not phase:
                return "Error: phase is required for update_status action"

            project_memory.update_status(phase=phase, focus=focus)
            log_decision("context.status_updated", {"phase": phase, "focus": focus}, logger)

            return f"✅ Context updated: Phase={phase}, Focus={focus}"

        elif action == "add_note":
            if not note:
                return "Error: note is required for add_note action"

            project_memory.log_scratchpad(note, source="Claude")
            log_decision("context.note_added", {"note": note[:100]}, logger)

            return f"✅ Note added to context: {note[:50]}..."

        else:
            return f"Error: Unknown action '{action}'. Use 'read', 'update_status', or 'add_note'."

    @mcp.tool()
    async def get_project_instructions(name: Optional[str] = None) -> str:
        """
        Get project instructions that are pre-loaded at session start.

        These instructions from agent/instructions/ are loaded when the MCP server starts,
        ensuring they're always available as default prompts for LLM sessions.

        Args:
            name: Specific instruction name (without .md), e.g., "project-conventions"
                  If empty, returns all instructions merged.

        Returns:
            Project instruction(s) content.

        Examples:
            # Get specific instruction
            get_project_instructions(name="project-conventions")

            # Get all instructions
            get_project_instructions()
        """
        from common.mcp_core.instructions import get_instruction

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

    log_decision("context_tools.registered", {}, logger)
