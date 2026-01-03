"""
src/agent/skills/git/tools.py
Git Skill Tools (Smart Commit with Session-based Authorization)
"""
import subprocess
import secrets
import json
from datetime import datetime
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd, get_git_status, get_git_diff, get_git_log
import structlog

logger = structlog.get_logger(__name__)

# Session-based Workflow State
# Stores { "session_id": { "status": "pending", "context": "...", "message": "..." } }
_commit_sessions: Dict[str, Dict[str, Any]] = {}


async def get_git_status() -> str:
    """Get the current git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"

        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        if not lines or lines == ['']:
            return "Working tree is clean"

        staged = []
        unstaged = []
        untracked = []

        for line in lines:
            if not line.strip():
                continue
            status = line[:2]
            filename = line[3:]
            if status.startswith('A') or status.startswith('M') and line[2] == ' ':
                staged.append(filename)
            elif status.startswith(' M'):
                unstaged.append(filename)
            elif status == '??':
                untracked.append(filename)
            else:
                unstaged.append(filename)

        output = ["Git Status"]
        if staged:
            output.append(f"\nStaged ({len(staged)}):")
            for f in staged:
                output.append(f"  {f}")
        if unstaged:
            output.append(f"\nUnstaged ({len(unstaged)}):")
            for f in unstaged:
                output.append(f"  {f}")
        if untracked:
            output.append(f"\nUntracked ({len(untracked)}):")
            for f in untracked:
                output.append(f"  {f}")
        return '\n'.join(output)
    except Exception as e:
        return f"Error getting status: {str(e)}"


async def get_git_diff(staged: bool = True) -> str:
    """Get the diff of staged or unstaged changes."""
    try:
        if staged:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True
            )
            title = "Staged Changes (to be committed)"
        else:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True
            )
            title = "Unstaged Changes (work in progress)"

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        if not result.stdout.strip():
            return f"No {title.lower()}"

        return f"{title}\n\n{result.stdout}"
    except Exception as e:
        return f"Error getting diff: {str(e)}"


async def get_git_log(n: int = 5) -> str:
    """Show recent commit history."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", "-n", str(n)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"

        commits = result.stdout.strip().split('\n')
        output = f"Recent Commits (last {n}):\n\n"
        for commit in commits:
            output += f"  {commit}\n"
        return output
    except Exception as e:
        return f"Error getting log: {str(e)}"


def register(mcp: FastMCP):
    """Register Git tools with Smart Commit V2 Engine."""

    @mcp.tool()
    async def git_status() -> str:
        """Get the current git status (staged, unstaged, and untracked files)."""
        return await get_git_status()

    @mcp.tool()
    async def git_diff_staged() -> str:
        """Get the diff of staged changes (what will be committed)."""
        return await get_git_diff(staged=True)

    @mcp.tool()
    async def git_diff_unstaged() -> str:
        """Get the diff of unstaged changes (work in progress)."""
        return await get_git_diff(staged=False)

    @mcp.tool()
    async def git_log(n: int = 5) -> str:
        """Show the recent commit history."""
        return await get_git_log(n)

    @mcp.tool()
    async def git_add(files: list[str]) -> str:
        """Stage files for commit."""
        try:
            await run_git_cmd(["add"] + files)
            return f"✅ Staged {len(files)} files."
        except Exception as e:
            return f"❌ Failed to stage files: {str(e)}"

    @mcp.tool()
    async def smart_commit(message: str, auth_token: str = "") -> str:
        """
        Commit staged changes with Smart Analysis & Session Authorization.

        Workflow:
        1. Agent calls `smart_commit(message="...")`.
        2. System generates a Session ID and returns analysis.
        3. User/Agent reviews.
        4. Agent calls `smart_commit(message="...", auth_token="SESSION_ID")` to execute.

        Args:
            message: The commit message.
            auth_token: The Session ID provided in the analysis step.
        """
        global _commit_sessions

        # Clean input
        if ":" not in message:
            return "❌ Error: Commit message must follow 'type(scope): subject' format."

        # 1️⃣ EXECUTE PHASE (If token provided)
        if auth_token:
            session = _commit_sessions.get(auth_token)

            # Validation
            if not session:
                return f"⛔️ Invalid or Expired Session Token: {auth_token}. Please start over."

            if session["message"] != message:
                return f"⚠️ Message Mismatch. Session expects: '{session['message']}'"

            # Execute
            try:
                output = await run_git_cmd(["commit", "-m", message])
                # Cleanup session on success
                _commit_sessions.pop(auth_token, None)
                logger.info("smart_commit.success", message=message[:50])
                return f"✅ Commit Successful (Session {auth_token[:6]}):\n{output}"
            except Exception as e:
                return f"❌ Commit Failed: {str(e)}"

        # 2️⃣ ANALYSIS PHASE (Start New Session)

        # Generate Session ID (Acts as the Token)
        session_id = secrets.token_hex(4)  # e.g. "8f2a9c1d"
        timestamp = datetime.now().isoformat()

        # Create Session State
        _commit_sessions[session_id] = {
            "status": "pending_auth",
            "message": message,
            "timestamp": timestamp
        }

        # Generate Analysis
        try:
            stats = await run_git_cmd(["diff", "--cached", "--stat"])
            if not stats.strip():
                _commit_sessions.pop(session_id, None)
                return "⚠️ No staged changes to commit. Did you run `git_add`?"
        except:
            stats = "(Unable to generate stats)"

        # Return Analysis with Session Authorization
        return f"""
📊 **SMART ANALYSIS**
--------------------------------------------------
{stats.strip()}

📝 **Proposed Message**: "{message}"

🔐 **AUTHORIZATION REQUIRED**
Session ID: `{session_id}`

To confirm, call this tool again with:
`auth_token="{session_id}"`

(Agent: Ask the user to confirm using this token.)
"""

    logger.info("Git skill tools registered (Smart Commit with Session Authorization)")
