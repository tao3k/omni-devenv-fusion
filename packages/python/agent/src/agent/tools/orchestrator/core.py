"""
agent/tools/orchestrator/core.py
Core delegation functionality.

DELEGATE a complex multi-step task to the Omni-Agentic OS.
"""

from typing import Dict, Any, List

from .state import get_orchestrator
from .types import MissionContext


async def delegate_mission(
    query: str,
    context_files: List[str] = None,
    history: List[Dict[str, Any]] = None,
) -> str:
    """
    DELEGATE a complex multi-step task to the Omni-Agentic OS.

    USE THIS FUNCTION WHEN:
    - The task requires multiple steps (e.g., edit file, then run test, then fix).
    - You want to use specialized agents (Coder, Reviewer).
    - You need 'Smart Mode' with self-correction.
    - You want real-time TUI visualization of progress.

    DO NOT USE THIS for simple single-file reads.

    Args:
        query: The mission description (e.g., "Fix the threading bug in main.py")
        context_files: Optional list of files relevant to the task
        history: Optional conversation history

    Returns:
        The result of the mission execution as a string.
    """
    orchestrator = get_orchestrator()

    # Build context dict
    context: MissionContext = {"relevant_files": context_files or []}

    # Dispatch! This triggers the whole Phase 18 TUI flow internally
    result = await orchestrator.dispatch(
        user_query=query,
        history=history or [],
        context=context,
    )

    return result


__all__ = ["delegate_mission"]
