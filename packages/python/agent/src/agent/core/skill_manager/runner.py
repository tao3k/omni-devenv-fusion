"""
src/agent/core/skill_manager/runner.py
Phase 62: Script Mode Runner for Sandboxed Subprocess Execution.

Provides isolated subprocess execution for skills that need:
- Dependency isolation (separate venv/environment)
- State isolation (no pollution of main process)
- Resource limits (timeout, memory)

Usage:
    runner = ScriptModeRunner()
    result = await runner.run_command(
        skill_path=Path("assets/skills/git"),
        command="smart_workflow",
        args={"message": "fix bug", "files": ["main.py"]}
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .models import SkillCommand

if TYPE_CHECKING:
    from ..protocols import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class SubprocessResult:
    """Result from subprocess execution."""

    success: bool
    output: str
    error: str | None = None
    return_code: int = 0
    duration_ms: float = 0.0


class ScriptModeRunner:
    """Runner for executing skills in isolated subprocess.

    Supports two execution modes:
    1. In-process: Direct function call (same as before)
    2. Subprocess: Isolated uv run execution
    """

    def __init__(
        self,
        uv_binary: str = "uv",
        timeout_seconds: int = 120,
    ) -> None:
        """Initialize the script mode runner.

        Args:
            uv_binary: Path to uv binary (default: "uv")
            timeout_seconds: Maximum execution time per command
        """
        self.uv_binary = uv_binary
        self.timeout_seconds = timeout_seconds

    async def run_command(
        self,
        skill_path: Path,
        command: SkillCommand,
        args: dict[str, Any],
    ) -> SubprocessResult:
        """Execute a skill command.

        This method:
        1. Checks if subprocess mode is required
        2. Prepares the execution environment
        3. Runs the command (in-process or subprocess)
        4. Returns the result

        Args:
            skill_path: Path to the skill directory
            command: SkillCommand to execute
            args: Arguments for the command

        Returns:
            SubprocessResult with output or error
        """
        import time

        t0 = time.perf_counter()

        try:
            # Check if we should run in subprocess
            # For now, always run in-process for simplicity
            # Phase 62: Could add execution_mode check here
            logger.debug(f"Running {command} in-process (skill at {skill_path})")

            result = await self._run_in_process(command, args)

            return SubprocessResult(
                success=result.success,
                output=result.output,
                error=result.error,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        except Exception as e:
            return SubprocessResult(
                success=False,
                output="",
                error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    async def run_in_subprocess(
        self,
        skill_path: Path,
        command: str,
        args: dict[str, Any],
        entry_point: str = "main.py",
    ) -> SubprocessResult:
        """Execute a skill command in an isolated subprocess.

        Uses uv run to ensure:
        - Dependency isolation
        - Consistent Python environment
        - No state pollution

        Args:
            skill_path: Path to the skill directory
            command: Name of the command to run
            args: Arguments for the command (JSON serialized)
            entry_point: Entry point script in the skill

        Returns:
            SubprocessResult with output or error
        """
        import time

        t0 = time.perf_counter()

        # Find the skill's script entry point
        script_path = skill_path / "scripts" / f"{command}.py"

        if not script_path.exists():
            # Fallback to skill root
            script_path = skill_path / entry_point

        if not script_path.exists():
            return SubprocessResult(
                success=False,
                output="",
                error=f"Script not found: {script_path}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # Prepare arguments as JSON
        args_json = json.dumps(args)

        # Build command
        cmd = [
            self.uv_binary,
            "run",
            "--directory",
            str(skill_path),
            "--quiet",
            "python",
            str(script_path),
            command,
            args_json,
        ]

        logger.debug(f"Executing {command} in subprocess for skill at {skill_path}")

        try:
            # Run with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                return SubprocessResult(
                    success=False,
                    output="",
                    error=f"Timeout after {self.timeout_seconds}s",
                    return_code=-1,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Decode output
            output = stdout.decode("utf-8").strip()
            error_msg = stderr.decode("utf-8").strip()

            success = process.returncode == 0

            if not success and not error_msg:
                error_msg = f"Exit code: {process.returncode}"

            return SubprocessResult(
                success=success,
                output=output,
                error=error_msg if not success else None,
                return_code=process.returncode or 0,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        except FileNotFoundError:
            return SubprocessResult(
                success=False,
                output="",
                error=f"uv not found: {self.uv_binary}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return SubprocessResult(
                success=False,
                output="",
                error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    async def _run_in_process(
        self,
        command: SkillCommand,
        args: dict[str, Any],
    ) -> "ExecutionResult":
        """Run command in the current process.

        This is the existing behavior, delegated to SkillCommand.execute().
        """
        return await command.execute(args)


# Type alias for circular import
if False:
    from ..protocols import ExecutionResult


__all__ = [
    "ScriptModeRunner",
    "SubprocessResult",
]
