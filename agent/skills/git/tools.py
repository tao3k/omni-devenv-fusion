"""
agent/skills/git/tools.py
Git Skill: The Unified Version Control System
Combines Low-level Ops (Git), Safety (Smart Commit V2), and Intelligence (Spec-Aware).
"""
import secrets
import json
from datetime import datetime
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd, get_git_status, get_git_diff, get_git_log
import structlog

logger = structlog.get_logger(__name__)

# Session Storage for Smart Commit V2
_commit_sessions: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# Module-Level Tool Definitions (Accessible via 'skill' proxy & 'getattr')
# =============================================================================

async def git_status() -> str:
    return await get_git_status()

async def git_diff_staged() -> str:
    """
    Get diff of staged changes. Returns summary if too large.
    MCP tool response limit is ~100KB, so we truncate proactively.
    """
    diff = await get_git_diff(staged=True)
    # Return summary if too large (avoid MCP client file save)
    if len(diff) > 20000:
        stats = await run_git_cmd(["diff", "--cached", "--stat"])
        return f"--- Diff too large (truncated) ---\n{stats}\n\nTotal changes: {len(diff)} bytes\nUse terminal to view full diff: git diff --cached"
    return diff

async def git_diff_unstaged() -> str:
    """
    Get diff of unstaged changes. Returns summary if too large.
    """
    diff = await get_git_diff(staged=False)
    # Return summary if too large
    if len(diff) > 20000:
        stats = await run_git_cmd(["diff", "--stat"])
        return f"--- Diff too large (truncated) ---\n{stats}\n\nTotal changes: {len(diff)} bytes\nUse terminal to view full diff: git diff"
    return diff

async def git_log(n: int = 5) -> str:
    return await get_git_log(n)

async def git_add(files: list[str]) -> str:
    try:
        await run_git_cmd(["add"] + files)
        return f"Staged {len(files)} files."
    except Exception as e:
        return f"Failed to stage files: {str(e)}"

async def spec_aware_commit(context: str) -> str:
    """
    Generate a Conventional Commit message using AI.
    """
    try:
        from common.mcp_core.inference import InferenceClient
        client = InferenceClient()

        prompt = f"""Generate a Conventional Commit message for:

{context}

Format: <type>(<scope>): <description>
Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Scope: mcp, router, cli, docs, nix, deps

Return ONLY the commit message, no explanation."""

        result = await client.complete(
            system_prompt="You are an expert technical writer.",
            user_query=prompt,
            max_tokens=100
        )

        if result["success"]:
            msg = result["content"].strip()
            return json.dumps({
                "status": "success", 
                "commit_message": msg,
                "message": f"Generated: {msg}\n\nNext: Call `smart_commit` to execute."
            }, indent=2)
        else:
            return f"Generation Failed: {result.get('error')}"

    except Exception as e:
        return f"Error: {str(e)}"

async def smart_commit(message: str, auth_token: str = "") -> str:
    """
    Commit staged changes using Smart Workflow V2 (Session-based).
    """
    global _commit_sessions

    # EXECUTE PHASE
    if auth_token:
        session = _commit_sessions.get(auth_token)
        if not session:
            return f"Invalid or Expired Session Token: {auth_token}"
        if session["message"] != message:
            return f"Message Mismatch. Session expects: '{session['message']}'"

        try:
            output = await run_git_cmd(["commit", "-m", message])
            _commit_sessions.pop(auth_token, None)
            return f"Commit Successful (Session {auth_token[:6]}):\n{output}"
        except Exception as e:
            return f"Commit Failed: {str(e)}"

    # ANALYSIS PHASE
    if ":" not in message:
        return "Error: Commit message must follow 'type(scope): subject' format."

    session_id = secrets.token_hex(4)
    timestamp = datetime.now().isoformat()
    _commit_sessions[session_id] = {
        "status": "pending_auth", "message": message, "timestamp": timestamp
    }
    
    try:
        stats = await run_git_cmd(["diff", "--cached", "--stat"])
        if not stats.strip():
            _commit_sessions.pop(session_id, None)
            return "No staged changes. Did you run `git_add`?"
    except:
        stats = "(Unable to generate stats)"

    return f"""
SMART COMMIT ANALYSIS
--------------------------------------------------
{stats.strip()}

Proposed Message: "{message}"

AUTHORIZATION REQUIRED
Session ID: `{session_id}`

To authorize, call this tool again with:
`auth_token="{session_id}"`
"""

# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register All Git Tools from Module Scope."""
    mcp.tool()(git_status)
    mcp.tool()(git_diff_staged)
    mcp.tool()(git_diff_unstaged)
    mcp.tool()(git_log)
    mcp.tool()(git_add)
    mcp.tool()(spec_aware_commit)
    mcp.tool()(smart_commit)
