"""
assets/skills/git/scripts/commit_state.py
Commit-Specific State Schema for Smart Commit Workflow

Defines the structured state for LangGraph-driven commit workflow
with Human-in-the-Loop (HITL) approval.

Architecture: Tool provides data, LLM provides intelligence.
"""

from typing import TypedDict, List, Optional


class CommitState(TypedDict):
    """
    State for the Smart Commit Workflow.

    Flow: prepare -> (LLM Analysis) -> execute
    - prepare: Stages files, extracts diff, runs security scan
    - LLM: Analyzes diff, generates commit message
    - execute: Performs the actual commit with LLM-generated message
    """

    # ==========================================================================
    # Input Fields (provided by user)
    # ==========================================================================
    project_root: str

    # ==========================================================================
    # Processing Fields (populated by prepare node)
    # ==========================================================================
    staged_files: List[str]
    diff_content: str  # Raw diff for LLM analysis
    security_issues: List[str]

    # ==========================================================================
    # Workflow State (managed by graph)
    # ==========================================================================
    status: str  # "pending", "prepared", "approved", "rejected", "security_violation", "error"
    workflow_id: str  # Unique ID for state persistence

    # ==========================================================================
    # Output Fields (populated by execute node)
    # ==========================================================================
    final_message: str  # LLM-generated commit message
    commit_hash: Optional[str]
    error: Optional[str]
    retry_note: Optional[str]  # Note about retry attempts
    scope_warning: Optional[str]  # Warning about invalid scope


def create_initial_state(
    project_root: str = ".",
    workflow_id: str = "default",
) -> CommitState:
    """
    Factory function to create initial CommitState.

    Args:
        project_root: Path to project root
        workflow_id: Unique ID for state persistence

    Returns:
        Initialized CommitState
    """
    return {
        "project_root": project_root,
        "staged_files": [],
        "diff_content": "",
        "security_issues": [],
        "status": "pending",
        "workflow_id": workflow_id,
        "final_message": "",
        "commit_hash": None,
        "error": None,
        "retry_note": None,
        "scope_warning": None,
    }


__all__ = [
    "CommitState",
    "create_initial_state",
]
