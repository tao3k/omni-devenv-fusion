"""
terminal/scripts/commands.py - Terminal Skill Commands

Migrated from tools.py to scripts pattern.
"""

import os
import platform

from omni.foundation.api.decorators import skill_command


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


@skill_command(
    name="run_task",
    category="workflow",
    description="""
    Runs safe development tasks (just, nix, git) with FLIGHT RECORDER.

    FLIGHT RECORDER captures command execution for debugging and audit trails.

    Args:
        cmd: The command to run (e.g., `git`, `just`, `nix`).
                Can include args in single string like `"just validate"`.
        args: Optional list of arguments as separate strings.
                Example: `{"cmd": "git", "args": ["status"]}`
        inject_root: Auto-inject $PRJ_ROOT to args (enabled by default).

    Returns:
        Command output with execution status and timing.

    Examples:
        @omni("terminal.run_task", {"cmd": "git", "args": ["status"]})
        @omni("terminal.run_task", {"cmd": "just validate"})
    """,
    inject_root=True,
)
async def run_task(cmd: str, args: list[str] | None = None, **kwargs) -> str:
    # Ensure args is a list of strings
    if args is None:
        args = []
    elif not isinstance(args, list):
        args = [str(args)] if args else []
    else:
        # Ensure all elements are strings
        args = [str(a) for a in args]

    if (
        args
        and len(args) == 1
        and isinstance(args[0], str)
        and " " in args[0]
    ):
        parts = args[0].split()
        cmd = parts[0]
        args = parts[1:]
    elif " " in cmd:
        parts = cmd.split()
        cmd = parts[0]
        extra_args = parts[1:]
        if extra_args:
            args = extra_args + args

    blocked, msg = _is_git_commit_blocked(cmd, args)
    if blocked:
        return msg

    from . import engine

    result = engine.run_command(cmd, args, timeout=60)
    return engine.format_result(result, cmd, args)


@skill_command(
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
        from omni.foundation.services.memory import ProjectMemory

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


@skill_command(
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


@skill_command(
    name="run_command",
    category="workflow",
    description="""
    Run a shell command and return output.

    Args:
        - cmd: str - Command to run
        - working_dir: Optional[str] - Working directory
        - timeout: int = 60 - Timeout in seconds
        - tail_lines: Optional[int] - Show only last N lines

    Returns:
        Command stdout and stderr output.
    """,
    inject_root=True,
)
async def run_command(
    cmd: str,
    working_dir: str | None = None,
    timeout: int = 60,
    tail_lines: int | None = None,
) -> str:
    from . import engine

    # Parse cmd string if it contains spaces
    if " " in cmd:
        parts = cmd.split()
        cmd_name = parts[0]
        cmd_args = [str(a) for a in parts[1:]]
    else:
        cmd_name = str(cmd)
        cmd_args = []

    result = engine.run_command(cmd_name, cmd_args, timeout=timeout, working_dir=working_dir)
    return engine.format_result(result, cmd_name, cmd_args, tail_lines=tail_lines)
