"""
agent/skills/git/tools.py
Git Skill - Complete Git Operations for Version Control.

Phase 23: The Skill Singularity
Migrated from common/mcp_core/gitops.py to achieve complete skill independence.

This module provides all Git capabilities required by the agent:
- Status, diff, log operations (read-only)
- Add, commit, branch, stash operations (write)
- Error handling and safe defaults

Usage:
    from agent.skills.git.tools import git_status, git_commit

    result = git_status(short=True)
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Optional
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
# Read Operations (Safe - No Side Effects)
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
        from agent.skills.git.workflow import run_git_workflow, format_workflow_result

        result = await run_git_workflow(
            intent=intent,
            target_branch=target_branch,
            commit_message=commit_message,
            checkpoint_id=checkpoint_id,
        )

        return format_workflow_result(result)
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
    mcp.add_tool(git_status, "Get the current status of the git repository.")
    mcp.add_tool(git_diff, "Get the diff of changes.")
    mcp.add_tool(git_log, "Show recent commit logs.")
    mcp.add_tool(git_branch, "List all git branches.")
    mcp.add_tool(git_show, "Show file content at a specific commit.")
    mcp.add_tool(git_remote, "Show remote repositories.")
    mcp.add_tool(git_tag_list, "List all tags.")

    # Write operations (require caution)
    mcp.add_tool(git_add, "Stage files for commit.")
    mcp.add_tool(git_stage_all, "Stage all changes with optional security scan.")
    mcp.add_tool(git_commit, "Commit staged changes.")
    mcp.add_tool(git_checkout, "Switch to a branch or create a new one.")
    mcp.add_tool(git_stash_save, "Stash changes in the working directory.")
    mcp.add_tool(git_stash_pop, "Apply the last stashed changes.")
    mcp.add_tool(git_stash_list, "List all stashed changes.")
    mcp.add_tool(git_reset, "Reset current HEAD to a specific state.")
    mcp.add_tool(git_revert, "Revert a specific commit.")

    # Advanced operations
    mcp.add_tool(git_tag_create, "Create an annotated tag.")
    mcp.add_tool(git_merge, "Merge a branch into current branch.")
    mcp.add_tool(git_submodule_update, "Update submodules.")

    # Phase 24: Living Skill Architecture - Workflow tools
    mcp.add_tool(
        invoke_git_workflow,
        """Invoke Git workflow with LangGraph orchestration.

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
