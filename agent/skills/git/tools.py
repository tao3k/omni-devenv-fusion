"""
agent/skills/git/tools.py
Git Skill: Critical Operations Only

Phase 13.10: Executor Mode - MCP handles dangerous operations.

This module provides only critical git operations (commit, push).
Safe operations (status, diff, log, add) should be done via Claude's native bash.

Philosophy:
- MCP = "The Guard" - handles operations that need explicit confirmation
- Claude-native bash = "The Explorer" - safe read operations
"""
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd


# =============================================================================
# Critical Git Tools (Require explicit confirmation)
# =============================================================================

async def git_commit(message: str, skip_hooks: bool = False) -> str:
    """
    Execute git commit directly.

    ⚠️ AUTHORIZATION PROTOCOL (MUST FOLLOW):
    1. BEFORE calling this tool: Show Commit Analysis to user
       - Type: feat/fix/docs/style/refactor/test/chore
       - Scope: git-ops/cli/docs/mcp/router/...
       - Message: describe change
    2. Wait for user to say "yes" or "confirm"
    3. ONLY then call this tool

    ❌ NEVER call this tool without showing analysis first
    ❌ Direct 'git commit' is PROHIBITED - use this tool

    Args:
        message: Conventional commit message (e.g., "feat(core): add feature")
        skip_hooks: If True, skip pre-commit and commit-msg hooks (--no-verify)
    """
    if ":" not in message:
        return "Error: Message must follow 'type(scope): subject' format."

    # Check for staged changes
    try:
        stat = await run_git_cmd(["diff", "--cached", "--stat"])
        if not stat.strip():
            return "Error: No staged changes. Stage first with 'git add' via bash."
    except Exception as e:
        return f"Error checking staged changes: {e}"

    # Build commit command
    cmd = ["commit", "-m", message]
    if skip_hooks:
        cmd.insert(1, "--no-verify")  # Add --no-verify flag

    # Execute commit
    try:
        output = await run_git_cmd(cmd)
        hook_note = " (hooks skipped)" if skip_hooks else ""
        return f"Commit Successful{hook_note}:\n{output}"
    except Exception as e:
        return f"Commit Failed: {e}"


async def git_push() -> str:
    """
    Execute git push to remote.

    Use this after successful commit to push changes.

    Note: For first push of a new branch, use 'git push -u origin branch_name' via bash.
    """
    try:
        output = await run_git_cmd(["push"])
        return f"Push Successful:\n{output}"
    except Exception as e:
        return f"Push Failed: {e}\n\nTip: For new branches, use: git push -u origin <branch>"


# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register critical Git tools only."""
    mcp.tool()(git_commit)
    mcp.tool()(git_push)
