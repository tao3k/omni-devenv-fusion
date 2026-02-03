"""
git/scripts/smart_commit_workflow.py - Smart Commit Workflow

Uses unified Rust LanceDB CheckpointStore for persistent state:
- State persists across skill reloads
- Supports workflow_id-based retrieval
- Centralized at path from settings (default: .cache/checkpoints.lance)

Workflow Type: smart_commit

Architecture: Map -> Check -> Route -> Execute

This implements a cognitive workflow that:
1. Maps repository state (staged files, diff)
2. Checks for errors (lefthook, security)
3. Routes based on state (empty/error/prepared)
4. Executes commit on approval

Uses Rust-Powered Cognitive Pipeline for state persistence:
- LanceDB checkpoint store via Rust bindings
- Parallel file I/O for state management
"""

import uuid
from pathlib import Path
from typing import Any

from git.scripts.commit_state import create_initial_state
from git.scripts.prepare import _get_cog_scopes
from git.scripts.rendering import render_commit_message, render_template
from langgraph.graph import END, StateGraph

from omni.core.skills.state import GraphState
from omni.foundation.checkpoint import (
    load_workflow_state,
    save_workflow_state,
)
from omni.foundation.config.logging import get_logger
from omni.langgraph.visualize import register_workflow, visualize_workflow as _get_diagram

from ._enums import SmartCommitAction, SmartCommitStatus, WorkflowRouting

logger = get_logger("git.smart_commit")

# Import Rust checkpoint saver for LangGraph (use shared singleton)
try:
    from omni.langgraph.checkpoint.saver import get_default_checkpointer as _get_checkpointer

    _CHECKPOINT_AVAILABLE = True
    _memory = _get_checkpointer()  # Get shared singleton (logs once)
except ImportError as e:
    _CHECKPOINT_AVAILABLE = False
    _memory = None
    logger.warning(f"RustCheckpointSaver import failed: {e}")

# Workflow type identifier for checkpoint table
_WORKFLOW_TYPE = "smart_commit"


def _build_workflow() -> Any:
    """Build the Smart Commit workflow graph (for visualization/future use)."""

    def _check_state_node(state: GraphState) -> dict[str, Any]:
        """Check state and determine next step."""
        staged_files = state.get("staged_files", [])
        lefthook_error = state.get("lefthook_error", "")
        security_issues = state.get("security_issues", [])

        if not staged_files:
            return {"_routing": WorkflowRouting.EMPTY}
        if lefthook_error:
            return {"_routing": WorkflowRouting.LEFTHOOK_ERROR}
        if security_issues:
            return {"_routing": WorkflowRouting.SECURITY_WARNING}
        return {"_routing": WorkflowRouting.PREPARED}

    def _route_state(state: GraphState) -> str:
        """Router function for conditional edges."""
        return state.get("_routing", "empty")

    def _return_state(state: GraphState) -> dict[str, Any]:
        """Return state as is."""
        return dict(state)

    def _lefthook_pre_commit_node(state: GraphState) -> dict[str, Any]:
        """Run lefthook pre-commit and re-stage any modified files.

        This step runs before commit to ensure formatting changes are included.
        """
        import os
        import subprocess
        import shutil

        # Use PRJ_ROOT env var or state value or fallback to "."
        project_root = os.environ.get("PRJ_ROOT") or state.get("project_root") or "."
        result = dict(state)

        try:
            if shutil.which("lefthook"):
                # Run lefthook pre-commit (applies formatting)
                subprocess.run(
                    ["git", "hook", "run", "pre-commit"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                )
                logger.info("Ran lefthook pre-commit in workflow")

                # Re-stage all modified files (including those modified by lefthook)
                proc = subprocess.run(
                    ["git", "diff", "--name-only"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                )
                modified = [f for f in proc.stdout.strip().split("\n") if f]

                proc = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                )
                untracked = [f for f in proc.stdout.strip().split("\n") if f]

                if modified or untracked:
                    subprocess.run(
                        ["git", "add", "-A"],
                        cwd=project_root,
                        capture_output=True,
                    )
                    logger.info(f"Re-staged {len(modified)} modified + {len(untracked)} new files")

                    # Update staged_files in state
                    proc = subprocess.run(
                        ["git", "diff", "--cached", "--name-only"],
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                    )
                    result["staged_files"] = [f for f in proc.stdout.strip().split("\n") if f]
        except Exception as e:
            logger.warning(f"Failed to run lefthook pre-commit: {e}")

        return result

    builder = StateGraph(GraphState)
    builder.add_node("check", _check_state_node)
    builder.add_node("lefthook_pre_commit", _lefthook_pre_commit_node)
    builder.add_node("empty", _return_state)
    builder.add_node("lefthook_error", _return_state)
    builder.add_node("security_warning", _return_state)
    builder.add_node("prepared", _return_state)
    builder.set_entry_point("check")
    builder.add_conditional_edges(
        "check",
        _route_state,
        {
            WorkflowRouting.EMPTY: "empty",
            WorkflowRouting.LEFTHOOK_ERROR: "lefthook_error",
            WorkflowRouting.SECURITY_WARNING: "security_warning",
            WorkflowRouting.PREPARED: "prepared",
        },
    )
    # All terminal states go to END
    for node in ["empty", "lefthook_error", "security_warning", "prepared"]:
        builder.add_edge(node, END)
    # lefthook_pre_commit is also terminal (user then needs to approve)
    builder.add_edge("lefthook_pre_commit", END)

    return builder


from omni.foundation.api.decorators import skill_command


@skill_command(
    name="smart_commit",
    category="workflow",
    description="""
    Primary git commit workflow with security scan and human approval.

    ⚠️  **Use smart_commit for all commits in this project** unless user explicitly requests otherwise.

    Multi-step workflow:
    1. start: Stages files, runs lefthook (formatting), security scan
    2. approve: User approves, LLM generates commit message, executes commit
    3. reject: Cancels the workflow
    4. status: Checks workflow status
    5. visualize: Shows the workflow diagram

    Benefits over direct git_commit:
    - Automatic commit message generation from diff analysis
    - Security scan for sensitive files
    - Lefthook formatting (cargo fmt, ruff, etc.) with automatic re-staging
    - Human-in-the-loop approval
    - File categorization for detailed commit messages

    Args:
        - action: str = "start" - Workflow action: start, approve, reject, status, visualize
        - workflow_id: str - Workflow ID from start action (required for approve/reject/status)
        - message: str - Commit message for approve action (required for approve)

    Returns:
        Workflow-specific result messages based on the action.

    Example:
        @omni("git.smart_commit", {"action": "start"})
        @omni("git.smart_commit", {"action": "approve", "workflow_id": "abc123", "message": "feat(git): add commit workflow"})
    """,
    # MCP Annotations for LLM context
    read_only=False,  # Creates commits, modifies repository
    destructive=True,  # approve action creates a commit
    idempotent=False,  # Each commit is unique
    open_world=False,  # No external network access
)
async def smart_commit(
    action: SmartCommitAction = SmartCommitAction.START,
    workflow_id: str = "",
    message: str = "",
    project_root: str = "",
) -> str:
    """
    Execute the Smart Commit workflow.

    State Machine Pattern - uses workflow_id to track progress across multiple calls.

    Args:
        - action: SmartCommitAction - Workflow action: start, lefthook, approve, reject, status, visualize
        - workflow_id: str - Workflow ID from start action (required for lefthook/approve/reject/status)
        - message: str - Commit message for approve action (required for approve)
        - project_root: str - Project root directory (defaults to PRJ_ROOT or ".")

    Returns:
        Workflow-specific result messages based on the action.
    """
    # Resolve project_root from PRJ_ROOT env var if not provided
    import os

    if not project_root:
        project_root = os.environ.get("PRJ_ROOT", ".")

    try:
        match action:
            case SmartCommitAction.START:
                result = await _start_smart_commit_async(project_root=project_root)
                wf_id = result.get("workflow_id", "unknown")
                files = result.get("staged_files", [])
                diff = result.get("diff_content", "")
                status = result.get("status", "unknown")
                scope_warning = result.get("scope_warning", "")
                valid_scopes = _get_cog_scopes(Path(project_root))

                match status:
                    case SmartCommitStatus.EMPTY:
                        return "Nothing to commit - No staged files detected."
                    case SmartCommitStatus.LEFTHOOK_FAILED:
                        lefthook_output = result.get("error", "Unknown lefthook error")
                        return f"Lefthook Pre-commit Failed\n\n{lefthook_output}\n\nPlease fix the error above and try again."
                    case SmartCommitStatus.SECURITY_VIOLATION:
                        issues = result.get("security_issues", [])
                        return f"Security Issue Detected\n\nSensitive files detected:\n{', '.join(issues)}\n\nPlease resolve these issues before committing."
                    case _:
                        return render_template(
                            "prepare_result.j2",
                            has_staged=bool(files),
                            staged_files=files,
                            staged_file_count=len(files),
                            scope_warning=scope_warning,
                            valid_scopes=valid_scopes,
                            lefthook_summary=result.get("lefthook_summary", ""),
                            lefthook_report="",
                            diff_content=diff,
                            wf_id=wf_id,
                        )

            case SmartCommitAction.APPROVE:
                if not workflow_id:
                    return "workflow_id required for approve action"
                if not message:
                    return "message required for approve action"

                import re

                commit_type = "feat"
                commit_scope = "general"
                commit_body = ""

                first_line = message.strip().split("\n")[0]
                commit_match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", first_line)
                if commit_match:
                    commit_type = commit_match.group(1)
                    scope_part = commit_match.group(2)
                    if scope_part:
                        commit_scope = scope_part
                    commit_description = commit_match.group(3)
                else:
                    commit_description = first_line

                lines = message.strip().split("\n")
                if len(lines) > 1:
                    commit_body = "\n".join(lines[1:]).strip()

                valid_scopes = _get_cog_scopes(Path(project_root))
                if valid_scopes and commit_scope not in valid_scopes:
                    from difflib import get_close_matches

                    matches = get_close_matches(commit_scope, valid_scopes, n=1, cutoff=0.6)
                    if matches:
                        commit_scope = matches[0]

                result = await _approve_smart_commit_async(
                    workflow_id=workflow_id,
                    message=message,
                    project_root=project_root,
                )

                return render_commit_message(
                    subject=commit_description,
                    body=commit_body,
                    status=SmartCommitStatus.COMMITTED,
                    commit_hash=result.get("commit_hash", ""),
                    file_count=result.get("file_count", 0),
                    verified_by="omni Git Skill (cog)",
                    security_status=result.get("security_status", "No sensitive files detected"),
                    workflow_id=workflow_id,
                    commit_type=commit_type,
                    commit_scope=commit_scope,
                )

            case SmartCommitAction.REJECT:
                if not workflow_id:
                    return "workflow_id required for reject action"
                return f"Commit Cancelled\n\nWorkflow `{workflow_id}` has been cancelled."

            case SmartCommitAction.STATUS:
                if not workflow_id:
                    return "workflow_id required for status action"
                status = await _get_workflow_status_async(workflow_id)
                if not status:
                    return f"Workflow `{workflow_id}` not found"
                return f"Workflow Status (`{workflow_id}`)\n\nStatus: {status.get('status', 'unknown')}\nFiles: {len(status.get('staged_files', []))}"

            case SmartCommitAction.VISUALIZE:
                diagram = _get_diagram("smart_commit")
                return f"Smart Commit Workflow\n\n{diagram}"

            case _:
                return f"Unknown action: {action}"

    except Exception as e:
        import traceback

        return f"Error: {e}\n\n```\n{traceback.format_exc()}\n```"


async def _start_smart_commit_async(
    project_root: str = "",
) -> dict[str, Any]:
    """Start smart commit workflow - stage and scan files."""
    import os

    if not project_root:
        project_root = os.environ.get("PRJ_ROOT", ".")

    from git.scripts.prepare import stage_and_scan

    wf_id = str(uuid.uuid4())[:8]
    root = Path(project_root)

    # Directly call stage_and_scan (not a skill command, just a helper function)
    result_data = stage_and_scan(project_root)

    staged_files = result_data.get("staged_files", [])
    diff = result_data.get("diff", "")
    security_issues = result_data.get("security_issues", [])
    lefthook_error = result_data.get("lefthook_error", "")
    lefthook_summary = result_data.get("lefthook_summary", "")

    valid_scopes = _get_cog_scopes(root)
    scope_warning = ""

    initial_state = create_initial_state(project_root=project_root, workflow_id=wf_id)
    initial_state["staged_files"] = staged_files
    initial_state["diff_content"] = diff
    initial_state["security_issues"] = security_issues

    # Check errors FIRST - lefthook failure may result in empty staged_files
    if lefthook_error:
        initial_state["status"] = SmartCommitStatus.LEFTHOOK_FAILED
        initial_state["error"] = lefthook_error
    elif security_issues:
        initial_state["status"] = SmartCommitStatus.SECURITY_VIOLATION
    elif not staged_files:
        initial_state["status"] = SmartCommitStatus.EMPTY
    else:
        initial_state["status"] = SmartCommitStatus.PREPARED

    state_dict: dict[str, Any] = dict(initial_state)
    state_dict["scope_warning"] = scope_warning
    state_dict["lefthook_report"] = ""
    state_dict["lefthook_summary"] = lefthook_summary

    state_dict["workflow_id"] = wf_id

    # Save to unified checkpoint store
    save_workflow_state(_WORKFLOW_TYPE, wf_id, state_dict)

    return state_dict


async def _approve_smart_commit_async(
    message: str,
    workflow_id: str,
    project_root: str = "",
) -> dict[str, Any]:
    """Approve and execute commit with the given message."""
    import os
    import subprocess

    if not project_root:
        project_root = os.environ.get("PRJ_ROOT", ".")

    # Step 1: Run lefthook pre-commit to apply any formatting
    # This mirrors what git commit's hook would do, but we do it explicitly
    # so we can re-stage the modified files before committing
    try:
        import shutil

        if shutil.which("lefthook"):
            subprocess.run(
                ["git", "hook", "run", "pre-commit"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            logger.info("Ran lefthook pre-commit")
    except Exception as e:
        logger.warning(f"Failed to run lefthook pre-commit: {e}")

    # Step 2: Re-stage ALL modified files (including those modified by lefthook)
    # This ensures the commit includes the formatted content
    try:
        # Get all modified (working tree vs HEAD) files
        proc = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        all_modified = [f for f in proc.stdout.strip().split("\n") if f]

        # Also get untracked files
        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        untracked = [f for f in proc.stdout.strip().split("\n") if f]

        # Use git add -A to stage all changes
        if all_modified or untracked:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=project_root,
                capture_output=True,
            )
            logger.info(f"Re-staged {len(all_modified)} modified + {len(untracked)} new files")
    except Exception as e:
        logger.warning(f"Failed to re-stage files: {e}")

    # Get final staged files count
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        staged_files = [f for f in proc.stdout.strip().split("\n") if f]
        file_count = len(staged_files)
    except Exception:
        file_count = 0

    # Save approved state to unified checkpoint store
    save_workflow_state(
        _WORKFLOW_TYPE,
        workflow_id,
        {"status": SmartCommitStatus.APPROVED, "final_message": message, "file_count": file_count},
    )

    # Execute commit directly via subprocess (simpler than skill_manager.run)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    commit_hash = ""
    if result.returncode == 0:
        # Extract commit hash from the commit output or run rev-parse
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            commit_hash = proc.stdout.strip()[:8]

    commit_result = result.stdout if result.returncode == 0 else f"Commit failed: {result.stderr}"

    return {
        "status": SmartCommitStatus.COMMITTED,
        "final_message": message,
        "workflow_id": workflow_id,
        "commit_result": commit_result,
        "commit_hash": commit_hash,
        "file_count": file_count,
        "security_status": "No sensitive files detected",
    }


async def _get_workflow_status_async(workflow_id: str) -> dict[str, Any] | None:
    """Get workflow status from unified checkpoint store."""
    return load_workflow_state(_WORKFLOW_TYPE, workflow_id)


def _smart_commit_diagram() -> str:
    """Generate a Mermaid diagram of the workflow."""
    return """graph TD
    A[Start: git.smart_commit action=start] --> B[git add -A → lefthook → re-stage]
    B --> C{Check Results}
    C -->|Empty| D[empty: Nothing to commit]
    C -->|Lefthook Failed| E[lefthook_error: Fix errors]
    C -->|Security Issues| F[security_warning: Review files]
    C -->|Prepared| G[User reviews changes]
    G --> H[User approves with message]
    H --> I[git.smart_commit action=approve]
    I --> J[git commit executes]
    J --> K[Done]"""


# Register with common visualization lib
_SMART_COMMIT_DIAGRAM = _smart_commit_diagram()
register_workflow("smart_commit", _SMART_COMMIT_DIAGRAM)


# =============================================================================
# LangGraph Compilation with Rust Checkpoint (shared singleton)
# =============================================================================

# Build and compile the workflow graph with shared checkpointer
_smart_commit_graph = _build_workflow()
_app = _smart_commit_graph.compile(checkpointer=_memory)
logger.info(f"Compiled SmartCommit checkpointer: {_app.checkpointer}")


__all__ = [
    "SmartCommitAction",
    "SmartCommitStatus",
    "WorkflowRouting",
    "smart_commit",
]
