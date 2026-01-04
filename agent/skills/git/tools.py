"""
agent/skills/git/tools.py
Git Skill: Atomic Git Operations

Phase 13.10: Executor Mode - Pure tool, no workflow logic.

This module provides atomic git operations. The workflow logic is handled
by prompts (Brain), not by Python code (Hands).
"""
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd, get_git_status, get_git_diff, get_git_log


# =============================================================================
# Atomic Git Tools (Hands)
# =============================================================================

async def git_status() -> str:
    """Get git status."""
    return await get_git_status()


async def git_diff_staged() -> str:
    """Get diff of staged changes."""
    diff = await get_git_diff(staged=True)
    if len(diff) > 20000:
        stats = await run_git_cmd(["diff", "--cached", "--stat"])
        return f"--- Diff too large (truncated) ---\n{stats}\n\nTotal: {len(diff)} bytes"
    return diff


async def git_diff_unstaged() -> str:
    """Get diff of unstaged changes."""
    diff = await get_git_diff(staged=False)
    if len(diff) > 20000:
        stats = await run_git_cmd(["diff", "--stat"])
        return f"--- Diff too large (truncated) ---\n{stats}\n\nTotal: {len(diff)} bytes"
    return diff


async def git_log(n: int = 5) -> str:
    """Get recent commit history."""
    return await get_git_log(n)


async def git_add(files: list[str]) -> str:
    """Stage files for commit."""
    try:
        await run_git_cmd(["add"] + files)
        return f"Staged {len(files)} files."
    except Exception as e:
        return f"Failed to stage files: {e}"


async def git_commit(message: str) -> str:
    """
    Execute git commit directly.

    Workflow (handled by prompts, not code):
    1. User says "commit"
    2. Claude sees {{git_status}} in context
    3. Claude generates conventional commit message
    4. Claude calls this tool directly
    5. User approves via Claude Desktop

    Args:
        message: Conventional commit message (e.g., "feat(core): add feature")
    """
    if ":" not in message:
        return "Error: Message must follow 'type(scope): subject' format."

    # Check for staged changes
    try:
        stat = await run_git_cmd(["diff", "--cached", "--stat"])
        if not stat.strip():
            return "Error: No staged changes. Stage first with git_add."
    except Exception as e:
        return f"Error checking staged changes: {e}"

    # Execute commit
    try:
        output = await run_git_cmd(["commit", "-m", message])
        return f"Commit Successful:\n{output}"
    except Exception as e:
        return f"Commit Failed: {e}"


# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register all Git tools."""
    mcp.tool()(git_status)
    mcp.tool()(git_diff_staged)
    mcp.tool()(git_diff_unstaged)
    mcp.tool()(git_log)
    mcp.tool()(git_add)
    mcp.tool()(git_commit)
