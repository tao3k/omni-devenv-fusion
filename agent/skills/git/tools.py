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

async def git_commit(message: str) -> str:
    """
    Execute git commit directly.

    Workflow (handled by prompts, not code):
    1. User says "commit"
    2. Claude sees {{git_status}} in context (from context injection)
    3. Claude generates conventional commit message
    4. Claude calls this tool
    5. User approves via Claude Desktop
    6. Tool executes

    Args:
        message: Conventional commit message (e.g., "feat(core): add feature")
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

    # Execute commit
    try:
        output = await run_git_cmd(["commit", "-m", message])
        return f"Commit Successful:\n{output}"
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
