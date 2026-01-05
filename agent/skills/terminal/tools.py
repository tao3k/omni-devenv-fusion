"""
Terminal Skill Tools

Unified shell execution with safety audit.
"""

import asyncio
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP
from common.mcp_core import log_decision, SafeExecutor, check_dangerous_patterns, ProjectMemory
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Initialize project memory for flight recorder
_project_memory = None


def _get_project_memory():
    """Lazy initialization of project memory."""
    global _project_memory
    if _project_memory is None:
        _project_memory = ProjectMemory()
    return _project_memory


# =============================================================================
# Module-Level Functions (for skill() tool compatibility)
# =============================================================================


async def execute_command(command: str, timeout: int = 60) -> str:
    """
    Execute a shell command with whitelist validation.

    Args:
        command: The command string to execute (e.g., "uv sync", "just test").
        timeout: Maximum execution time in seconds (default: 60).
    """
    # Protocol Enforcement: Block direct git commit
    cmd_lower = command.lower()
    if "git commit" in cmd_lower:
        return (
            "PROHIBITED: Direct 'git commit' is disabled in Terminal.\n"
            "Use the 'git_commit' tool in the 'git' skill.\n"
            "Reason: Requires user confirmation via Claude Desktop."
        )

    # Parse command and args for security checks
    parts = command.strip().split()
    if not parts:
        return "Error: Empty command"

    cmd = parts[0]
    args = parts[1:]

    # Check dangerous patterns
    is_safe, error_msg = check_dangerous_patterns(command, args)
    if not is_safe:
        return f"Blocked: {error_msg}"

    # Execute using SafeExecutor (whitelist-based)
    result = await SafeExecutor.run(cmd, args, timeout=timeout)

    # Flight Recorder - auto-log execution
    cmd_str = f"{cmd} {' '.join(args)}" if args else cmd
    status_icon = "OK" if result.get("exit_code", -1) == 0 else "FAIL"

    log_content = f"[{status_icon}] {cmd_str}"
    if result.get("stdout"):
        preview = result["stdout"][:200].strip()
        if preview:
            log_content += f"\n  Out: {preview}"
    if result.get("stderr"):
        preview = result["stderr"][:200].strip()
        if preview:
            log_content += f"\n  Err: {preview}"

    try:
        pm = _get_project_memory()
        pm.log_scratchpad(log_content, source="Terminal")
    except Exception:
        pass  # Best effort logging

    return SafeExecutor.format_result(result, cmd, args)


async def run_task(command: str, args: Optional[list[str]] = None) -> str:
    """
    Run safe development tasks (just, nix, git) with FLIGHT RECORDER.

    All executions are automatically logged to .memory/active_context/SCRATCHPAD.md.

    Allowed commands:
    - just: validate, build, test, lint, fmt, test-basic, test-mcp, agent-commit
    - nix: fmt, build, shell, flake-check
    - git: status, diff, log, add, checkout, branch

    SECURITY: Git commit operations are BLOCKED. Use git_commit in git skill.
    """
    if args is None:
        args = []

    # GIT COMMIT BLOCKLIST - Prevents bypass of authorization protocol
    if command == "git" and args and "commit" in args:
        blocked_msg = """GIT COMMIT BLOCKED

This command was blocked because git commit operations MUST go through the git skill.

**Correct workflow:**
1. skill("git", "git_commit(message='feat(scope): description')")
2. System shows analysis
3. User confirms via Claude Desktop
4. Commit is executed

**Allowed git operations (non-committing):**
- git status, git diff, git log, git add, git checkout, git branch
"""
        log_decision(
            "run_task.blocked",
            {"command": command, "args": args, "reason": "git_commit_blocked"},
            logger,
        )
        return blocked_msg

    # Check bash command containing "git commit"
    if command == "bash" and args:
        full_cmd = " ".join(args) if isinstance(args, list) else str(args)
        if "git commit" in full_cmd:
            blocked_msg = """GIT COMMIT BLOCKED (via bash)

Running `git commit` through bash is FORBIDDEN.

Use git_commit in git skill instead.
"""
            log_decision(
                "run_task.blocked",
                {"command": command, "reason": "bash_git_commit_blocked"},
                logger,
            )
            return blocked_msg

    # Execute command
    log_decision("run_task.request", {"command": command, "args": args}, logger)
    result = await SafeExecutor.run(command=command, args=args)
    formatted_output = SafeExecutor.format_result(result, command, args)

    # Flight Recorder
    cmd_str = f"{command} {' '.join(args)}"
    status_icon = "OK" if result.get("exit_code", -1) == 0 else "FAIL"

    log_content = f"[{status_icon}] {cmd_str}"
    if result.get("stdout"):
        preview = result["stdout"][:300].strip()
        if preview:
            log_content += f"\n  Out: {preview}"
    if result.get("stderr"):
        preview = result["stderr"][:300].strip()
        if preview:
            log_content += f"\n  Err: {preview}"

    try:
        pm = _get_project_memory()
        pm.log_scratchpad(log_content, source="run_task")
    except Exception:
        pass

    return formatted_output


async def analyze_last_error() -> str:
    """
    [Debug Tool] Deeply analyzes the LAST failed command in the Flight Recorder.

    Use this when the error log in manage_context("read") is truncated or unclear.
    It retrieves the full stderr/stdout and asks the AI to pinpoint the root cause.
    """
    try:
        pm = _get_project_memory()
        scratchpad_path = pm.active_dir / "SCRATCHPAD.md"
        if not scratchpad_path.exists():
            return "No crash logs found."

        content = scratchpad_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Take last 50 lines for crash analysis
        recent_log = "\n".join(lines[-50:])

        return f"""--- Crash Analysis Context ---

The following is the raw log of the recent crash.
Please analyze it to find:
1. The specific error message.
2. The file and line number causing it.
3. A suggested fix.

--- LOG START ---
{recent_log}
--- LOG END ---
"""
    except Exception as e:
        return f"Error reading crash logs: {e}"


async def inspect_environment() -> str:
    """Check the current execution environment."""
    import os
    import platform

    return f"OS: {platform.system()}, CWD: {os.getcwd()}"


# =============================================================================
# Registration
# =============================================================================


def register(mcp: FastMCP):
    """Register Terminal tools using direct function binding."""
    import sys
    import types

    # Get the current module from sys.modules (loaded by _load_module_from_path)
    current_module = sys.modules.get("agent.skills.terminal.tools")
    if current_module is None:
        # Fallback: load module directly from file
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "agent.skills.terminal.tools", Path(__file__).resolve()
        )
        current_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(current_module)
        sys.modules["agent.skills.terminal.tools"] = current_module

    # Get functions from the module
    exec_cmd = getattr(current_module, "execute_command", None)
    run_tsk = getattr(current_module, "run_task", None)
    analyze_err = getattr(current_module, "analyze_last_error", None)
    inspect_env = getattr(current_module, "inspect_environment", None)

    # Register tools
    if exec_cmd:
        mcp.add_tool(exec_cmd, "Execute a shell command with whitelist validation.")
    if run_tsk:
        mcp.add_tool(
            run_tsk,
            "Run safe development tasks (just, nix, git) with FLIGHT RECORDER. "
            "Git commit is BLOCKED - use git_commit in git skill.",
        )
    if analyze_err:
        mcp.add_tool(
            analyze_err,
            "[Debug Tool] Analyze the last failed command in Flight Recorder.",
        )
    if inspect_env:
        mcp.add_tool(inspect_env, "Check the current execution environment (read-only, safe).")

    logger.info("Terminal skill tools registered")
