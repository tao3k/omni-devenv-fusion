"""
assets/skills/git/scripts/smart_workflow.py
Phase 36.7: Smart Commit Workflow with LangGraph

Architecture: Tool provides data, LLM provides intelligence.
Flow: prepare -> (LLM Analysis) -> execute

Nodes:
    - prepare: Stages files, extracts diff, runs security scan
    - execute: Performs the actual commit (only if approved)

The graph interrupts before 'execute' to allow LLM to analyze diff
and generate the commit message before execution.
"""

from typing import Dict, Literal, Optional
from pathlib import Path
import subprocess
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .commit_state import CommitState, create_initial_state
from . import prepare as prepare_mod
from . import commit as commit_mod
from . import rendering

# In-memory checkpoint for state persistence
_memory = MemorySaver()


# ==============================================================================
# Node Functions
# ==============================================================================


def node_prepare(state: CommitState) -> CommitState:
    """
    Prepare stage: Stage files, extract diff, run security scan.

    This node does the "dirty work" and prepares data for LLM analysis.
    The actual analysis and message generation happens in LLM's cognitive space.

    Args:
        state: Current CommitState with project_root

    Returns:
        Updated state with staged_files, diff_content, security_issues
    """
    try:
        project_root = state.get("project_root", ".")

        # Call stage_and_scan to do the heavy lifting
        scan_result = prepare_mod.stage_and_scan(root_dir=project_root)

        # Check for empty staging
        if not scan_result["staged_files"]:
            return {
                **state,
                "status": "empty",
                "error": "Nothing to commit",
            }

        # Check for lefthook failure (format issues)
        if scan_result.get("lefthook_error"):
            return {
                **state,
                "status": "lefthook_failed",
                "error": scan_result["lefthook_error"],
            }

        # Check for security issues
        if scan_result["security_issues"]:
            return {
                **state,
                "status": "security_violation",
                "security_issues": scan_result["security_issues"],
            }

        return {
            **state,
            "staged_files": scan_result["staged_files"],
            "diff_content": scan_result["diff"],
            "status": "prepared",
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "error": f"Preparation failed: {str(e)}",
        }


def _get_valid_scopes() -> list[str]:
    """Get valid scopes from cog.toml."""
    try:
        from common.config.settings import get_setting
        from common.gitops import get_project_root

        root = get_project_root()
        cog_path = root / get_setting("config.cog_toml", "cog.toml")

        if cog_path.exists():
            import re

            content = cog_path.read_text()
            match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
            if match:
                scopes_str = match.group(1)
                return re.findall(r'"([^"]+)"', scopes_str)
    except Exception:
        pass
    return []


def _fix_scope_in_message(message: str, valid_scopes: list[str]) -> str:
    """Fix invalid scope in commit message using valid scopes."""
    import re

    # Parse existing message
    match = re.match(r"^(\w+)\(([^)]+)\):\s*(.+)$", message.strip())
    if not match:
        return message  # Can't parse, return as-is

    commit_type = match.group(1)
    scope = match.group(2)
    description = match.group(3)

    scope_lower = scope.lower()
    valid_scopes_lower = [s.lower() for s in valid_scopes]

    # Find close match
    if scope_lower in valid_scopes_lower:
        return message  # Scope already valid

    from difflib import get_close_matches

    close_matches = get_close_matches(scope_lower, valid_scopes_lower, n=1, cutoff=0.6)

    if close_matches:
        # Use the original casing
        fixed_scope = valid_scopes[valid_scopes_lower.index(close_matches[0])]
        return f"{commit_type}({fixed_scope}): {description}"

    # No match found, use first valid scope as fallback
    if valid_scopes:
        return f"{commit_type}({valid_scopes[0]}): {description}"

    return message


def _get_staged_files(cwd: str = ".") -> set[str]:
    """Get currently staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return set(f.strip() for f in result.stdout.splitlines() if f.strip())


def _get_unstaged_files(cwd: str = ".") -> set[str]:
    """Get unstaged (modified but not staged) files."""
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return set(f.strip() for f in result.stdout.splitlines() if f.strip())


def _try_commit(message: str, cwd: str = ".") -> tuple[bool, str]:
    """
    Try to commit and return (success, result).

    Returns:
        (True, commit_hash) on success
        (False, error_message) on failure
    """
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    if result.returncode == 0:
        # Extract commit hash
        import re

        match = re.search(r"[a-f0-9]{7,40}", result.stdout)
        hash_val = match.group() if match else "unknown"
        return True, hash_val

    # Check for specific error types
    error_text = result.stdout + result.stderr

    if "reformatted" in error_text.lower() or "formatted" in error_text.lower():
        return False, "lefthook_format"

    if "Invalid scope" in error_text or "scope" in error_text.lower():
        return False, "invalid_scope"

    return False, error_text[:200]


def node_execute(state: CommitState) -> CommitState:
    """
    Execute stage: Perform the actual git commit with retry logic.

    Retry strategy:
    1. First try: Re-stage all modified tracked files, then commit
    2. If lefthook reformatted: Re-stage only reformatted files and retry
    3. If invalid scope: Fix scope and retry
    4. If all retries fail: Mark as failed

    Args:
        state: CommitState with approval and final_message

    Returns:
        Updated state with commit_hash or status="failed"
    """
    if state.get("status") != "approved":
        return state

    from pathlib import Path

    message = state.get("final_message", "")
    project_root = state.get("project_root", ".")
    cwd = Path(project_root)

    if not message:
        return {
            **state,
            "status": "failed",
            "error": "No commit message provided",
        }

    # ===== Step 0: Ensure files are staged before trying to commit =====
    # Get files that were staged during prepare phase
    originally_staged = set(state.get("staged_files", []))
    currently_staged = _get_staged_files(str(cwd))

    # Lefthook may have reformatted files between prepare and execute
    # Also, user may have modified additional files
    # Get all modified tracked files (ACM = Added, Copied, Modified)
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    modified_out = result.stdout
    all_modified = set(line.strip() for line in modified_out.splitlines() if line.strip())

    # Re-stage all modified files (including originally staged + new ones)
    # This ensures all changes are included in the commit
    files_to_stage = originally_staged | all_modified

    if files_to_stage:
        for f in files_to_stage:
            subprocess.run(
                ["git", "add", f],
                cwd=str(cwd),
                capture_output=True,
            )
        # Update currently_staged after re-staging
        currently_staged = _get_staged_files(str(cwd))

    # If no files staged at all, nothing to commit
    if not currently_staged:
        return {
            **state,
            "status": "failed",
            "error": "Nothing to commit - no staged files",
        }

    # ===== Step 1: First try - commit with current staged files =====
    success, result = _try_commit(message, str(cwd))
    if success:
        return {
            **state,
            "commit_hash": result,
            "status": "completed",
        }

    # ===== Step 2: Check error type and retry =====
    error_type = result

    # Retry 1: Lefthook reformatted files
    if error_type == "lefthook_format":
        # Get files that were reformatted (were staged during prepare, now unstaged)
        staged_after = _get_staged_files(str(cwd))
        reformatted = originally_staged - staged_after  # Files that moved from staged to unstaged

        # Only re-stage the reformatted files, not everything
        if reformatted:
            for f in reformatted:
                subprocess.run(
                    ["git", "add", f],
                    cwd=str(cwd),
                    capture_output=True,
                )

            # Try commit again
            success, result = _try_commit(message, str(cwd))
            if success:
                return {
                    **state,
                    "commit_hash": result,
                    "status": "completed",
                    "retry_note": f"Retried after lefthook format ({len(reformatted)} files)",
                }

    # Retry 2: Invalid scope
    if error_type == "invalid_scope" or error_type == "lefthook_format":
        valid_scopes = _get_valid_scopes()
        if valid_scopes:
            fixed_message = _fix_scope_in_message(message, valid_scopes)
            if fixed_message != message:
                # Try with fixed scope
                success, result = _try_commit(fixed_message, str(cwd))
                if success:
                    return {
                        **state,
                        "commit_hash": result,
                        "final_message": fixed_message,  # Update with fixed message
                        "status": "completed",
                        "retry_note": f"Retried with fixed scope",
                    }

    # ===== Step 3: All retries failed =====
    return {
        **state,
        "status": "failed",
        "error": f"Commit failed after retries. Last error: {error_type}",
    }


# ==============================================================================
# Conditional Edge Functions
# ==============================================================================


def route_after_prepare(state: CommitState) -> Literal["execute", "END"]:
    """
    Route after prepare stage based on preparation results.

    Returns:
        "execute" if all checks passed (will interrupt before execute)
        "END" if there are issues (empty, security_violation, error)
    """
    status = state.get("status")

    if status == "prepared":
        return "execute"  # Goes to interrupt before execute
    return "END"


# ==============================================================================
# Workflow Construction
# ==============================================================================


def build_workflow() -> StateGraph:
    """
    Build the Smart Commit Workflow StateGraph.

    Flow: prepare -> (interrupt) -> execute

    The graph interrupts before 'execute' node, allowing:
    1. LLM to receive the diff and staged files
    2. LLM to analyze and generate commit message
    3. User to approve
    4. Workflow to resume with the approved message

    Returns:
        Compiled StateGraph ready to run
    """
    workflow = StateGraph(CommitState)

    # Add nodes
    workflow.add_node("prepare", node_prepare)
    workflow.add_node("execute", node_execute)

    # Set entry point
    workflow.set_entry_point("prepare")

    # After prepare: check results, may skip to end
    workflow.add_conditional_edges(
        "prepare",
        route_after_prepare,
        {
            "execute": "execute",
            "END": END,
        },
    )

    # After execute: workflow complete
    workflow.add_edge("execute", END)

    return workflow


# Compile with interrupt BEFORE execute node for Human-in-the-Loop
_workflow = build_workflow().compile(
    checkpointer=_memory,
    interrupt_before=["execute"],
)


# ==============================================================================
# Convenience Functions
# ==============================================================================


def start_workflow(
    project_root: str = ".",
    workflow_id: str = "default",
) -> CommitState:
    """
    Start a new smart commit workflow.

    Runs the graph until it reaches the interrupt point (before execute).

    Args:
        project_root: Project root path
        workflow_id: Unique ID for this workflow session

    Returns:
        State at interrupt point with diff_content for LLM analysis
    """
    initial_state = create_initial_state(
        project_root=project_root,
        workflow_id=workflow_id,
    )

    config = {"configurable": {"thread_id": workflow_id}}

    # Run until interrupt (at execute node)
    for _ in _workflow.stream(initial_state, config):
        pass

    # Get state at interrupt
    snapshot = _workflow.get_state(config)
    return snapshot.values


def approve_workflow(
    message: str,
    workflow_id: str = "default",
) -> CommitState:
    """
    Approve a pending commit and resume the workflow.

    Args:
        message: LLM-generated commit message
        workflow_id: Same workflow ID used when starting

    Returns:
        Final state after commit execution
    """
    config = {"configurable": {"thread_id": workflow_id}}

    # Get current state
    snapshot = _workflow.get_state(config)
    current_state = snapshot.values if snapshot else {}

    # Update state with approval and message from LLM
    updated_state = {
        **current_state,
        "status": "approved",
        "final_message": message,
    }
    _workflow.update_state(config, updated_state)

    # Direct call to node_execute instead of relying on langgraph resume
    # This is more reliable than the interrupt mechanism
    result = node_execute(updated_state)

    # Update the checkpoint with the result
    _workflow.update_state(config, result)

    return result


def reject_workflow(workflow_id: str = "default") -> CommitState:
    """
    Reject/cancel a pending commit.

    Args:
        workflow_id: Same workflow ID used when starting

    Returns:
        Final state after rejection
    """
    config = {"configurable": {"thread_id": workflow_id}}

    # Update state with rejection
    _workflow.update_state(config, {"status": "rejected"})

    # Resume to complete the workflow
    for _ in _workflow.stream(None, config):
        pass

    return _workflow.get_state(config).values


def get_workflow_status(workflow_id: str = "default") -> Optional[CommitState]:
    """
    Get the current status of a workflow.

    Args:
        workflow_id: The workflow checkpoint ID

    Returns:
        Current state or None if not found
    """
    config = {"configurable": {"thread_id": workflow_id}}
    snapshot = _workflow.get_state(config)

    if snapshot:
        return snapshot.values
    return None


def format_review_card(state: CommitState) -> str:
    """
    Generate a review card from the current state for LLM consumption.

    This format is designed to be passed back to the LLM for analysis
    and message generation.

    Args:
        state: Current CommitState

    Returns:
        Formatted review card string
    """
    import re

    status = state.get("status")

    # Status: Empty
    if status == "empty":
        return "🤷 **Nothing to commit** - No staged files detected."

    # Status: Security Violation
    if status == "security_violation":
        issues = state.get("security_issues", [])
        return f"⚠️ **Security Issue Detected**\n\nSensitive files detected:\n{', '.join(issues)}\n\nPlease remove sensitive files or add them to .gitignore."

    # Status: Lefthook Failed (format issues detected)
    if status == "lefthook_failed":
        error = state.get("error", "")
        return f"""❌ **Lefthook Pre-commit Failed**

The pre-commit checks found formatting issues that must be fixed before committing:

{error}

**Files are still staged** - Fix the issues above and run `/smart-commit` again."""

    # Status: Error
    if status == "error":
        return f"❌ **Error**: {state.get('error', 'Unknown error')}"

    # Status: Prepared (ready for LLM analysis)
    if status == "prepared":
        # Build data for template
        staged_files = state.get("staged_files", [])
        files_list = "\n".join([f"- `{f}`" for f in staged_files[:15]])
        if len(staged_files) > 15:
            files_list += f"\n- ... and {len(staged_files) - 15} more files"

        diff = state.get("diff_content", "")
        workflow_id = state.get("workflow_id", "default")

        # Get scope warning from state (set during prepare)
        scope_warning = state.get("scope_warning", "")

        # Get valid scopes from cog.toml
        valid_scopes = _get_valid_scopes()

        # Build review card with scope validation notice
        review_lines = []

        if valid_scopes:
            review_lines.append(f"**Valid Scopes**: {', '.join(valid_scopes)}")
            if scope_warning:
                review_lines.append(f"\n{scope_warning}")

        review_lines.append(f"\n**{len(staged_files)} Files to commit**")
        review_lines.append(files_list)

        # Add diff preview
        if diff:
            review_lines.append(f"\n**Diff Preview**:\n{diff[:2000]}")

        # Add scope validation notice for LLM
        if valid_scopes:
            review_lines.append(
                "\n**⚠️ Scope Validation Notice**: "
                "If your commit message uses a scope NOT in the list above, "
                "please REPLACE it with a valid scope from the list."
            )

        return "\n".join(review_lines)

    # Status: Completed
    if status == "completed":
        commit_hash = state.get("commit_hash", "unknown")
        message = state.get("final_message", "")
        staged_files = state.get("staged_files", [])

        # Parse message into subject and body
        lines = message.strip().split("\n")
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip()

        # Use the new commit message template
        return rendering.render_commit_message(
            subject=subject,
            body=body,
            status="committed",
            commit_hash=commit_hash,
            file_count=len(staged_files),
            verified_by="omni Git Skill (cog)",
            security_status="No sensitive files detected",
        )

    # Status: Rejected
    if status == "rejected":
        return "🛑 **Commit Cancelled** - You rejected this commit."

    return f"ℹ️ **Status**: {status}"


__all__ = [
    "build_workflow",
    "start_workflow",
    "approve_workflow",
    "reject_workflow",
    "get_workflow_status",
    "format_review_card",
]
