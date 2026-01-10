"""
agent/skills/terminal/tools.py
Terminal Skill - Shell execution with safety.

Phase 25.1: Macro System with @skill_command decorators.
Phase 36: Local SafeExecutor implementation (moved from mcp_core.execution)
"""

import asyncio
import re
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# Initialize project memory for flight recorder
_project_memory = None


def _get_project_memory():
    """Lazy initialization of project memory."""
    global _project_memory
    if _project_memory is None:
        try:
            from common.mcp_core.memory import ProjectMemory

            _project_memory = ProjectMemory()
        except ImportError:
            _project_memory = None
    return _project_memory


# =============================================================================
# Local SafeExecutor Implementation (moved from mcp_core.execution)
# =============================================================================

# Whitelist of allowed commands (empty = allow all for development)
ALLOWED_COMMANDS: list[str] = []

# Dangerous patterns that will always be blocked
DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+/", "rm -rf / - Deletes entire filesystem"),
    (r"rm\s+-rf\s+/\w+", "rm -rf /{path} - Dangerous recursive delete"),
    (r":\(\)\s*\|", "Process substitution - may bypass security"),
    (r"\$\(.*\)", "Command substitution - complex execution"),
    (r"`[^`]+`", "Backtick command substitution - complex execution"),
    (r">\s*/dev/", "Redirect to device - potential DoS"),
    (r"&\&", "Conditional execution - may alter logic"),
    (r"\|\|", "Conditional execution - may alter logic"),
    (r";\s*rm", "Chained rm - potential data loss"),
    (r"mkfs", "Format filesystem - destructive"),
    (r"dd\s+if=", "Direct disk access - dangerous"),
    (r"wget\s+.*\|\s*sh", "Pipe to shell - extremely dangerous"),
    (r"curl\s+.*\|\s*sh", "Pipe to shell - extremely dangerous"),
    (r"python.*-c.*\|", "Python one-liner pipe - suspicious"),
    (r"nc\s+-e", "Netcat with execute - reverse shell pattern"),
    (r"/etc/passwd", "Access to password file - privilege escalation risk"),
    (r"~/.ssh", "Access to SSH keys - credential theft risk"),
    (r"chmod\s+\+[xs]", "Add executable permission - privilege escalation"),
    (r"chown", "Change ownership - privilege escalation"),
    (r"sudo\s+rm", "sudo rm - high risk operation"),
    (r"fork\s* bomb", "Fork bomb - DoS attack"),
]


@dataclass
class ExecutionResult:
    """Result of command execution."""

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    command: str = ""
    args: list[str] = field(default_factory=list)


class SafeExecutor:
    """
    Safe command executor with whitelist validation.

    Phase 36: Local implementation - no longer depends on mcp_core.execution
    """

    # Whitelist of allowed commands
    _whitelist: set[str] = set()

    @classmethod
    def add_to_whitelist(cls, commands: list[str]) -> None:
        """Add commands to the whitelist."""
        cls._whitelist.update(commands)

    @classmethod
    def clear_whitelist(cls) -> None:
        """Clear the whitelist."""
        cls._whitelist.clear()

    @classmethod
    async def run(
        cls, command: str, args: list[str] | None = None, timeout: int = 60
    ) -> dict[str, Any]:
        """
        Execute a command safely with timeout.

        Args:
            command: Command to execute
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            Dict with exit_code, stdout, stderr, duration_ms
        """
        if args is None:
            args = []

        # Check whitelist if not empty
        if cls._whitelist and command not in cls._whitelist:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Command '{command}' not in whitelist",
                "duration_ms": 0,
                "command": command,
                "args": args,
            }

        # Build command string for logging
        cmd_str = f"{command} {' '.join(args)}" if args else command

        try:
            start_time = asyncio.get_event_loop().time()

            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutExpired:
                process.kill()
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout}s",
                    "duration_ms": timeout * 1000,
                    "command": command,
                    "args": args,
                }

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return {
                "exit_code": process.returncode,
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "duration_ms": duration_ms,
                "command": command,
                "args": args,
            }

        except FileNotFoundError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command not found: {command}",
                "duration_ms": 0,
                "command": command,
                "args": args,
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": 0,
                "command": command,
                "args": args,
            }

    @staticmethod
    def format_result(result: dict[str, Any], command: str, args: list[str]) -> str:
        """Format execution result for display."""
        output = []

        if result.get("stdout"):
            output.append(result["stdout"])

        if result.get("stderr"):
            output.append(f"STDERR:\n{result['stderr']}")

        if result.get("exit_code", 0) != 0:
            output.append(f"Exit code: {result.get('exit_code')}")

        return "\n".join(output).strip() or "(no output)"


def check_dangerous_patterns(command: str, args: list[str]) -> tuple[bool, str]:
    """
    Check if a command contains dangerous patterns.

    Args:
        command: The command being executed
        args: Command arguments

    Returns:
        Tuple of (is_safe, error_message)
    """
    full_command = f"{command} {' '.join(args)}"

    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, full_command, re.IGNORECASE):
            return False, f"Dangerous pattern detected: {description}"

    return True, ""


def log_decision(event: str, payload: dict[str, Any], logger=None) -> None:
    """Log a decision/event with structured payload."""
    if logger is None:
        logger = structlog.get_logger("decision")
    logger.info(event, **payload)


@skill_command(
    name="execute_command",
    category="workflow",
    description="Execute a shell command with whitelist validation.",
)
async def execute_command(command: str, args: Optional[list[str]] = None, timeout: int = 60) -> str:
    """
    Execute a shell command with whitelist validation.

    Args:
        command: The command to execute (e.g., "cat", "ls").
        args: Command arguments (e.g., ["cog.toml", "-la"]).
        timeout: Maximum execution time in seconds (default: 60).
    """
    if args is None:
        args = []

    # Protocol Enforcement: Block direct git commit
    cmd_lower = command.lower()
    if "git commit" in cmd_lower:
        return (
            "PROHIBITED: Direct 'git commit' is disabled in Terminal.\n"
            "Use the 'git_commit' tool in the 'git' skill.\n"
            "Reason: Requires user confirmation via Claude Desktop."
        )

    # Security check
    is_safe, error_msg = check_dangerous_patterns(command, args)
    if not is_safe:
        return f"Blocked: {error_msg}"

    cmd = command

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


@skill_command(
    name="run_task",
    category="workflow",
    description="Run safe development tasks (just, nix, git) with FLIGHT RECORDER.",
)
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
1. omni_run("git", "git_commit", {"message": "feat(scope): description"})
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
    log_decision("run_task.request", {"cmd": command, "args": args}, logger)
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


@skill_command(
    name="analyze_last_error",
    category="view",
    description="Analyze the last failed command in Flight Recorder.",
)
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


@skill_command(
    name="inspect_environment",
    category="read",
    description="Check the current execution environment.",
)
async def inspect_environment() -> str:
    """Check the current execution environment."""
    import os
    import platform

    return f"OS: {platform.system()}, CWD: {os.getcwd()}"
