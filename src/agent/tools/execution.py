# agent/tools/execution.py
"""
Execution Tools

Provides task execution and debugging tools.

Tools:
- run_task: Run safe development tasks
- analyze_last_error: Debug tool for error analysis
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP
from common.mcp_core import (
    log_decision,
    SafeExecutor,
    ProjectMemory,
)
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Initialize project memory
project_memory = ProjectMemory()


def register_execution_tools(mcp: FastMCP) -> None:
    """Register all execution tools."""

    @mcp.tool()
    async def run_task(command: str, args: Optional[List[str]] = None) -> str:
        """
        Run safe development tasks (just, nix, git) with FLIGHT RECORDER.

        All executions are automatically logged to .memory/active_context/SCRATCHPAD.md
        so you don't lose track of error messages.

        Allowed commands:
        - just: validate, build, test, lint, fmt, test-basic, test-mcp, agent-commit
        - nix: fmt, build, shell, flake-check
        - git: status, diff, log, add, checkout, branch

        SECURITY: Git commit operations are BLOCKED. Use @omni-orchestrator smart_commit instead.
        """
        if args is None:
            args = []

        # GIT COMMIT BLOCKLIST - Prevents bypass of authorization protocol
        # This check prevents agents from bypassing smart_commit() authorization
        # by using run_task to execute git commit directly.

        # Check 1: Direct git commit command
        if command == "git" and args and "commit" in args:
            blocked_msg = """🚫 GIT COMMIT BLOCKED

This command was blocked because git commit operations MUST go through the authorization protocol.

**Why this is blocked:**
- Agents must use @omni-orchestrator smart_commit() for commit validation
- Authorization requires user to say "run just agent-commit"
- Direct git commit bypasses pre-commit hooks and authorization

**Correct workflow:**
1. @omni-orchestrator smart_commit(type="feat", scope="mcp", message="description")
2. System returns: {authorization_required: true, auth_token: "..."}
3. Ask user: "Please say: run just agent-commit"
4. @omni-orchestrator execute_authorized_commit(auth_token="xxx")

**Allowed git operations (non-committing):**
- git status, git diff, git log, git add, git checkout, git branch
"""
            log_decision("run_task.blocked", {"command": command, "args": args, "reason": "git_commit_blocked"}, logger)
            return blocked_msg

        # Check 2: bash command containing "git commit"
        if command == "bash" and args:
            full_cmd = " ".join(args) if isinstance(args, list) else str(args)
            if "git commit" in full_cmd:
                blocked_msg = """🚫 GIT COMMIT BLOCKED (via bash)

Running `git commit` through bash is FORBIDDEN.

**Use the authorized commit path instead:**
1. @omni-orchestrator smart_commit(type="...", scope="...", message="...")
2. Wait for authorization token
3. @omni-orchestrator execute_authorized_commit(auth_token="...")

**This is a protocol violation if you intentionally wrote this.**
"""
                log_decision("run_task.blocked", {"command": command, "reason": "bash_git_commit_blocked"}, logger)
                return blocked_msg

        # Execute command
        log_decision("run_task.request", {"command": command, "args": args}, logger)
        result = await SafeExecutor.run(command=command, args=args)
        formatted_output = SafeExecutor.format_result(result, command, args)

        # Flight Recorder - auto-log execution
        cmd_str = f"{command} {' '.join(args)}"
        status_icon = "✅" if result.get("exit_code", -1) == 0 else "❌"

        log_content = f"{status_icon} `{cmd_str}`"
        if result.get("stdout"):
            stdout_preview = result["stdout"][:300].strip()
            if stdout_preview:
                log_content += f"\n  Out: {stdout_preview}"
        if result.get("stderr"):
            stderr_preview = result["stderr"][:300].strip()
            if stderr_preview:
                log_content += f"\n  Err: {stderr_preview}"

        # Write to background memory
        project_memory.log_scratchpad(log_content, source="System")

        return formatted_output

    @mcp.tool()
    async def analyze_last_error() -> str:
        """
        [Debug Tool] Deeply analyzes the LAST failed command in the Flight Recorder.

        Use this when the error log in `manage_context("read")` is truncated or unclear.
        It retrieves the full stderr/stdout and asks the AI to pinpoint the root cause.
        """
        # Read the scratchpad's last 50 lines (usually contains full error stack)
        scratchpad_path = project_memory.active_dir / "SCRATCHPAD.md"
        if not scratchpad_path.exists():
            return "No crash logs found."

        content = scratchpad_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Take last 50 lines for crash analysis
        recent_log = "\n".join(lines[-50:])

        return f"""--- 🕵️‍♀️ Crash Analysis Context ---

The following is the raw log of the recent crash.
Please analyze it to find:
1. The specific error message.
2. The file and line number causing it.
3. A suggested fix.

--- LOG START ---
{recent_log}
--- LOG END ---
"""

    log_decision("execution_tools.registered", {}, logger)
