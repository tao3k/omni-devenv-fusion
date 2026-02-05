"""
nodes.py - Smart Commit Workflow Nodes

Contains all node functions for the smart commit workflow:
- check_state_node: Validates workflow state
- handle_submodules_node: Detects and processes submodule changes
- commit_submodules_node: Commits changes in each submodule
- lefthook_pre_commit_node: Runs lefthook pre-commit hooks
- Terminal nodes: empty, lefthook_error, security_warning, prepared
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Any

from omni.core.skills.state import GraphState
from omni.foundation.config.logging import get_logger

from ._enums import WorkflowRouting

logger = get_logger("git.smart_commit")


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


def _handle_submodules_node(state: GraphState) -> dict[str, Any]:
    """Handle submodule commits before main repo commit.

    This node:
    1. Detects if project has submodules with changes
    2. For each changed submodule:
       - cd into submodule
       - Stage files with git add -A
       - Run lefthook pre-commit
       - Auto-commit with generated message
    3. Stage submodule reference updates in main repo
    4. Return PREPARED for main repo workflow
    """
    import shutil
    from datetime import datetime

    project_root = os.environ.get("PRJ_ROOT") or state.get("project_root") or "."
    result = dict(state)

    try:
        # Check if project has submodules
        proc = subprocess.run(
            ["git", "submodule", "status"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            # No submodules, proceed normally
            result["_routing"] = WorkflowRouting.PREPARED
            result["submodules_committed"] = []
            return result

        # Parse submodule status lines
        # Format: "<status> <sha1> <path> (<ref>)"
        # - status can be " " (clean), "+" (new commits), "-" (not initialized)
        submodule_lines = proc.stdout.split("\n")
        submodules_with_changes = []

        for line in submodule_lines:
            if not line:
                continue

            # Get status char from FIRST character (before stripping)
            status_char = line[0]

            # The rest after status char: "sha1 path (ref)"
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

                # Submodule has changes if:
                # 1. status_char is '+' (recorded commit differs)
                # 2. OR submodule has internal changes
                if has_internal_changes or status_char == "+":
                    submodules_with_changes.append(submodule_path)

        if not submodules_with_changes:
            result["_routing"] = WorkflowRouting.PREPARED
            result["submodules_committed"] = []
            return result

        # Commit each submodule with changes
        submodule_commits = []
        for sub_path in submodules_with_changes:
            sub_full_path = Path(project_root) / sub_path

            try:
                # Stage all changes in submodule
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=sub_full_path,
                    capture_output=True,
                )
                logger.info(f"Staged changes in submodule {sub_path}")

                # Run lefthook pre-commit if available
                if shutil.which("lefthook"):
                    subprocess.run(
                        ["git", "hook", "run", "pre-commit"],
                        cwd=sub_full_path,
                        capture_output=True,
                    )
                    logger.info(f"Ran lefthook in submodule {sub_path}")

                # Get staged files for commit message
                proc_files = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=sub_full_path,
                    capture_output=True,
                    text=True,
                )
                file_count = (
                    len(proc_files.stdout.strip().split("\n")) if proc_files.stdout.strip() else 0
                )

                if file_count > 0:
                    # Generate commit message
                    date_str = datetime.now().strftime("%Y%m%d")
                    commit_msg = f"chore(submodule): update {sub_path} ({date_str})\n\nAuto-committed by omni smart_commit\n\nSubmodule: {sub_path}\nFiles: {file_count}"

                    # Commit in submodule
                    commit_result = subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=sub_full_path,
                        capture_output=True,
                        text=True,
                    )

                    if commit_result.returncode == 0:
                        # Get commit hash
                        proc_hash = subprocess.run(
                            ["git", "rev-parse", "HEAD"],
                            cwd=sub_full_path,
                            capture_output=True,
                            text=True,
                        )
                        commit_hash = (
                            proc_hash.stdout.strip()[:8] if proc_hash.returncode == 0 else "unknown"
                        )
                        submodule_commits.append(
                            {
                                "path": sub_path,
                                "commit_hash": commit_hash,
                            }
                        )
                        logger.info(
                            f"Committed {file_count} files in submodule {sub_path}: {commit_hash}"
                        )
                    else:
                        logger.warning(f"Failed to commit in {sub_path}: {commit_result.stderr}")
                else:
                    logger.info(f"No staged files in submodule {sub_path}, skipping commit")

            except Exception as e:
                logger.warning(f"Failed to process submodule {sub_path}: {e}")

        # After committing in submodules, stage the submodule reference updates in main repo
        subprocess.run(
            ["git", "add", "-A"],
            cwd=project_root,
            capture_output=True,
        )
        logger.info(f"Staged {len(submodule_commits)} submodule reference updates in main repo")

        result["_routing"] = WorkflowRouting.PREPARED
        result["submodules_committed"] = submodule_commits
        result["submodule_info"] = (
            (
                f"\n\n**Submodules committed:**\n"
                + "\n".join(f"- `{s['path']}`: `{s['commit_hash']}`" for s in submodule_commits)
            )
            if submodule_commits
            else ""
        )

        logger.info(f"Handled {len(submodule_commits)} submodules with changes")

    except Exception as e:
        logger.warning(f"Failed to handle submodules: {e}")
        result["_routing"] = WorkflowRouting.PREPARED
        result["submodules_committed"] = []
        result["submodule_info"] = ""

    return result


def _commit_submodules_node(state: GraphState) -> dict[str, Any]:
    """Commit changes in all submodules with pending changes.

    This node is called after user approves the commit message.
    It stages and commits changes in each submodule, then stages the
    submodule reference updates in the main repo.
    """
    project_root = os.environ.get("PRJ_ROOT") or state.get("project_root") or "."
    result = dict(state)

    submodules_pending = state.get("submodules_pending", [])
    main_commit_message = state.get("final_message", "")

    if not submodules_pending:
        result["_routing"] = WorkflowRouting.PREPARED
        return result

    submodule_commits = []

    try:
        for sub_path in submodules_pending:
            sub_full_path = Path(project_root) / sub_path

            if not sub_full_path.exists():
                logger.warning(f"Submodule path {sub_path} does not exist, skipping")
                continue

            # Stage all changes in submodule
            subprocess.run(
                ["git", "add", "-A"],
                cwd=sub_full_path,
                capture_output=True,
            )

            # Check if there are staged changes
            proc = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=sub_full_path,
                capture_output=True,
                text=True,
            )
            if not proc.stdout.strip():
                # No staged changes in submodule, skip
                continue

            # Generate commit message for submodule
            sub_commit_message = f"""chore(submodule): update {sub_path}

{main_commit_message}

[Auto-generated by omni smart_commit for submodule]

Submodule: {sub_path}
"""

            # Commit in submodule
            commit_result = subprocess.run(
                ["git", "commit", "-m", sub_commit_message],
                cwd=sub_full_path,
                capture_output=True,
                text=True,
            )

            if commit_result.returncode == 0:
                # Get the commit hash
                proc_hash = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=sub_full_path,
                    capture_output=True,
                    text=True,
                )
                commit_hash = (
                    proc_hash.stdout.strip()[:8] if proc_hash.returncode == 0 else "unknown"
                )

                submodule_commits.append(
                    {
                        "path": sub_path,
                        "commit_hash": commit_hash,
                    }
                )
                logger.info(f"Committed changes in submodule {sub_path}: {commit_hash}")
            else:
                logger.warning(f"Failed to commit in submodule {sub_path}: {commit_result.stderr}")

        # After committing in submodules, stage the submodule reference updates
        subprocess.run(
            ["git", "add", "-A"],
            cwd=project_root,
            capture_output=True,
        )

        result["submodule_commits"] = submodule_commits
        result["_routing"] = WorkflowRouting.PREPARED

    except Exception as e:
        logger.warning(f"Failed to commit submodules: {e}")
        result["_routing"] = WorkflowRouting.PREPARED

    return result


__all__ = [
    "_check_state_node",
    "_route_state",
    "_return_state",
    "_lefthook_pre_commit_node",
    "_handle_submodules_node",
    "_commit_submodules_node",
]
