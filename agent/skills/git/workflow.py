"""
agent/skills/git/workflow.py
Git Skill Workflow - Phase 24: Living Skill Architecture

Implements LangGraph-based workflow orchestration for Git operations.
This is the "Brain" layer of the Omni Skill Standard (OSS).

Usage:
    from agent.skills.git.workflow import app, GitWorkflowState

    state = GitWorkflowState(intent="hotfix", target_branch="hotfix/v1.2.3")
    result = app.invoke(state)
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.skills.git.state import GitWorkflowState, WorkflowStep
from agent.skills.git.tools import (
    git_status,
    git_branch,
    git_stash_save,
    git_stash_pop,
    git_checkout,
    git_add,
    git_commit,
    GitError,
)


# ==============================================================================
# Node Functions (Pure Functions)
# ==============================================================================


def node_check_env(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Check the current Git environment.

    Returns:
        Dict with is_dirty, current_branch, and files_changed
    """
    try:
        status_output = git_status(short=True)
        is_dirty = bool(status_output and status_output.strip())

        branch_output = git_branch().strip()
        current_branch = branch_output.split("\n")[0].strip().lstrip("* ")

        files_changed = []
        if is_dirty:
            # Parse short status output
            for line in status_output.strip().split("\n"):
                if line.strip():
                    # Get the file path (column 3+ in short format)
                    parts = line.split()
                    if len(parts) >= 2:
                        files_changed.append(parts[-1])

        return {
            "is_dirty": is_dirty,
            "current_branch": current_branch,
            "files_changed": files_changed,
            "current_step": WorkflowStep.CHECK_ENV.value,
        }
    except GitError as e:
        return {
            "error_message": f"Failed to check environment: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


def node_stash(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Stash current changes.

    Returns:
        Dict with stashed_hash
    """
    try:
        message = f"Auto-stash by Omni Living Skill - {state.intent}"
        result = git_stash_save(message)

        # Extract stash hash from result
        stashed_hash = None
        for line in result.split("\n"):
            if "WIP on" in line or "Saved working directory" in line:
                # Try to extract the stash reference
                import re

                match = re.search(r"stash@\{\d+\}", result)
                if match:
                    stashed_hash = match.group()

        return {
            "stashed_hash": stashed_hash or "stash@{0}",
            "current_step": WorkflowStep.STASH.value,
        }
    except GitError as e:
        return {
            "error_message": f"Failed to stash changes: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


def node_switch_branch(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Switch to the target branch.

    Returns:
        Dict with success status and result message
    """
    if not state.target_branch:
        return {
            "error_message": "No target branch specified",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }

    try:
        result = git_checkout(state.target_branch)
        return {
            "current_step": WorkflowStep.SWITCH.value,
            "result_message": f"Switched to branch: {state.target_branch}\n{result}",
        }
    except GitError as e:
        return {
            "error_message": f"Failed to switch branch: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


def node_add(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Stage all changes for commit.

    Returns:
        Dict with success status
    """
    try:
        result = git_add(".")
        return {
            "current_step": WorkflowStep.ADD.value,
            "result_message": result or "All changes staged",
        }
    except GitError as e:
        return {
            "error_message": f"Failed to stage changes: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


def node_commit(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Commit staged changes.

    Returns:
        Dict with commit_hash and result message
    """
    if not state.commit_message:
        return {
            "error_message": "No commit message provided",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }

    try:
        result = git_commit(state.commit_message)

        # Extract commit hash from result
        commit_hash = None
        for line in result.split("\n"):
            if line.strip().startswith("[") or "commit" in line.lower():
                import re

                match = re.search(r"[a-f0-9]{7,40}", line)
                if match:
                    commit_hash = match.group()
                    break

        return {
            "commit_hash": commit_hash,
            "current_step": WorkflowStep.COMMIT.value,
            "result_message": result,
            "success": True,
        }
    except GitError as e:
        return {
            "error_message": f"Failed to commit: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


def node_pop_stash(state: GitWorkflowState) -> Dict[str, Any]:
    """
    Apply stashed changes and remove from stash.

    Returns:
        Dict with result message
    """
    if not state.stashed_hash:
        return {
            "result_message": "No stashed changes to apply",
            "current_step": WorkflowStep.POP.value,
        }

    try:
        result = git_stash_pop()
        return {
            "stashed_hash": None,  # Clear after pop
            "current_step": WorkflowStep.POP.value,
            "result_message": result,
        }
    except GitError as e:
        return {
            "error_message": f"Failed to pop stash: {str(e)}",
            "current_step": WorkflowStep.ERROR.value,
            "success": False,
        }


# ==============================================================================
# Workflow Routers (Conditional Edge Functions)
# ==============================================================================


def route_by_intent(state: GitWorkflowState) -> str:
    """
    Route to the appropriate workflow based on user intent.

    Args:
        state: Current GitWorkflowState

    Returns:
        Next node name
    """
    intent = state.intent.lower()

    if intent in ("hotfix", "pr"):
        # Hotfix/PR workflow: check env -> stash if dirty -> switch -> commit -> pop
        return "handle_dirty_branch"
    elif intent == "branch":
        # Just switch branch
        return "switch_branch"
    elif intent == "commit":
        # Direct commit workflow
        return "commit"
    elif intent == "stash":
        # Just stash
        return "stash"
    else:
        # Default: check env first
        return "check_env"


def route_dirty_branch(state: GitWorkflowState) -> str:
    """
    Route based on whether the working tree is dirty.

    Args:
        state: Current GitWorkflowState

    Returns:
        Next node name
    """
    if state.is_dirty:
        return "stash"
    return "switch_branch"


def route_after_switch(state: GitWorkflowState) -> str:
    """
    Route after branch switch based on intent.

    Args:
        state: Current GitWorkflowState

    Returns:
        Next node name
    """
    intent = state.intent.lower()

    if intent == "hotfix" and state.stashed_hash:
        # For hotfix, we might want to pop stash after commit
        return "add"
    elif intent == "pr":
        return "add"
    elif state.target_branch:
        return "add"

    return END


def route_after_commit(state: GitWorkflowState) -> str:
    """
    Route after commit based on whether we need to pop stash.

    Args:
        state: Current GitWorkflowState

    Returns:
        Next node name
    """
    if state.stashed_hash and state.intent.lower() == "hotfix":
        return "pop_stash"
    return END


# ==============================================================================
# LangGraph Workflow Construction
# ==============================================================================


def create_workflow() -> StateGraph:
    """
    Create the Git workflow StateGraph.

    Returns:
        Configured StateGraph ready to be compiled
    """
    workflow = StateGraph(GitWorkflowState)

    # Add nodes
    workflow.add_node("check_env", node_check_env)
    workflow.add_node("stash", node_stash)
    workflow.add_node("switch_branch", node_switch_branch)
    workflow.add_node("add", node_add)
    workflow.add_node("commit", node_commit)
    workflow.add_node("pop_stash", node_pop_stash)

    # Set entry point
    workflow.set_entry_point("check_env")

    # Add conditional edges from check_env
    workflow.add_conditional_edges(
        "check_env",
        route_by_intent,
        {
            "handle_dirty_branch": "handle_dirty_branch",
            "switch_branch": "switch_branch",
            "commit": "commit",
            "stash": "stash",
            "check_env": "check_env",  # Loop back for unknown intents
        },
    )

    # Handle dirty branch logic
    workflow.add_node("handle_dirty_branch", node_check_env)
    workflow.add_conditional_edges(
        "handle_dirty_branch",
        route_dirty_branch,
        {"stash": "stash", "switch_branch": "switch_branch"},
    )

    # After switch, route to add or end
    workflow.add_conditional_edges(
        "switch_branch",
        route_after_switch,
        {"add": "add", END: END},
    )

    # After add, go to commit
    workflow.add_edge("add", "commit")

    # After commit, check if we need to pop stash
    workflow.add_conditional_edges(
        "commit",
        route_after_commit,
        {"pop_stash": "pop_stash", END: END},
    )

    # After pop stash, end
    workflow.add_edge("pop_stash", END)

    # Direct routes
    workflow.add_edge("stash", END)
    workflow.add_edge("commit", END)

    return workflow


# Compile with memory checkpoint for state persistence
_memory = MemorySaver()
app = create_workflow().compile(checkpointer=_memory)


# ==============================================================================
# Convenience Functions
# ==============================================================================


async def run_git_workflow(
    intent: str,
    target_branch: str = "",
    commit_message: str = "",
    checkpoint_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> GitWorkflowState:
    """
    Convenience function to run a Git workflow.

    Args:
        intent: The high-level user intent
        target_branch: Target branch for operations
        commit_message: Commit message for commit operations
        checkpoint_id: Optional checkpoint ID for resumption
        config: Optional LangGraph configuration

    Returns:
        Final GitWorkflowState after workflow completion
    """
    initial_state = GitWorkflowState(
        intent=intent,
        target_branch=target_branch,
        commit_message=commit_message,
        checkpoint_id=checkpoint_id,
    )

    thread_config = {"configurable": {"thread_id": checkpoint_id or "default"}}
    if config:
        thread_config.update(config)

    result = app.invoke(initial_state, config=thread_config)
    return result


def format_workflow_result(state: GitWorkflowState) -> str:
    """
    Format the workflow result for human-readable output.

    Args:
        state: The final GitWorkflowState

    Returns:
        Formatted result string
    """
    lines = [
        "=" * 40,
        "Git Workflow Result",
        "=" * 40,
        f"Intent: {state.intent}",
        f"Target Branch: {state.target_branch or '(not specified)'}",
        f"Status: {'✓ Success' if state.success else '✗ Failed'}",
    ]

    if state.error_message:
        lines.append(f"\nError: {state.error_message}")

    if state.result_message:
        lines.append(f"\nResult:\n{state.result_message}")

    if state.commit_hash:
        lines.append(f"\nCommit: {state.commit_hash}")

    if state.stashed_hash:
        lines.append(f"\nStashed: {state.stashed_hash}")

    return "\n".join(lines)
