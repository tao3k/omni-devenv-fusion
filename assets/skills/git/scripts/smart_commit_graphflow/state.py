"""
state.py - Smart Commit Workflow State Schema

Defines the GraphState type for the smart commit workflow.
"""

from typing import Any

from omni.core.skills.state import GraphState as BaseGraphState


class SmartCommitGraphState(BaseGraphState):
    """GraphState for the smart commit workflow.

    Attributes:
        workflow_id: Unique identifier for this workflow instance
        project_root: Root directory of the git repository
        staged_files: List of files staged for commit
        diff_content: The diff of staged changes
        security_issues: List of sensitive files detected
        lefthook_error: Error message from lefthook if failed
        lefthook_summary: Summary output from lefthook
        lefthook_report: Full report from lefthook
        scope_warning: Warning about scope validation
        submodules_pending: List of submodule paths with pending changes
        submodule_commits: List of commits made in submodules
        status: Current workflow status
        final_message: User-approved commit message
        file_count: Number of files in the commit
        commit_hash: Hash of the created commit
        commit_result: Output from git commit command
        security_status: Status of security scan
        _routing: Internal routing decision for workflow
    """

    workflow_id: str
    project_root: str
    staged_files: list[str]
    diff_content: str
    security_issues: list[str]
    lefthook_error: str
    lefthook_summary: str
    lefthook_report: str
    scope_warning: str
    submodules_pending: list[str]
    submodule_commits: list[dict[str, str]]
    status: str
    final_message: str
    file_count: int
    commit_hash: str
    commit_result: str
    security_status: str
    _routing: str


def create_initial_state(project_root: str, workflow_id: str) -> dict[str, Any]:
    """Create initial state for a new smart commit workflow.

    Args:
        project_root: Root directory of the git repository
        workflow_id: Unique identifier for this workflow instance

    Returns:
        Initial state dictionary with all required fields set to defaults
    """
    return {
        "workflow_id": workflow_id,
        "project_root": project_root,
        "staged_files": [],
        "diff_content": "",
        "security_issues": [],
        "lefthook_error": "",
        "lefthook_summary": "",
        "lefthook_report": "",
        "scope_warning": "",
        "submodules_pending": [],
        "submodule_commits": [],
        "status": "",
        "final_message": "",
        "file_count": 0,
        "commit_hash": "",
        "commit_result": "",
        "security_status": "",
        "_routing": "",
    }


__all__ = [
    "SmartCommitGraphState",
    "create_initial_state",
]
