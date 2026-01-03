"""
Git Skill Tools (Smart Analysis & Token Auth)

Restoring the classic 'Token Challenge' workflow.
"""
import subprocess
import secrets
import structlog
from typing import Dict
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd, get_git_status, get_git_diff, get_git_log

logger = structlog.get_logger(__name__)

# In-Memory Token Store
# Stores { "pending_token": "a1b2", "message": "feat: ..." }
_auth_context: Dict[str, str] = {}


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
    """Register Git tools with Smart Analysis."""

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
        Commit staged changes with Smart Analysis & Token Authorization.

        Workflow:
        1. Agent calls `smart_commit(message="...")` (no token).
        2. Tool returns "Smart Analysis" + "Auth Token: [abcd]".
        3. Agent/User reviews analysis.
        4. Agent calls `smart_commit(message="...", auth_token="abcd")`.
        5. Tool executes commit.

        Args:
            message: The commit message.
            auth_token: Authorization token. Leave empty for analysis.
        """
        global _auth_context

        # Clean input
        if ":" not in message:
            return "❌ Error: Commit message must follow 'type(scope): subject' format."

        # Check if this is a Confirmation Call
        stored_token = _auth_context.get("pending_token")

        if auth_token and stored_token:
            # Verify token
            if auth_token.strip().lower() == stored_token.lower():
                # Execute commit
                try:
                    output = await run_git_cmd(["commit", "-m", message])
                    _auth_context.clear()
                    logger.info("smart_commit.success", message=message[:50])
                    return f"✅ Commit Successful:\n{output}"
                except Exception as e:
                    return f"❌ Commit Failed: {str(e)}"
            else:
                return f"⛔️ Invalid Token. Expected: [{stored_token}], Got: [{auth_token}]"

        # No token provided (or new request) - Generate Smart Analysis
        new_token = secrets.token_hex(2)
        _auth_context["pending_token"] = new_token
        _auth_context["message"] = message

        # Run Smart Analysis (Diff Stat)
        try:
            stats = await run_git_cmd(["diff", "--cached", "--stat"])
            if not stats.strip():
                _auth_context.clear()
                return "⚠️ No staged changes to commit. Did you run `git_add`?"
        except:
            stats = "(Unable to generate stats)"

        return f"""
📊 **SMART ANALYSIS**
--------------------------------------------------
{stats.strip()}

📝 **Proposed Message**: "{message}"

🔐 **AUTHORIZATION REQUIRED**

To confirm this commit, please call this tool again with:

`auth_token="{new_token}"`

(Agent: Ask the user to confirm this action.)
"""

    logger.info("Git skill tools registered (Smart Analysis + Token Auth)")
