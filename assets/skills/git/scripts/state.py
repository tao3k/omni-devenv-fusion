"""
agent/skills/git/state.py
Git Skill State Definition - Living Skill Architecture

Defines the structured context for Git workflows using Pydantic models.
This is the "Memory" layer of the Omni Skill Standard (OSS).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStep(str, Enum):
    """Enum representing the current step in a Git workflow."""

    INIT = "init"
    CHECK_ENV = "check_env"
    STASH = "stash"
    SWITCH = "switch"
    ADD = "add"
    COMMIT = "commit"
    PUSH = "push"
    POP = "pop"
    DONE = "done"
    ERROR = "error"


class GitIntent(str, Enum):
    """High-level intents that can trigger Git workflows."""

    HOTFIX = "hotfix"
    PR = "pr"
    BRANCH = "branch"
    COMMIT = "commit"
    STASH = "stash"
    MERGE = "merge"
    REVERT = "revert"
    TAG = "tag"
    STATUS = "status"


class GitWorkflowState(BaseModel):
    """
    Structured state for Git workflow orchestration.

    This model serves as the single source of truth for all Git operations,
    enabling:
    - State persistence across interruptions
    - Type-safe data flow between workflow nodes
    - Checkpoint/resume capability
    - Debug and telemetry

    Attributes:
        intent: The high-level user intent (e.g., 'hotfix', 'pr')
        target_branch: The branch to operate on
        commit_message: The commit message for the operation
        current_step: The current step in the workflow
        is_dirty: Whether the working tree has uncommitted changes
        stashed_hash: The stash reference if changes were stashed
        files_changed: List of files modified in this operation
        error_message: Error message if the workflow failed
        success: Whether the workflow completed successfully
    """

    # Input fields (provided by user or router)
    intent: str = Field(
        default="status", description="User's high-level intent, e.g. 'hotfix', 'pr', 'commit'"
    )
    target_branch: str = Field(
        default="", description="Target branch for operations like checkout, merge"
    )
    commit_message: str = Field(default="", description="Commit message for commit operations")
    source_branch: str = Field(default="", description="Source branch for merge/rebase operations")

    # Runtime state (maintained by workflow nodes)
    current_step: str = Field(default="init", description="Current step in the workflow")
    is_dirty: bool = Field(
        default=False, description="Whether the working tree has uncommitted changes"
    )
    stashed_hash: str | None = Field(
        default=None, description="Stash reference if changes were stashed"
    )
    files_changed: list[str] = Field(
        default_factory=list, description="List of files modified in this operation"
    )
    current_branch: str = Field(default="", description="Current branch before operation")
    commit_hash: str | None = Field(default=None, description="Commit hash if a commit was made")

    # Result fields (populated by workflow)
    error_message: str | None = Field(
        default=None, description="Error message if the workflow failed"
    )
    success: bool = Field(default=False, description="Whether the workflow completed successfully")
    result_message: str = Field(default="", description="Human-readable result of the operation")

    # Metadata for checkpoint/resume (renamed from checkpoint_id to avoid LangGraph conflict)
    resume_id: str | None = Field(default=None, description="Resume ID for state persistence")
    retry_count: int = Field(default=0, description="Number of retry attempts for the current step")

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields for flexibility
        use_enum_values=True,  # Store enum values as strings
    )


def create_initial_state(
    intent: str, target_branch: str = "", commit_message: str = "", **kwargs
) -> GitWorkflowState:
    """
    Factory function to create an initial GitWorkflowState.

    Args:
        intent: The high-level user intent
        target_branch: Target branch for the operation
        commit_message: Commit message if applicable
        **kwargs: Additional state fields

    Returns:
        Initialized GitWorkflowState
    """
    return GitWorkflowState(
        intent=intent,
        target_branch=target_branch,
        commit_message=commit_message,
        current_step="init",
        **kwargs,
    )


def format_state_for_output(state: GitWorkflowState) -> str:
    """
    Format the workflow state for human-readable output.

    Args:
        state: The GitWorkflowState to format

    Returns:
        Formatted string representation
    """
    lines = [
        "=== Git Workflow State ===",
        f"Intent: {state.intent}",
        f"Current Step: {state.current_step}",
        f"Target Branch: {state.target_branch or '(not specified)'}",
        f"Dirty Working Tree: {state.is_dirty}",
        f"Stashed: {state.stashed_hash or 'No'}",
        f"Files Changed: {len(state.files_changed)}",
        f"Success: {state.success}",
    ]

    if state.error_message:
        lines.append(f"Error: {state.error_message}")

    if state.result_message:
        lines.append(f"Result: {state.result_message}")

    return "\n".join(lines)
