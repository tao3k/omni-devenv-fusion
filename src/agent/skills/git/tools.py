"""
src/agent/skills/git/tools.py
Git Skill: The Unified Version Control System
Combines Low-level Ops (Git), Safety (Smart Commit V2), and Intelligence (Spec-Aware).
"""
import os
import subprocess
import secrets
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd, get_git_status, get_git_diff, get_git_log
import structlog

logger = structlog.get_logger(__name__)

# Session Storage for Smart Commit V2
_commit_sessions: Dict[str, Dict[str, Any]] = {}

# Token file path for just agent-commit compatibility
TOKEN_FILE = Path("/tmp/.omni_commit_token")

def register(mcp: FastMCP):
    """Register All Git Tools (Ops + Intelligence)."""

    # --- 1. Basic Git Operations ---
    @mcp.tool()
    async def git_status() -> str:
        return await get_git_status()

    @mcp.tool()
    async def git_diff_staged() -> str:
        return await get_git_diff(staged=True)

    @mcp.tool()
    async def git_diff_unstaged() -> str:
        return await get_git_diff(staged=False)

    @mcp.tool()
    async def git_log(n: int = 5) -> str:
        return await get_git_log(n)

    @mcp.tool()
    async def git_add(files: list[str]) -> str:
        try:
            await run_git_cmd(["add"] + files)
            return f"Staged {len(files)} files."
        except Exception as e:
            return f"Failed to stage files: {str(e)}"

    # --- 2. Intelligence: Spec-Aware Commit (The Writer) ---
    @mcp.tool()
    async def spec_aware_commit(context: str) -> str:
        """
        Generate a Conventional Commit message using AI.

        Args:
            context: Description of changes (e.g. "implemented auth v2").
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

    # --- 3. Safety: Smart Commit V2 (The Gatekeeper) ---
    @mcp.tool()
    async def smart_commit(message: str, auth_token: str = "") -> str:
        """
        Commit staged changes using Smart Workflow V2 (Session-based).

        Workflow:
        1. Call without auth_token to create session and get analysis
        2. User says "run just agent-commit" to authorize
        3. just agent-commit reads token file and executes commit
        """
        global _commit_sessions

        # EXECUTE PHASE (called by just agent-commit)
        if auth_token:
            session = _commit_sessions.get(auth_token)
            if not session:
                return f"Invalid or Expired Session Token: {auth_token}"
            if session["message"] != message:
                return f"Message Mismatch. Session expects: '{session['message']}'"

            try:
                output = await run_git_cmd(["commit", "-m", message])
                _commit_sessions.pop(auth_token, None)
                # Clean up token file
                TOKEN_FILE.unlink(missing_ok=True)
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

        # Write token file for just agent-commit compatibility
        # Format: session_id:token:timestamp:message
        token_content = f"{session_id}:{session_id}:{timestamp}:{message}"
        try:
            TOKEN_FILE.write_text(token_content, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to write token file", error=str(e))

        try:
            stats = await run_git_cmd(["diff", "--cached", "--stat"])
            if not stats.strip():
                _commit_sessions.pop(session_id, None)
                TOKEN_FILE.unlink(missing_ok=True)
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

To authorize, say exactly: "run just agent-commit"
"""
