"""
agent/skills/git/tools.py
Git Skill - Complete Git Operations for Version Control.

Phase 24: The MiniMax Shift
Protocol-Native Implementation - All tools return str for MCP compliance.

This module provides all Git capabilities:
- Status, diff, log operations (read-only)
- View-Enhanced tools (Markdown with icons/code blocks)
- Error handling and safe defaults

Key Principle: All @mcp.tool functions return str (not dict).
FastMCP auto-wraps str into CallToolResult(content=[TextContent...]).
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================


class GitError(Exception):
    """Raised when a git command fails."""

    pass


# ==============================================================================
# Core Git Implementation (Migrated from common/mcp_core/gitops.py)
# ==============================================================================


def _run_git(args: List[str], check: bool = True) -> str:
    """
    Execute a raw git command.

    This is the internal workhorse for all git operations.

    Args:
        args: Git command arguments (without 'git')
        check: If True, raise GitError on non-zero exit code

    Returns:
        Command stdout (stripped)

    Raises:
        GitError: If check=True and command fails
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check and result.returncode != 0:
            error_msg = f"Git command failed: git {' '.join(args)}\n{result.stderr}"
            logger.error(error_msg)
            raise GitError(error_msg)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        error_msg = f"Git command timed out: git {' '.join(args)}"
        logger.error(error_msg)
        raise GitError(error_msg)
    except FileNotFoundError:
        error_msg = "Git executable not found. Is git installed?"
        logger.error(error_msg)
        raise GitError(error_msg)


# ==============================================================================
# Helper Functions for View Layer
# ==============================================================================


def _get_status_details() -> Tuple[str, bool, List[str], List[str]]:
    """
    Get detailed git status for rendering.

    Returns:
        Tuple of (branch, is_dirty, staged_files, unstaged_files)
    """
    # Get current branch
    try:
        branch = _run_git(["branch", "--show-current"])
    except GitError:
        branch = "unknown"

    # Get porcelain status
    status_output = _run_git(["status", "--porcelain"])

    staged = []
    unstaged = []

    for line in status_output.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:]

        # First column: staged (added, modified, deleted, renamed, copied)
        # Second column: unstaged (modified, deleted, untracked)
        if code[0] in "AMDRC":
            staged.append(path)
        if code[1] in "AMDRC?" or code[1] != " ":
            unstaged.append(path)

    is_dirty = bool(staged or unstaged)

    return branch, is_dirty, staged, unstaged


# ==============================================================================
# Self-Evolution Tools (Bootstrap Pattern)
# ==============================================================================


def git_read_backlog() -> str:
    """
    [Evolution] Read the Git Skill's own backlog to see what features are missing.
    Use this to decide what to implement next.
    """
    from pathlib import Path

    # Backlog.md is in the same directory as tools.py
    backlog_path = Path(__file__).parent / "Backlog.md"

    if not backlog_path.exists():
        return "Backlog.md not found in git skill directory."

    content = backlog_path.read_text(encoding="utf-8")

    # FastMCP auto-wraps str into CallToolResult(content=[TextContent(...)])
    return content


# ==============================================================================
# View-Enhanced Tools (Inline Markdown Formatting)
# ==============================================================================


def _render_status_report(
    branch: str, is_dirty: bool, staged: list[str], unstaged: list[str]
) -> str:
    """Render a status report using Markdown with icons."""
    status_icon = "🔴 Dirty" if is_dirty else "🟢 Clean"

    report = f"""
📊 **Git Status Report**

* **Branch**: `{branch}`
* **State**: {status_icon}
"""

    if staged:
        report += "\n**Staged Changes:**\n"
        for f in staged:
            report += f"  ✅ `{f}`\n"
        report += "\n"

    if unstaged:
        report += "**Unstaged Changes:**\n"
        for f in unstaged:
            report += f"  ⚠️ `{f}`\n"
        report += "\n"

    if not staged and not unstaged:
        report += "\n✅ Working tree is clean. No changes to commit.\n"

    return report


def _render_hotfix_plan(
    issue_id: str, commands: list[str], explanation: list[str]
) -> str:
    """Render a Hotfix Plan as a Terminal Block."""
    cmd_block = " && \\\n    ".join(commands)
    expl_text = "\n".join([f"- {item}" for item in explanation])

    return f"""
🛠️ **Hotfix Plan Prepared**

I have calculated the safe path to fix Issue-{issue_id}.

**Strategy:**
{expl_text}

**Please execute the following command block in your terminal to apply this environment:**

```bash
cd $(git rev-parse --show-toplevel) && \\
    {cmd_block}

```

*Tip: Click "Run" to execute, or copy the command block.*
"""


def _render_smart_diff(filename: str, context_lines: int = 3) -> str:
    """Instruct Claude to run git diff natively."""
    return f"""
🔍 **Review Required**

I have identified that `{filename}` has modifications that need your attention.
To review them with the best UX, please execute the following command:

```bash
git diff -U{context_lines} {filename}

```

This will show you exactly what changed in a familiar diff format.
"""


def git_status_report() -> str:
    """
    [VIEW] Returns a formatted git status report with UI hints.

    Returns a nicely formatted Markdown report showing:
    - Current branch
    - Working tree state (clean/dirty)
    - Staged files (with ✅)
    - Unstaged files (with ⚠️)

    Use this for better UX instead of raw git status.
    """
    try:
        branch, is_dirty, staged, unstaged = _get_status_details()
        return _render_status_report(branch, is_dirty, staged, unstaged)
    except Exception as e:
        return f"Error checking status: {e}"


# ==============================================================================
# Workflow Tools (Phase 24)
# ==============================================================================


def git_plan_hotfix(
    issue_id: str,
    base_branch: str = "main",
    create_branch: bool = True,
) -> str:
    """
    [WORKFLOW] Generates a hotfix execution plan.

    Smartly handles stashing if the working directory is dirty.

    Args:
        issue_id: The issue identifier (e.g., "999", "OSD-123")
        base_branch: Base branch to work from
        create_branch: Whether to create a new hotfix branch

    Returns:
        A formatted plan with commands to execute
    """
    try:
        # 1. Logic: Check environment
        branch, is_dirty, staged, unstaged = _get_status_details()

        commands = []
        explanation = []

        # 2. Logic: Build Plan
        if is_dirty:
            explanation.append("Stash: Detected uncommitted changes, stashing them first")
            commands.append(f'git stash push -m "Auto-stash before hotfix/{issue_id}"')

        explanation.append(f"Checkout: Switching to '{base_branch}' and updating")
        commands.append(f"git checkout {base_branch}")
        commands.append("git pull")

        if create_branch:
            branch_name = f"hotfix/{issue_id}"
            explanation.append(f"Branch: Creating '{branch_name}'")
            commands.append(f"git checkout -b {branch_name}")

        cmd_block = " && \\\n    ".join(commands)
        expl_text = "\n".join([f"- {item}" for item in explanation])

        # 3. View: Render using views module
        return _render_hotfix_plan(issue_id, commands, explanation)

    except Exception as e:
        return f"Error: {e}"


def git_smart_diff(filename: str, context_lines: int = 3) -> str:
    """
    [VIEW] Returns instructions to show a native git diff.

    Use this instead of reading the file if you suspect changes.
    Claude will render this with native git diff UI.
    """
    return _render_smart_diff(filename, context_lines)


# ==============================================================================
# Atomic Tools (Preserved for Low-Level Access)
# ==============================================================================


def git_status(short: bool = False) -> str:
    """
    Get the current status of the git repository.

    Args:
        short: If True, returns short format (-s)

    Returns:
        Git status output
    """
    args = ["status"]
    if short:
        args.append("-s")
    return _run_git(args)


def git_diff(staged: bool = False, filename: Optional[str] = None) -> str:
    """
    Get the diff of changes.

    Args:
        staged: If True, shows staged changes (--staged)
        filename: Optional filename to limit the diff

    Returns:
        Git diff output
    """
    args = ["diff"]
    if staged:
        args.append("--staged")
    if filename:
        args.append(filename)
    return _run_git(args)


def git_log(n: int = 5, oneline: bool = True) -> str:
    """
    Show recent commit logs.

    Args:
        n: Number of commits to show
        oneline: If True, uses --oneline format

    Returns:
        Git log output
    """
    args = ["log", f"-n{n}"]
    if oneline:
        args.append("--oneline")
    return _run_git(args)


def git_branch(show_remote: bool = False) -> str:
    """
    List all git branches.

    Args:
        show_remote: If True, include remote branches (-a)

    Returns:
        Branch list output
    """
    args = ["branch"]
    if show_remote:
        args.append("-a")
    return _run_git(args)


def git_show(path: str) -> str:
    """
    Show the content of a file at a specific commit.

    Args:
        path: File path to show (can include commit:path format)

    Returns:
        File content at that point in history
    """
    return _run_git(["show", path])


def git_remote() -> str:
    """
    Show remote repositories.

    Returns:
        Remote list (origin, etc.)
    """
    return _run_git(["remote", "-v"])


# ==============================================================================
# Write Operations (Require Caution)
# ==============================================================================


def git_add(files: List[str]) -> str:
    """
    Stage files for commit.

    Args:
        files: List of file paths to add. Use ["."] to add all.

    Returns:
        Output message
    """
    return _run_git(["add"] + files)


def git_stage_all(scan: bool = True) -> str:
    """
    Stage all changes in the repository.

    This is a convenience wrapper around git_add(["."]) with optional
    security scanning for sensitive files.

    Args:
        scan: If True, scan for sensitive files before staging

    Returns:
        Output message
    """
    if scan:
        # Simple pattern check - deny staging if sensitive files are present
        import glob

        sensitive_found = []
        for pattern in ["*.env", ".env*", "*.pem", "*.key", "*.secret"]:
            matches = glob.glob(pattern, recursive=True)
            sensitive_found.extend(matches)

        if sensitive_found:
            return f"⚠️ Staging blocked: Found sensitive files: {sensitive_found}"

    return _run_git(["add", "."])


def git_commit(message: str) -> str:
    """
    Commit staged changes.

    Args:
        message: The commit message

    Returns:
        Commit hash and message
    """
    return _run_git(["commit", "-m", message])


def git_checkout(branch: str, create: bool = False) -> str:
    """
    Switch to a branch or create a new one.

    Args:
        branch: Target branch name
        create: If True, create the branch first (-b)

    Returns:
        Checkout output
    """
    if create:
        return _run_git(["checkout", "-b", branch])
    return _run_git(["checkout", branch])


def git_stash_save(message: Optional[str] = None) -> str:
    """
    Stash changes in the working directory.

    Args:
        message: Optional stash message

    Returns:
        Stash output
    """
    args = ["stash", "push"]
    if message:
        args.extend(["-m", message])
    return _run_git(args)


def git_stash_pop() -> str:
    """
    Apply the last stashed changes and remove from stash.

    Returns:
        Stash pop output
    """
    return _run_git(["stash", "pop"])


def git_stash_list() -> str:
    """
    List all stashed changes.

    Returns:
        Stash list output
    """
    return _run_git(["stash", "list"])


def git_reset(soft: bool = False, commit: Optional[str] = None) -> str:
    """
    Reset current HEAD to a specific state.

    Args:
        soft: If True, use --soft (keep changes in working directory)
        commit: Target commit (default: HEAD~1)

    Returns:
        Reset output
    """
    args = ["reset"]
    if soft:
        args.append("--soft")
    if commit:
        args.append(commit)
    return _run_git(args)


def git_revert(commit: str, no_commit: bool = False) -> str:
    """
    Revert a specific commit.

    Args:
        commit: Commit hash to revert
        no_commit: If True, prepare revert but don't commit

    Returns:
        Revert output
    """
    args = ["revert"]
    if no_commit:
        args.append("--no-commit")
    args.append(commit)
    return _run_git(args)


# ==============================================================================
# Tag Operations
# ==============================================================================


def git_tag_list() -> str:
    """
    List all tags.

    Returns:
        Tag list output
    """
    return _run_git(["tag", "-l"])


def git_tag_create(name: str, message: Optional[str] = None) -> str:
    """
    Create an annotated tag.

    Args:
        name: Tag name
        message: Optional tag message

    Returns:
        Tag creation output
    """
    args = ["tag"]
    if message:
        args.extend(["-m", message])
    args.append(name)
    return _run_git(args)


# ==============================================================================
# Merge Operations
# ==============================================================================


def git_merge(branch: str, no_ff: bool = True, message: Optional[str] = None) -> str:
    """
    Merge a branch into current branch.

    Args:
        branch: Source branch to merge
        no_ff: If True, create merge commit even if fast-forward
        message: Optional merge commit message

    Returns:
        Merge output
    """
    args = ["merge"]
    if no_ff:
        args.append("--no-ff")
    if message:
        args.extend(["-m", message])
    args.append(branch)
    return _run_git(args)


# ==============================================================================
# Submodule Operations
# ==============================================================================


def git_submodule_update(init: bool = False) -> str:
    """
    Update submodules.

    Args:
        init: If True, initialize submodules first (--init)

    Returns:
        Submodule update output
    """
    args = ["submodule", "update", "--recursive"]
    if init:
        args.append("--init")
    return _run_git(args)


# ==============================================================================
# Exported Functions (for Skill Registry)
# ==============================================================================


__all__ = [
    # Exceptions
    "GitError",
    # Read operations
    "git_status",
    "git_diff",
    "git_log",
    "git_branch",
    "git_show",
    "git_remote",
    "git_tag_list",
    # Phase 24: Director Pattern
    "git_status_report",
    # Phase 24: Workflow Tools
    "git_plan_hotfix",
    "git_smart_diff",
    # Write operations
    "git_add",
    "git_stage_all",
    "git_commit",
    "git_checkout",
    "git_stash_save",
    "git_stash_pop",
    "git_stash_list",
    "git_reset",
    "git_revert",
    # Tag operations
    "git_tag_create",
    # Merge operations
    "git_merge",
    # Submodule operations
    "git_submodule_update",
    # Phase 24: Workflow
    "invoke_git_workflow",
    # Registration
    "register",
]


# ==============================================================================
# MCP Tool Registration
# ==============================================================================


async def invoke_git_workflow(
    intent: str,
    target_branch: str = "",
    commit_message: str = "",
    checkpoint_id: str = None,
) -> str:
    """
    [Phase 24] Invoke Git workflow with LangGraph orchestration.

    Use this for complex Git operations that require multiple steps:
    - Hotfix: Check env -> Stash if dirty -> Switch branch -> Commit -> Pop stash
    - PR workflow: Similar to hotfix with proper branch handling
    - Branch operations: Switch with optional creation

    Args:
        intent: High-level intent (hotfix, pr, branch, commit, stash)
        target_branch: Target branch for operations
        commit_message: Commit message for commit operations
        checkpoint_id: Optional checkpoint ID for state persistence

    Returns:
        Formatted workflow result with success/error status
    """
    try:
        # Lazy load workflow module using importlib to avoid import issues
        # during skill loading (spec-based loading doesn't register in sys.modules)
        import importlib.util
        import sys
        from pathlib import Path

        workflow_path = Path(__file__).parent / "workflow.py"
        if not workflow_path.exists():
            return "Error: Workflow module not found"

        module_name = "agent.skills.git.workflow"

        # Load the module if not already in sys.modules
        if module_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(module_name, workflow_path)
            if spec and spec.loader:
                workflow_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = workflow_module
                spec.loader.exec_module(workflow_module)
            else:
                return "Error: Could not create spec for workflow module"
        else:
            workflow_module = sys.modules[module_name]

        result = await workflow_module.run_git_workflow(
            intent=intent,
            target_branch=target_branch,
            commit_message=commit_message,
            checkpoint_id=checkpoint_id,
        )

        return workflow_module.format_workflow_result(result)
    except ImportError as e:
        return f"Error: Workflow module not available. Ensure langgraph is installed.\nDetails: {e}"
    except Exception as e:
        logger.error("Workflow invocation failed", error=str(e))
        return f"Error invoking Git workflow: {e}"


def register(mcp: FastMCP) -> None:
    """
    Register all git tools with the MCP server.

    This function is called by the SkillRegistry during hot reload.

    Args:
        mcp: FastMCP server instance
    """
    # Read operations (safe)
    mcp.add_tool(git_status, description="Get the current status of the git repository.")
    mcp.add_tool(git_diff, description="Get the diff of changes.")
    mcp.add_tool(git_log, description="Show recent commit logs.")
    mcp.add_tool(git_branch, description="List all git branches.")
    mcp.add_tool(git_show, description="Show file content at a specific commit.")
    mcp.add_tool(git_remote, description="Show remote repositories.")
    mcp.add_tool(git_tag_list, description="List all tags.")

    # Phase 24: Director Pattern (View-Enhanced Tools)
    mcp.add_tool(
        git_status_report,
        description="""[VIEW] Get a formatted git status report with icons.

        Returns a nicely formatted Markdown report showing:
        - Current branch
        - Working tree state (clean/dirty)
        - Staged files (with ✅)
        - Unstaged files (with ⚠️)

        Use this for better UX instead of raw git status.
        """,
    )

    # Phase 24: Workflow Tools
    mcp.add_tool(
        git_plan_hotfix,
        description="""[WORKFLOW] Generate a hotfix execution plan.

        Smartly handles the current environment:
        - Stashes changes if working tree is dirty
        - Switches to base branch and pulls latest
        - Creates a new hotfix branch

        Returns a terminal block with all commands to execute.
        This uses Bypass Rendering for better UX.

        Args:
            issue_id: The issue identifier (e.g., "999")
            base_branch: Base branch to work from (default: "main")
            create_branch: Whether to create a new hotfix branch
        """,
    )
    mcp.add_tool(
        git_smart_diff,
        description="""[VIEW] Get instructions to view a native git diff.

        Use this instead of reading the file directly when you want
        to see what changed. Returns a terminal block with the diff command.

        Args:
            filename: Path to the file to diff
            context_lines: Number of context lines to show (default: 3)
        """,
    )

    # Write operations (require caution)
    mcp.add_tool(git_add, description="Stage files for commit.")
    mcp.add_tool(git_stage_all, description="Stage all changes with optional security scan.")
    mcp.add_tool(git_commit, description="Commit staged changes.")
    mcp.add_tool(git_checkout, description="Switch to a branch or create a new one.")
    mcp.add_tool(git_stash_save, description="Stash changes in the working directory.")
    mcp.add_tool(git_stash_pop, description="Apply the last stashed changes.")
    mcp.add_tool(git_stash_list, description="List all stashed changes.")
    mcp.add_tool(git_reset, description="Reset current HEAD to a specific state.")
    mcp.add_tool(git_revert, description="Revert a specific commit.")

    # Advanced operations
    mcp.add_tool(git_tag_create, description="Create an annotated tag.")
    mcp.add_tool(git_merge, description="Merge a branch into current branch.")
    mcp.add_tool(git_submodule_update, description="Update submodules.")

    # Phase 24: Self-Evolution Tools (Bootstrap Pattern)
    mcp.add_tool(
        git_read_backlog,
        description="""[Evolution] Read the Git Skill's own backlog to see what features are missing.

        Use this to decide what to implement next. Returns the content of Backlog.md.
        """,
    )

    # Phase 24: Living Skill Architecture - Workflow tools
    mcp.add_tool(
        invoke_git_workflow,
        description="""Invoke Git workflow with LangGraph orchestration.

        Use this for complex Git operations that require multiple steps:
        - Hotfix: Check env -> Stash if dirty -> Switch branch -> Commit -> Pop stash
        - PR workflow: Similar to hotfix with proper branch handling
        - Branch operations: Switch with optional creation

        Args:
            intent: High-level intent (hotfix, pr, branch, commit, stash)
            target_branch: Target branch for operations
            commit_message: Commit message for commit operations
            checkpoint_id: Optional checkpoint ID for state persistence

        Returns:
            Formatted workflow result with success/error status
        """,
    )

    logger.info("Git skill tools registered with MCP server")
