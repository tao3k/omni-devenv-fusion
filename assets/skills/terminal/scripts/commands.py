"""
terminal/scripts/commands.py - Terminal Skill Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import os
import platform
from pathlib import Path
from typing import Optional

from agent.skills.decorators import skill_script


def _is_git_commit_blocked(command: str, args: list[str]) -> tuple[bool, str]:
    """Check if command is a blocked git commit operation."""
    cmd_lower = command.lower()

    if "git commit" in cmd_lower:
        return True, (
            "PROHIBITED: Direct 'git commit' is disabled in Terminal.\n"
            "Use the 'git_commit' tool in the 'git' skill.\n"
            "Reason: Requires user confirmation via Claude Desktop."
        )

    if command == "git" and args and "commit" in args:
        return (
            True,
            """GIT COMMIT BLOCKED

This command was blocked because git commit operations MUST go through the git skill.

**Correct workflow:**
1. omni_run("git", "git_commit", {"message": "feat(scope): description"})
2. System shows analysis
3. User confirms via Claude Desktop
4. Commit is executed

**Allowed git operations (non-committing):**
- git status, git diff, git log, git add, git checkout, git branch
""",
        )

    if command == "bash" and args:
        full_cmd = " ".join(args) if isinstance(args, list) else str(args)
        if "git commit" in full_cmd:
            return (
                True,
                """GIT COMMIT BLOCKED (via bash)

Running `git commit` through bash is FORBIDDEN.

Use git_commit in git skill instead.
""",
            )

    return False, ""


@skill_script(
    name="run_task",
    category="workflow",
    description="""
    Runs safe development tasks (just, nix, git) with FLIGHT RECORDER.

    FLIGHT RECORDER captures command execution for debugging and audit trails.

    Args:
        command: The command to run (e.g., `git`, `just`, `nix`).
        args: Optional list of arguments. Defaults to empty list.
              Can also be a single string like `"status"` which gets parsed.
        inject_root: Auto-inject project root directory.

    Returns:
        Command output with execution status and timing.

    Example:
        @omni("terminal.run_task", {"command": "git", "args": ["status"]})
        @omni("terminal.run_task", {"command": "just validate"})
    """,
    inject_root=True,
)
async def run_task(command: str, args: Optional[list[str]] = None, **kwargs) -> str:
    if args is None:
        args = []

    if (
        args
        and isinstance(args, list)
        and len(args) == 1
        and isinstance(args[0], str)
        and " " in args[0]
    ):
        parts = args[0].split()
        command = parts[0]
        args = parts[1:]
    elif " " in command:
        parts = command.split()
        command = parts[0]
        extra_args = parts[1:]
        if extra_args:
            args = extra_args + args

    blocked, msg = _is_git_commit_blocked(command, args)
    if blocked:
        return msg

    from agent.skills.terminal.scripts import engine

    result = engine.run_command(command, args, timeout=60)
    return engine.format_result(result, command, args)


@skill_script(
    name="analyze_last_error",
    category="view",
    description="""
    [Debug Tool] Analyzes the last failed command in Flight Recorder.

    Reads crash logs from SCRATCHPAD.md and provides analysis context
    for debugging purposes.

    Args:
        None

    Returns:
        Formatted log analysis with error message, file/line number,
        and suggested fix.
    """,
)
async def analyze_last_error() -> str:
    try:
        from common.mcp_core.memory import ProjectMemory

        pm = ProjectMemory()
        scratchpad_path = pm.active_dir / "SCRATCHPAD.md"
        if not scratchpad_path.exists():
            return "No crash logs found."

        content = scratchpad_path.read_text(encoding="utf-8")
        lines = content.split("\n")
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


@skill_script(
    name="inspect_environment",
    category="read",
    description="""
    Checks the current execution environment.

    Returns system information including OS and current working directory.

    Args:
        None

    Returns:
        Formatted string with OS type and CWD.
    """,
)
async def inspect_environment() -> str:
    return f"OS: {platform.system()}, CWD: {os.getcwd()}"


@skill_script(
    name="run_command",
    category="workflow",
    description="""
    Runs a shell command and returns stdout/stderr.

    Use this for general-purpose command execution.

    Args:
        command: The command to execute (e.g., `ls`, `cat`, `echo`).
        args: Optional list of arguments. Can be a single string.
        timeout: Command timeout in seconds. Defaults to `60`.

    Returns:
        Command stdout and stderr output.

    Example:
        @omni("terminal.run_command", {"command": "git", "args": ["status"]})
        @omni("terminal.run_command", {"command": "ls -la"})
    """,
    inject_root=True,
)
async def run_command(command: str, args: Optional[list[str]] = None, timeout: int = 60) -> str:
    if args is None:
        args = []

    if " " in command:
        parts = command.split()
        command = parts[0]
        extra_args = parts[1:]
        if extra_args:
            args = extra_args + args

    from agent.skills.terminal.scripts import engine

    result = engine.run_command(command, args, timeout=timeout)
    return engine.format_result(result, command, args)
