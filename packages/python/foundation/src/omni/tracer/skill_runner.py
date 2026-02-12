"""
skill_runner.py - Skill execution with UltraRAG-style tracing

Provides traced execution for skill commands with colored console output.

Usage:
    from omni.tracer.skill_runner import run_traced_skill

    result = await run_traced_skill(
        skill_name="git",
        command="git_commit",
        params={"message": "feat: add tracing"},
        trace_id="auto",
    )
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable

from omni.tracer.ui import (
    TracedExecution,
    print_header,
    print_step_start,
    print_step_end,
    print_thinking,
    print_memory,
    print_param,
    print_trace_summary,
    print_execution_path,
    print_error,
)


async def run_traced_skill(
    skill_name: str,
    command: str,
    handler: Callable,
    params: dict[str, Any] | None = None,
    trace_id: str | None = None,
    stream_output: bool = True,
) -> dict[str, Any]:
    """Run a skill command with UltraRAG-style tracing.

    Args:
        skill_name: Name of the skill (e.g., "git", "filesystem")
        command: Command name (e.g., "git_commit")
        handler: Async function to execute the command
        params: Command parameters
        trace_id: Optional trace ID (auto-generated if not provided)
        stream_output: Whether to stream events to console

    Returns:
        Command result dict with trace info
    """
    params = params or {}
    task_name = f"[cyan]{skill_name}[/cyan].[green]{command}[/green]"

    async with TracedExecution(
        task_name=task_name,
        trace_id=trace_id,
        stream_to_console=stream_output,
    ) as tracer:
        # Set parameters
        for key, value in params.items():
            tracer.set_param(f"${key}", value)

        # Start main step
        step_id = tracer.start_step(
            name=f"{skill_name}.{command}",
            step_type="TOOL_START",
            input_data=params,
        )

        # Record thinking
        tracer.record_thinking(
            step_id,
            f"Executing {skill_name}.{command} with params: {list(params.keys())}",
        )

        try:
            # Execute the handler
            result = await handler(**params)

            # Record result
            tracer.record_thinking(
                step_id,
                f"Command completed successfully with result type: {type(result).__name__}",
            )

            tracer.end_step(step_id, output_data={"result": "completed"}, status="completed")

            return {
                "status": "success",
                "result": result,
                "trace_id": tracer.trace_id,
                "step_count": tracer.step_count,
                "thinking_count": tracer.thinking_count,
            }

        except Exception as e:
            tracer.record_thinking(step_id, f"Error: {str(e)}")
            tracer.end_step(step_id, output_data={"error": str(e)}, status="error")

            return {
                "status": "error",
                "error": str(e),
                "trace_id": tracer.trace_id,
                "step_count": tracer.step_count,
                "thinking_count": tracer.thinking_count,
            }


class SkillRunner:
    """Runner for skill commands with tracing support."""

    def __init__(self, skills_dir: str | None = None, stream_output: bool = True):
        """Initialize skill runner.

        Args:
            skills_dir: Path to skills directory
            stream_output: Whether to stream events to console
        """
        self.skills_dir = skills_dir
        self.stream_output = stream_output
        self._traces: dict[str, dict] = {}

    async def run(
        self,
        skill_name: str,
        command: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a skill command.

        Args:
            skill_name: Name of the skill
            command: Command name
            params: Command parameters
            trace_id: Optional trace ID

        Returns:
            Command result with trace info
        """
        # Import from skill context
        from omni.core.skills.runtime import get_skill_context
        from omni.foundation.config.dirs import get_skills_dir
        from pathlib import Path

        skills_path = Path(self.skills_dir) if self.skills_dir else get_skills_dir()
        ctx = get_skill_context(skills_path)

        # Get the command handler
        full_command = f"{skill_name}.{command}"
        handler = ctx.get_command(full_command)

        if handler is None:
            # Try native function
            handler = ctx.get_native(skill_name, command)

        if handler is None:
            raise ValueError(f"Command not found: {full_command}")

        # Run with tracing
        return await run_traced_skill(
            skill_name=skill_name,
            command=command,
            handler=handler,
            params=params,
            trace_id=trace_id,
            stream_output=self.stream_output,
        )

    def get_trace(self, trace_id: str) -> dict | None:
        """Get a trace by ID.

        Args:
            trace_id: Trace ID

        Returns:
            Trace dict or None
        """
        return self._traces.get(trace_id)

    def list_traces(self, limit: int = 20) -> list[dict]:
        """List all traces.

        Args:
            limit: Maximum number of traces to return

        Returns:
            List of trace summaries
        """
        return [{"trace_id": k, **v} for k, v in list(self._traces.items())[-limit:]]


async def demo_skill_runner():
    """Demonstrate skill runner with tracing."""
    print_header("Skill Runner Demo", "demo_skill_001")

    # Mock skill handler for demo
    async def mock_git_commit(message: str, author: str = "Claude"):
        """Mock git commit handler."""
        await asyncio.sleep(0.1)  # Simulate work
        return {"commit": "abc123", "message": message, "author": author}

    async def mock_search(query: str, limit: int = 5):
        """Mock search handler."""
        await asyncio.sleep(0.1)
        return [{"title": f"Result {i}", "score": 1.0 - i * 0.1} for i in range(min(limit, 3))]

    # Run commands with tracing
    print("\n[cyan]=== Running git.git_commit with tracing ===[/cyan]\n")

    result1 = await run_traced_skill(
        skill_name="git",
        command="git_commit",
        handler=mock_git_commit,
        params={"message": "feat: add UltraRAG tracing"},
        trace_id="git_demo_001",
    )

    print("\n[cyan]=== Running search with tracing ===[/cyan]\n")

    result2 = await run_traced_skill(
        skill_name="knowledge",
        command="search",
        handler=mock_search,
        params={"query": "UltraRAG tracing", "limit": 3},
        trace_id="search_demo_001",
    )

    print("\n[success]=== Demo Complete ===[/success]")


if __name__ == "__main__":
    from omni.foundation.utils import run_async_blocking

    run_async_blocking(demo_skill_runner())
