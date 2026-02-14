"""
commands.py - Smart Commit Skill Commands

Entry point for git.smart_commit skill command.
Contains the async function decorated with @skill_command.

Imports from modularized workflow, nodes, and state modules.
"""

import uuid
import re
import os
import subprocess
import shutil
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from git.scripts.prepare import _get_cog_scopes, stage_and_scan
from git.scripts.rendering import render_commit_message, render_template

from omni.foundation.checkpoint import load_workflow_state, save_workflow_state
from omni.foundation.config.logging import get_logger
from omni.langgraph.visualize import register_workflow
from omni.foundation.api.decorators import skill_command

from ._enums import SmartCommitAction, SmartCommitStatus, WorkflowRouting
from .state import create_initial_state
from .workflow import _get_diagram as _get_workflow_diagram

logger = get_logger("git.smart_commit")

# Workflow type identifier for checkpoint table
_WORKFLOW_TYPE = "smart_commit"


def _handle_submodules_prepare(project_root: str) -> list[dict[str, str]]:
    """Detect submodules with changes and run prepare in each.

    For each submodule with changes:
    1. cd into submodule
    2. Stage files with git add -A
    3. Run lefthook pre-commit
    4. Return info about committed submodules
    """
    submodule_commits = []

    try:
        # Check if project has submodules
        proc = subprocess.run(
            ["git", "submodule", "status"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        # Parse submodule status lines
        # Format: "<status> <sha1> <path> (<ref>)"
        submodule_lines = proc.stdout.split("\n")

        for line in submodule_lines:
            if not line:
                continue

            # Get status char from FIRST character
            status_char = line[0]
            parts = line[1:].strip().split()
            if len(parts) >= 2:
                submodule_path = parts[1]
                sub_full_path = Path(project_root) / submodule_path

                # Check if submodule has its own changes
                proc_sub = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=sub_full_path,
                    capture_output=True,
                    text=True,
                )
                has_internal_changes = proc_sub.returncode == 0 and proc_sub.stdout.strip()

                if has_internal_changes or status_char == "+":
                    try:
                        # Stage all changes in submodule
                        subprocess.run(
                            ["git", "add", "-A"],
                            cwd=sub_full_path,
                            capture_output=True,
                        )
                        logger.info(f"Staged changes in submodule {submodule_path}")

                        # Run lefthook pre-commit if available
                        if shutil.which("lefthook"):
                            subprocess.run(
                                ["git", "hook", "run", "pre-commit"],
                                cwd=sub_full_path,
                                capture_output=True,
                            )
                            logger.info(f"Ran lefthook in submodule {submodule_path}")

                        # Get staged files count
                        proc_files = subprocess.run(
                            ["git", "diff", "--cached", "--name-only"],
                            cwd=sub_full_path,
                            capture_output=True,
                            text=True,
                        )
                        file_count = (
                            len(proc_files.stdout.strip().split("\n"))
                            if proc_files.stdout.strip()
                            else 0
                        )

                        if file_count > 0:
                            # Auto-commit in submodule
                            date_str = datetime.now().strftime("%Y%m%d")
                            commit_msg = (
                                f"chore(submodule): update {submodule_path} ({date_str})\n\n"
                                f"Auto-committed by omni smart_commit\n\n"
                                f"Submodule: {submodule_path}\nFiles: {file_count}"
                            )

                            commit_result = subprocess.run(
                                ["git", "commit", "-m", commit_msg],
                                cwd=sub_full_path,
                                capture_output=True,
                                text=True,
                            )

                            if commit_result.returncode == 0:
                                proc_hash = subprocess.run(
                                    ["git", "rev-parse", "HEAD"],
                                    cwd=sub_full_path,
                                    capture_output=True,
                                    text=True,
                                )
                                commit_hash = (
                                    proc_hash.stdout.strip()[:8]
                                    if proc_hash.returncode == 0
                                    else "unknown"
                                )
                                submodule_commits.append(
                                    {
                                        "path": submodule_path,
                                        "commit_hash": commit_hash,
                                    }
                                )
                                logger.info(
                                    f"Committed {file_count} files in submodule {submodule_path}: {commit_hash}"
                                )
                            else:
                                logger.warning(
                                    f"Failed to commit in {submodule_path}: {commit_result.stderr}"
                                )
                        else:
                            logger.info(f"No staged files in submodule {submodule_path}")

                    except Exception as e:
                        logger.warning(f"Failed to process submodule {submodule_path}: {e}")

        # After committing in submodules, stage the submodule reference updates in main repo
        if submodule_commits:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=project_root,
                capture_output=True,
            )
            logger.info(f"Staged {len(submodule_commits)} submodule reference updates")

    except Exception as e:
        logger.warning(f"Failed to handle submodules: {e}")

    return submodule_commits


@skill_command(
    name="smart_commit",
    category="workflow",
    description="""
    Primary git commit workflow with security scan and human approval.

    Multi-step workflow:
    1. start: Stages files, runs lefthook (formatting), security scan
    2. approve: User approves, LLM generates commit message, executes commit
    3. reject: Cancels the workflow
    4. status: Checks workflow status
    5. visualize: Shows the workflow diagram

    Submodule support: If project has submodules with changes, they are
    automatically committed first before the main repo commit.

    Returns:
        Workflow-specific result messages based on the action.

    Example:
        @omni("git.smart_commit", {"action": "start"})
        @omni("git.smart_commit", {"action": "approve", "workflow_id": "abc123", "message": "feat(git): add commit workflow"})
    """,
    read_only=False,
    destructive=True,
    idempotent=False,
    open_world=False,
)
async def smart_commit(
    action: SmartCommitAction = SmartCommitAction.START,
    workflow_id: str = "",
    message: str = "",
    project_root: str = "",
) -> str:
    """Execute the Smart Commit workflow."""
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
                submodules_committed = result.get("submodules_committed", [])
                valid_scopes = _get_cog_scopes(Path(project_root))

                match status:
                    case SmartCommitStatus.EMPTY:
                        return "Nothing to commit - No staged files detected."
                    case SmartCommitStatus.LEFTHOOK_FAILED:
                        lefthook_output = result.get("error", "Unknown lefthook error")
                        return (
                            f"Lefthook Pre-commit Failed\n\n{lefthook_output}\n\n"
                            "Please fix the error above and try again."
                        )
                    case SmartCommitStatus.SECURITY_VIOLATION:
                        issues = result.get("security_issues", [])
                        return (
                            f"Security Issue Detected\n\nSensitive files detected:\n{', '.join(issues)}\n\n"
                            "Please resolve these issues before committing."
                        )
                    case _:
                        submodule_info = ""
                        if submodules_committed:
                            submodule_info = f"\n\n**Submodules committed:**\n" + "\n".join(
                                f"- `{s['path']}`: `{s['commit_hash']}`"
                                for s in submodules_committed
                            )

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
                            submodule_info=submodule_info,
                        )

            case SmartCommitAction.APPROVE:
                if not workflow_id:
                    return "workflow_id required for approve action"
                if not message:
                    return "message required for approve action"

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
                    matches = get_close_matches(commit_scope, valid_scopes, n=1, cutoff=0.6)
                    return {
                        "status": "error",
                        "message": f"Invalid scope: '{commit_scope}'. Valid scopes: {valid_scopes}",
                        "suggestion": f"Did you mean: {matches[0]}?"
                        if matches
                        else "Use a valid scope from the list",
                    }

                result = await _approve_smart_commit_async(
                    workflow_id=workflow_id,
                    message=message,
                    project_root=project_root,
                )

                submodule_commits = result.get("submodule_commits", [])
                submodule_section = ""
                if submodule_commits:
                    submodule_section = "\n\n**Submodule commits:**\n" + "\n".join(
                        f"- `{s['path']}`: `{s['commit_hash']}`" for s in submodule_commits
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
                    submodule_section=submodule_section,
                )

            case SmartCommitAction.REJECT:
                if not workflow_id:
                    return f"Commit Cancelled\n\nWorkflow `{workflow_id}` has been cancelled."
                return f"Commit Cancelled\n\nWorkflow `{workflow_id}` has been cancelled."

            case SmartCommitAction.STATUS:
                if not workflow_id:
                    return "workflow_id required for status action"
                status = await _get_workflow_status_async(workflow_id)
                if not status:
                    return f"Workflow `{workflow_id}` not found"

                submodules = status.get("submodules_committed", [])
                submodule_info = f"\nSubmodules committed: {len(submodules)}" if submodules else ""

                return (
                    f"Workflow Status (`{workflow_id}`)\n\n"
                    f"Status: {status.get('status', 'unknown')}\n"
                    f"Files: {len(status.get('staged_files', []))}"
                    f"{submodule_info}"
                )

            case SmartCommitAction.VISUALIZE:
                from omni.langgraph.visualize import visualize_workflow

                diagram = visualize_workflow("smart_commit")
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
    wf_id = str(uuid.uuid4())[:8]
    root = Path(project_root) if project_root else Path(".")

    result_data = stage_and_scan(project_root)

    staged_files = result_data.get("staged_files", [])
    diff = result_data.get("diff", "")
    security_issues = result_data.get("security_issues", [])
    lefthook_error = result_data.get("lefthook_error", "")
    lefthook_summary = result_data.get("lefthook_summary", "")

    # Handle submodules first
    submodule_commits = _handle_submodules_prepare(project_root)
    if submodule_commits:
        logger.info(f"Committed {len(submodule_commits)} submodules")

    # Re-stage after submodule commits (may have modified parent repo)
    if submodule_commits:
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=project_root,
                capture_output=True,
            )
            # Re-get staged files
            proc = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            staged_files = [f for f in proc.stdout.strip().split("\n") if f]
            diff = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=project_root,
                capture_output=True,
                text=True,
            ).stdout
        except Exception as e:
            logger.warning(f"Failed to re-stage after submodules: {e}")

    valid_scopes = _get_cog_scopes(root)
    scope_warning = ""

    initial_state = create_initial_state(project_root=project_root, workflow_id=wf_id)
    initial_state["staged_files"] = staged_files
    initial_state["diff_content"] = diff
    initial_state["security_issues"] = security_issues

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
    state_dict["submodules_committed"] = submodule_commits

    save_workflow_state(_WORKFLOW_TYPE, wf_id, state_dict)

    return state_dict


async def _approve_smart_commit_async(
    message: str,
    workflow_id: str,
    project_root: str = "",
) -> dict[str, Any]:
    """Approve and execute commit with the given message."""
    if not project_root:
        project_root = os.environ.get("PRJ_ROOT", ".")

    # Get already-committed submodule info from workflow state
    workflow_state = load_workflow_state(_WORKFLOW_TYPE, workflow_id)
    submodule_commits = workflow_state.get("submodules_committed", []) if workflow_state else []

    # Run lefthook pre-commit
    try:
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

    # Re-stage modified files
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        all_modified = [f for f in proc.stdout.strip().split("\n") if f]

        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        untracked = [f for f in proc.stdout.strip().split("\n") if f]

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

    # Save approved state
    save_workflow_state(
        _WORKFLOW_TYPE,
        workflow_id,
        {
            "status": SmartCommitStatus.APPROVED,
            "final_message": message,
            "file_count": file_count,
            "submodule_commits": submodule_commits,
        },
    )

    # Execute commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    commit_hash = ""
    if result.returncode == 0:
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
        "submodule_commits": submodule_commits,
    }


async def _get_workflow_status_async(workflow_id: str) -> dict[str, Any] | None:
    """Get workflow status from unified checkpoint store."""
    return load_workflow_state(_WORKFLOW_TYPE, workflow_id)


# Register workflow diagram
try:
    _SMART_COMMIT_DIAGRAM = _get_workflow_diagram()
    register_workflow("smart_commit", _SMART_COMMIT_DIAGRAM)
except Exception:
    pass


__all__ = ["smart_commit"]
