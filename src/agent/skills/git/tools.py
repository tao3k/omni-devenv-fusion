"""
Git Skill Tools
Refactored from src/mcp_server/executor/git_ops.py
"""
import subprocess
from typing import Dict, List
from mcp.server.fastmcp import FastMCP
import structlog

logger = structlog.get_logger(__name__)


async def run_git_cmd(args: List[str]) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or "OK"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"


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
            return "✅ Working tree is clean"

        # Categorize
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

        output = "📍 Git Status\n"
        if staged:
            output += f"\n✅ Staged ({len(staged)}):\n" + '\n'.join(f"  {f}" for f in staged)
        if unstaged:
            output += f"\n📝 Unstaged ({len(unstaged)}):\n" + '\n'.join(f"  {f}" for f in unstaged)
        if untracked:
            output += f"\n❓ Untracked ({len(untracked)}):\n" + '\n'.join(f"  {f}" for f in untracked)
        return output
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
            return f"✅ No {title.lower()}"

        output = f"--- {title} ---\n\n{result.stdout}"
        return output
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
        output = f"📜 Recent Commits (last {n}):\n\n"
        for commit in commits:
            output += f"  {commit}\n"
        return output
    except Exception as e:
        return f"Error getting log: {str(e)}"


def register(mcp: FastMCP):
    """Register Git tools with the MCP server."""

    @mcp.tool()
    async def git_status() -> str:
        """
        Get the current git status (staged, unstaged, and untracked files).
        Use this to check what files have been changed.
        """
        return await get_git_status()

    @mcp.tool()
    async def git_diff_staged() -> str:
        """
        Get the diff of staged changes (what will be committed).
        ALWAYS call this before smart_commit to verify your work.
        """
        return await get_git_diff(staged=True)

    @mcp.tool()
    async def git_diff_unstaged() -> str:
        """
        Get the diff of unstaged changes (work in progress).
        """
        return await get_git_diff(staged=False)

    @mcp.tool()
    async def git_log(n: int = 5) -> str:
        """
        Show the recent commit history.
        Args:
            n: Number of commits to show (default: 5)
        """
        return await get_git_log(n)

    @mcp.tool()
    async def smart_commit(message: str) -> str:
        """
        [Protocol Enforced] Commit staged changes with a conventional message.

        This tool will:
        1. Validates the commit message format.
        2. Runs pre-commit checks (if configured).
        3. Executes the commit.

        Args:
            message: The conventional commit message (e.g., 'feat(auth): add login').
        """
        # Simple validation
        if ":" not in message:
            return "❌ Error: Commit message must follow 'type(scope): subject' format."

        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return f"❌ Commit Failed: {result.stderr}"
            return f"✅ Commit Successful:\n{result.stdout or 'Committed successfully'}"
        except Exception as e:
            logger.error("Smart commit failed", error=str(e))
            return f"❌ Commit Failed: {str(e)}"

    @mcp.tool()
    async def git_add(files: list[str]) -> str:
        """
        Stage files for commit.
        Args:
            files: List of file paths to add (or ["."] for all).
        """
        try:
            await run_git_cmd(["add"] + files)
            return f"✅ Staged {len(files)} files."
        except Exception as e:
            return f"❌ Failed to stage files: {str(e)}"
