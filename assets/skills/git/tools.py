"""
git/tools.py - Git Skill Router (Phase 35.3)

This is the ROUTER layer - it only dispatches to implementation scripts.
All actual logic is in the scripts/ directory.

Architecture (Isolated Sandbox + Explicit Routing):
    tools.py    -> Router (just dispatches, validates params)
    scripts/    -> Controllers (actual implementation)
                -> Fully isolated namespace (no conflicts with docker/scripts/)

Naming Convention:
    @skill_command(name="<command>", ...)
    - Command names are just the function name (e.g., "commit", "status")
    - MCP Server automatically prefixes with skill name: "git.commit"

Usage:
    from agent.skills.git.scripts import status, branch, log

Note: We use absolute imports to work with ModuleLoader's package setup.
The scripts module is loaded as agent.skills.git.scripts.xxx
"""

from pathlib import Path
from typing import Optional

from agent.skills.decorators import skill_command

# ==============================================================================
# READ Operations (Router Layer)
# ==============================================================================


@skill_command(
    name="status",
    category="read",
    description="Get git status",
    inject_root=True,
)
def status(project_root: Path = None) -> str:
    """Check git status in project directory."""
    from agent.skills.git.scripts import status as status_mod

    return status_mod.git_status(project_root)


@skill_command(name="branch", category="read", description="List git branches.")
def branch() -> str:
    """List all branches."""
    from agent.skills.git.scripts import branch as branch_mod

    return branch_mod.list_branches()


@skill_command(name="log", category="read", description="Show recent commits.")
def log(n: int = 5) -> str:
    """Show recent commit history."""
    from agent.skills.git.scripts import log as log_mod

    return log_mod.get_log(n)


@skill_command(name="diff", category="read", description="Show changes.")
def diff(staged: bool = False, filename: Optional[str] = None) -> str:
    """Show working directory or staged changes."""
    from agent.skills.git.scripts import diff as diff_mod

    return diff_mod.get_diff(staged, filename)


@skill_command(name="remote", category="read", description="Show remotes.")
def remote() -> str:
    """Show remote repositories."""
    from agent.skills.git.scripts import remote as remote_mod

    return remote_mod.list_remotes()


@skill_command(name="tag_list", category="read", description="List tags.")
def tag_list() -> str:
    """List all git tags."""
    from agent.skills.git.scripts import tag_list as tag_mod

    return tag_mod.list_tags()


# ==============================================================================
# VIEW Operations (Router Layer)
# ==============================================================================


@skill_command(name="status_report", category="view", description="Formatted status report.")
def status_report() -> str:
    """Get a nice formatted status report."""
    from agent.skills.git.scripts import status as status_mod

    branch = status_mod.current_branch() or "unknown"
    has_staged, staged = status_mod.has_staged_files()
    has_unstaged, unstaged = status_mod.has_unstaged_files()

    lines = [f"**Branch**: `{branch}", ""]
    if has_staged:
        lines.extend(["**Staged**:", *[f"  ✅ {f}" for f in staged], ""])
    if has_unstaged:
        lines.extend(["**Unstaged**:", *[f"  ⚠️ {f}" for f in unstaged], ""])
    if not has_staged and not has_unstaged:
        lines.append("✅ Working tree clean")

    return "\n".join(lines)


@skill_command(name="smart_diff", category="view", description="Instructions for native diff.")
def smart_diff(filename: str, context: int = 3) -> str:
    """Show how to view diff natively."""
    return f"Run: `git diff -U{context} {filename}`"


# ==============================================================================
# WORKFLOW Operations (Router Layer)
# ==============================================================================


@skill_command(name="hotfix", category="workflow", description="Generate hotfix plan.")
def hotfix(issue_id: str, base: str = "main") -> str:
    """Generate a hotfix execution plan."""
    from agent.skills.git.scripts import branch as branch_mod

    plan = [
        f"git checkout {base}",
        "git pull",
        f"git checkout -b hotfix/{issue_id}",
    ]
    return f"**Hotfix Plan for {issue_id}**\n\n" + "\n".join([f"`{c}`" for c in plan])


# ==============================================================================
# WRITE Operations (Router Layer)
# ==============================================================================


@skill_command(name="add", category="write", description="Stage files.")
def add(files: list[str]) -> str:
    """Stage files for commit."""
    from agent.skills.git.scripts import add as add_mod

    return add_mod.add(files)


@skill_command(name="stage_all", category="write", description="Stage all changes.")
def stage_all(scan: bool = True) -> str:
    """Stage all changes with optional security scan."""
    import glob

    if scan:
        sensitive = []
        for p in ["*.env", "*.pem", "*.key", "*.secret"]:
            sensitive.extend(glob.glob(p, recursive=True))

        if sensitive:
            return f"⚠️ Blocked: {sensitive}"

    from agent.skills.git.scripts import add as add_mod

    return add_mod.add_all()


@skill_command(
    name="prepare_commit",
    category="workflow",
    description="Prepare commit: stage all, run checks, return staged diff.",
    inject_root=True,
)
def prepare_commit(project_root: Path = None, message: str = None) -> str:
    """
    Prepare commit workflow for /commit command.

    This command:
    1. Stages all changes with security scan
    2. Runs quality checks (lefthook pre-commit)
    3. Returns staged diff for commit analysis

    Returns:
        Formatted result with status, staged files, and diff
    """
    from agent.skills.git.scripts import prepare as prepare_mod

    result = prepare_mod.prepare_commit(project_root=project_root, message=message)
    return prepare_mod.format_prepare_result(result)


@skill_command(name="commit", category="write", description="Commit staged changes.")
def commit(message: str) -> str:
    """Commit staged changes with template rendering."""
    from agent.skills.git.scripts import commit as commit_mod
    from agent.skills.git.scripts import prepare as prepare_mod

    # First, execute the actual git commit
    result = commit_mod.commit(message)

    # If commit failed, return error
    if not result.startswith("✅"):
        return result

    # Run security guard check (same as prepare_commit)
    from common.gitops import get_project_root

    root = get_project_root()
    prep_result = prepare_mod.prepare_commit(project_root=root, message=message)

    # Get security status from prepare_commit result
    security_passed = prep_result.get("security_passed", True)
    security_issues = prep_result.get("security_issues", [])
    security_guard = prep_result.get("security_guard", "")
    # Ensure security_guard always has a value for template rendering
    if not security_guard:
        if security_passed:
            security_guard = (
                "🛡️ Security Guard Detection - No sensitive files detected. Safe to proceed."
            )
        else:
            security_guard = "⚠️ Security Guard Detection - Sensitive files detected. Please review."

    # Parse commit message for template rendering
    lines = message.strip().split("\n")
    first_line = lines[0]

    # Parse "type(scope): description" format
    import re

    match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", first_line)

    if match:
        commit_type = match.group(1)
        scope = match.group(2) or ""
        description = match.group(3)
        body = "\n".join(lines[1:]).strip()
    else:
        commit_type = ""
        scope = ""
        description = first_line
        body = ""

    # Use template rendering for the output
    from agent.skills.git.scripts.rendering import render_commit_message

    return render_commit_message(
        subject=first_line,
        body=body,
        status="committed",
        security_status="No sensitive files detected"
        if not security_issues
        else f"Issues: {', '.join(security_issues)}",
    )


# ==============================================================================
# SMART COMMIT Workflow (Phase 36.7)
# ==============================================================================
# Architecture: Tool provides data, LLM provides intelligence.
# Flow: prepare -> (LLM Analysis) -> execute
# ==============================================================================


import uuid


@skill_command(
    name="smart_commit",
    category="workflow",
    description="Smart commit: Tool stages & extracts diff, LLM analyzes & generates message",
)
def smart_commit(
    message: str = None,
    action: str = "start",
    workflow_id: str = None,
) -> str:
    """
    Smart commit workflow with Human-in-the-Loop (HITL) approval.

    Architecture: Tool provides data, LLM provides intelligence.

    Flow:
    1. prepare: Stage files, extract diff, run security scan
    2. LLM analyzes diff and generates commit message
    3. execute: Perform the actual git commit

    Args:
        message: LLM-generated commit message (for 'approve' action)
        action: "start" to begin workflow, "approve" to confirm, "reject" to cancel
        workflow_id: Unique workflow ID (auto-generated if not provided)

    Returns:
        Review card with diff for LLM analysis, or result message for approve/reject

    Usage:
        # Start workflow (returns diff for LLM analysis)
        @omni("git.smart_commit", {"action": "start"})

        # LLM analyzes diff, generates message, then:
        @omni("git.smart_commit", {"action": "approve", "workflow_id": "abc123", "message": "refactor(core): ..."})

        # Reject
        @omni("git.smart_commit", {"action": "reject", "workflow_id": "abc123"})
    """
    from common.gitops import get_project_root
    from agent.skills.git.scripts import smart_workflow as smart_mod

    root = get_project_root()
    thread_id = workflow_id or str(uuid.uuid4())[:8]

    if action == "start":
        # Start the workflow - runs prepare node and interrupts before execute
        state = smart_mod.start_workflow(
            project_root=str(root),
            workflow_id=thread_id,
        )

        # Return formatted review card for LLM consumption
        return smart_mod.format_review_card(state)

    elif action == "approve":
        if not message:
            return "❌ **Error**: Message required for 'approve' action"

        # Approve with LLM-generated message and resume
        state = smart_mod.approve_workflow(
            message=message,
            workflow_id=thread_id,
        )

        status = state.get("status")

        from agent.skills.git.scripts.rendering import render_commit_message

        if status == "error":
            return render_commit_message(
                subject="Commit Error",
                body=state.get("error", "Unknown error"),
                status="error",
                error=state.get("error", "Unknown error"),
                security_status="⚠️ Workflow Error",
            )
        elif status == "completed" and state.get("commit_hash"):
            # Workflow completed successfully - return success message
            retry_note = state.get("retry_note", "")
            note_line = f" ({retry_note})" if retry_note else ""

            return render_commit_message(
                subject=state.get("final_message", message).split("\n")[0],
                body="\n".join(state.get("final_message", message).split("\n")[1:]).strip(),
                status="committed",
                commit_hash=state.get("commit_hash", ""),
                file_count=len(state.get("staged_files", [])),
                verified_by="omni Git Skill (cog)" + note_line,
                security_status="No sensitive files detected",
            )
        elif status == "failed":
            # Commit failed after all retries
            error = state.get("error", "Unknown error")
            retry_note = state.get("retry_note", "")
            note_line = f" ({retry_note})" if retry_note else ""

            return render_commit_message(
                subject="Commit Failed",
                body=f"{error}{note_line}",
                status="failed",
                error=error,
                security_status="⚠️ Commit Failed",
            )
        elif status == "approved":
            # Execute node ran but commit failed (lefthook check, etc.)
            error = state.get("error", "Commit was not created")
            return render_commit_message(
                subject="Commit Failed",
                body="Workflow executed but commit was not created. Please fix the issue and try again.",
                status="failed",
                error=error,
                security_status="⚠️ Execution Error",
            )
        else:
            return render_commit_message(
                subject="Unexpected Status",
                body=f"Status: {status}",
                status="error",
                error=f"Unexpected status: {status}",
                security_status="⚠️ Unknown Status",
            )

    elif action == "reject":
        # Reject and cancel
        state = smart_mod.reject_workflow(workflow_id=thread_id)
        return "🛑 **Commit Cancelled** - You rejected this commit."

    else:
        return f"❌ **Unknown action**: {action}. Use 'start', 'approve', or 'reject'"


@skill_command(
    name="commit_status",
    category="read",
    description="Check status of a smart commit workflow",
)
def commit_status(workflow_id: str = "default") -> str:
    """Check the status of a pending smart commit workflow."""
    from agent.skills.git.scripts import smart_workflow as smart_mod

    state = smart_mod.get_workflow_status(workflow_id)

    if not state:
        return f"ℹ️ No workflow found with ID: {workflow_id}"

    status = state.get("status", "unknown")

    # New status values from simplified workflow
    if status == "prepared":
        return (
            "⏳ **Waiting for LLM Analysis** - Diff extracted, ready for commit message generation"
        )
    elif status == "completed":
        retry_note = state.get("retry_note", "")
        note = f" ({retry_note})" if retry_note else ""
        return f"✅ **Committed**{note} - `{state.get('commit_hash', 'unknown')}`"
    elif status == "failed":
        error = state.get("error", "Unknown error")
        return f"❌ **Failed** - {error}"
    elif status == "rejected":
        return "🛑 **Cancelled** - You rejected this commit"
    elif status == "security_violation":
        return "⚠️ **Security Issue** - Fix before committing"
    elif status == "error":
        return f"❌ **Error**: {state.get('error', 'Unknown')}"
    elif status == "empty":
        return "🤷 **Nothing to commit** - No staged files"
    else:
        return f"ℹ️ **Status**: {status}"


@skill_command(name="checkout", category="write", description="Switch branch.")
def checkout(branch: str, create: bool = False) -> str:
    """Switch to a branch."""
    from agent.skills.git.scripts import branch as branch_mod

    if create:
        return branch_mod.create_branch(branch, checkout=True)
    return branch_mod.create_branch(branch, checkout=False)


@skill_command(name="stash_save", category="write", description="Stash changes.")
def stash_save(msg: Optional[str] = None) -> str:
    """Stash working directory changes."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_save(msg)


@skill_command(name="stash_pop", category="write", description="Pop stash.")
def stash_pop() -> str:
    """Apply and remove last stash."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_pop()


@skill_command(name="stash_list", category="write", description="List stashes.")
def stash_list() -> str:
    """List all stashes."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_list()


@skill_command(name="reset", category="write", description="Reset HEAD.")
def reset(soft: bool = False, commit: Optional[str] = None) -> str:
    """Reset HEAD to a commit."""
    from agent.skills.git.scripts import add as add_mod

    cmd = ["git", "reset"]
    if soft:
        cmd.append("--soft")
    if commit:
        cmd.append(commit)
    import subprocess

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


@skill_command(name="merge", category="write", description="Merge branch.")
def merge(branch: str, no_ff: bool = True) -> str:
    """Merge a branch."""
    import subprocess

    cmd = ["git", "merge"]
    if no_ff:
        cmd.append("--no-ff")
    cmd.append(branch)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


@skill_command(name="tag_create", category="write", description="Create tag.")
def tag_create(name: str, msg: Optional[str] = None) -> str:
    """Create an annotated tag."""
    from agent.skills.git.scripts import tag_list as tag_mod

    return tag_mod.create_tag(name, msg)


@skill_command(name="revert", category="write", description="Revert commit.")
def revert(commit: str, no_commit: bool = False) -> str:
    """Revert a specific commit."""
    from agent.skills.git.scripts import commit as commit_mod

    return commit_mod.revert(commit, no_commit)


@skill_command(name="submodule_update", category="write", description="Update submodules.")
def submodule_update(init: bool = False) -> str:
    """Update git submodules."""
    import subprocess

    cmd = ["git", "submodule", "update", "--recursive"]
    if init:
        cmd.append("--init")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


# ==============================================================================
# EVOLUTION Operations (Router Layer)
# ==============================================================================


@skill_command(name="read_backlog", category="evolution", description="Read skill backlog.")
def read_backlog() -> str:
    """Read the Git Skill's own backlog."""
    from common.skill_utils import skill_path

    backlog = skill_path("assets/Backlog.md")
    return backlog.read_text() if backlog.exists() else "No backlog found"
