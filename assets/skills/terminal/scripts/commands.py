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
    description="Run safe development tasks (just, nix, git) with FLIGHT RECORDER.",
    inject_root=True,
)
async def run_task(command: str, args: Optional[list[str]] = None, **kwargs) -> str:
    """
    Run safe development tasks (just, nix, git) with FLIGHT RECORDER.

    Usage:
    - run_task(command="git", args=["status"])
    - run_task(command="git status")
    """
    if args is None:
        args = []

    # Handle args=["git status"] case - legacy format
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
    # Always parse command string if it contains spaces
    elif " " in command:
        parts = command.split()
        command = parts[0]
        extra_args = parts[1:]
        if extra_args:
            args = extra_args + args

    # Check git commit block
    blocked, msg = _is_git_commit_blocked(command, args)
    if blocked:
        return msg

    # Import from controller layer
    from agent.skills.terminal.scripts import engine

    result = engine.run_command(command, args, timeout=60)
    return engine.format_result(result, command, args)


@skill_script(
    name="analyze_last_error",
    category="view",
    description="Analyze the last failed command in Flight Recorder.",
)
async def analyze_last_error() -> str:
    """
    [Debug Tool] Deeply analyzes the LAST failed command in the Flight Recorder.
    """
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
    description="Check the current execution environment.",
)
async def inspect_environment() -> str:
    """Check the current execution environment."""
    return f"OS: {platform.system()}, CWD: {os.getcwd()}"
