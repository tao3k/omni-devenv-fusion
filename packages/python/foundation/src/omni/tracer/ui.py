"""
tracing_ui.py - UltraRAG-style tracing UI with rich colors

Provides colored console output for execution tracing, inspired by UltraRAG's CLI design.

Features:
- Step-by-step visualization with colors
- Thinking content display
- Memory pool tracking
- Execution summary with statistics

Usage:
    from omni.tracer.ui import TracedExecution, console

    async with TracedExecution("my_task", trace_id="run_001") as tracer:
        tracer.set_param("$query", "...")
        step = tracer.start_step("planner", "NODE_START", {...})
        tracer.record_thinking(step, "Thinking...")
        tracer.end_step(step, {...})
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncGenerator

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markup import escape
from rich.columns import Columns
from rich.align import Align

# UltraRAG-inspired theme
THEME = Theme(
    {
        "step": "cyan",
        "step_start": "bold cyan",
        "step_end": "bold green",
        "thinking": "italic yellow",
        "memory": "magenta",
        "param": "bold blue",
        "tool": "bold white on blue",
        "error": "bold red",
        "success": "bold green",
        "trace_id": "dim cyan",
        "duration": "dim yellow",
        "info": "blue",
        "warn": "yellow",
        "header": "bold cyan",
    }
)

console = Console(theme=THEME)


def print_header(title: str, trace_id: str | None = None) -> None:
    """Print fancy header."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if trace_id:
        subtitle = f"[trace_id]Trace: {trace_id}[/trace_id] | [duration]{timestamp}[/duration]"
    else:
        subtitle = f"[duration]{timestamp}[/duration]"

    console.print(
        Panel(
            Text(f"[header]{title}[/header]\n\n{subtitle}", justify="center"),
            style="cyan",
            box=box.HEAVY,
            subtitle="[trace_id]UltraRAG Tracing[/trace_id]",
            subtitle_align="right",
        )
    )


def print_step_start(
    name: str, step_type: str, step_id: str, input_data: dict | None = None
) -> None:
    """Print step start event."""
    console.print(f"\n[step_start]▶ ENTER[/step_start] [tool]{name}[/tool]")
    console.print(f"   [dim]type={step_type} | id={step_id}[/dim]")

    if input_data:
        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Input", style="cyan", width=15)
        table.add_column("Value", style="white")
        for k, v in input_data.items():
            val = str(v)
            if len(val) > 60:
                val = val[:60] + "..."
            table.add_row(f"[param]{k}[/param]", escape(val))
        console.print(table)


def print_step_end(
    name: str, status: str, duration_ms: float, output_data: dict | None = None
) -> None:
    """Print step end event."""
    status_icon = "✓" if status == "completed" else "✗"
    status_style = "success" if status == "completed" else "error"
    console.print(f"\n[step_end]{status_icon} EXIT[/step_end] [tool]{name}[/tool]")
    console.print(
        f"   [{status_style}]{status.upper()}[/{status_style}] | [duration]{duration_ms:.1f}ms[/duration]"
    )

    if output_data:
        table = Table(show_header=True, header_style="bold green", box=box.SIMPLE)
        table.add_column("Output", style="cyan", width=15)
        table.add_column("Value", style="white")
        for k, v in output_data.items():
            val = str(v)
            if len(val) > 60:
                val = val[:60] + "..."
            table.add_row(f"[param]{k}[/param]", escape(val))
        console.print(table)


def print_thinking(step_name: str, content: str, indent: bool = True) -> None:
    """Print thinking content."""
    prefix = "    " if indent else ""
    lines = [content[i : i + 70] for i in range(0, len(content), 70)]
    for line in lines:
        console.print(f"{prefix}[thinking]💭 {escape(line)}[/thinking]")


def print_memory(var_name: str, value: Any, source_step: str, version: int) -> None:
    """Print memory save event."""
    console.print(f"\n[memory]📦 MEMORY → {var_name}[/memory]")
    console.print(f"   [dim]from={source_step} | v={version}[/dim]")

    if isinstance(value, (dict, list)):
        preview = str(value)
        if len(preview) > 80:
            preview = preview[:80] + "..."
        console.print(f"   [cyan]{escape(preview)}[/cyan]")
    else:
        console.print(f"   [cyan]{escape(str(value))}[/cyan]")


def print_param(key: str, value: Any) -> None:
    """Print parameter."""
    console.print(f"\n[param]🔧 PARAM → {key}[/param] = [cyan]{escape(str(value))}[/cyan]")


def print_error(message: str) -> None:
    """Print error."""
    console.print(f"\n[error]✗ ERROR[/error] {message}")


def print_success(message: str) -> None:
    """Print success."""
    console.print(f"\n[success]✓ {message}[/success]")


def print_info(message: str) -> None:
    """Print info."""
    console.print(f"\n[info]ℹ {message}[/info]")


def print_trace_summary(
    trace_id: str,
    success: bool,
    step_count: int,
    thinking_count: int,
    duration_ms: float,
    memory_summary: dict | None = None,
) -> None:
    """Print final trace summary."""
    status = "SUCCESS" if success else "FAILED"
    status_style = "success" if success else "error"

    summary = Table(title="[bold]Execution Summary[/bold]", show_header=False, box=box.ROUNDED)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="white")

    summary.add_row("Trace ID", f"[trace_id]{trace_id}[/trace_id]")
    summary.add_row("Status", f"[{status_style}]{status}[/{status_style}]")
    summary.add_row("Steps", str(step_count))
    summary.add_row("Thinking", str(thinking_count))
    summary.add_row("Duration", f"[duration]{duration_ms:.1f}ms[/duration]")

    if memory_summary:
        summary.add_row("", "")  # spacer
        for mem_type, count in memory_summary.items():
            if isinstance(count, dict):
                for name, c in count.items():
                    summary.add_row(f"  {mem_type}_{name}", str(c))
            else:
                summary.add_row(mem_type, str(count))

    console.print(
        Panel(
            Align.center(summary),
            title="[bold]TRACE COMPLETE[/bold]",
            style="cyan",
        )
    )


def print_execution_path(path: list[dict]) -> None:
    """Print execution path as a flow diagram."""
    if not path:
        return

    console.print("\n[header]📍 Execution Path[/header]")

    flow_table = Table(show_header=False, box=box.SIMPLE)
    flow_table.add_column("Step", style="cyan", width=30)
    flow_table.add_column("Type", style="magenta")
    flow_table.add_column("Status", style="green")

    for step in path:
        name = step.get("name", "unknown")[:25]
        step_type = step.get("type", "unknown")[:15]
        status = step.get("status", "pending")[:10]
        flow_table.add_row(f"[bold]{name}[/bold]", step_type, status)

    console.print(flow_table)


# =============================================================================
# Async context manager for traced execution
# =============================================================================

from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class StepInfo:
    """Information about a tracked step."""

    name: str
    step_type: str
    step_id: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    thinking: list[str] | None = None
    duration_ms: float = 0
    status: str = "pending"


class TracedExecution:
    """Async context manager for UltraRAG-style traced execution.

    Usage:
        async with TracedExecution("my_task", trace_id="run_001") as tracer:
            tracer.set_param("$query", "...")
            step = tracer.start_step("planner", "NODE_START", {...})
            tracer.record_thinking(step, "Thinking...")
            tracer.end_step(step, {...})
    """

    def __init__(
        self,
        task_name: str,
        trace_id: str | None = None,
        user_query: str | None = None,
        stream_to_console: bool = True,
    ):
        """Initialize traced execution.

        Args:
            task_name: Name of the task being traced
            trace_id: Optional trace ID (auto-generated if not provided)
            user_query: Optional user query for context
            stream_to_console: Whether to stream events to console
        """
        self.task_name = task_name
        self.trace_id = trace_id
        self.user_query = user_query
        self.stream_to_console = stream_to_console

        # Internal state
        self._steps: list[StepInfo] = []
        self._current_step_id: str | None = None
        self._step_stack: list[str] = []
        self._params: dict[str, Any] = {}
        self._memory: dict[str, list[dict]] = {}
        self._start_time: datetime | None = None
        self._step_count = 0
        self._thinking_count = 0

    async def __aenter__(self) -> "TracedExecution":
        """Enter context manager."""
        self._start_time = datetime.now()
        self.trace_id = self.trace_id or f"trace_{self._start_time.strftime('%Y%m%d_%H%M%S')}"

        if self.stream_to_console:
            print_header(self.task_name, self.trace_id)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and print summary."""
        assert self._start_time is not None, "Context not properly entered"
        duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000
        success = exc_type is None

        # Ensure trace_id is a string
        trace_id_str = self.trace_id or "unknown"

        if self.stream_to_console:
            # Build execution path
            path = [
                {
                    "name": s.name,
                    "type": s.step_type,
                    "status": s.status,
                }
                for s in self._steps
            ]

            print_execution_path(path)

            # Memory summary
            memory_summary = {
                "params": len(self._params),
                "memory_vars": {k: len(v) for k, v in self._memory.items()},
            }

            print_trace_summary(
                trace_id_str,
                success,
                len(self._steps),
                self._thinking_count,
                duration_ms,
                memory_summary,
            )

    def set_param(self, key: str, value: Any) -> None:
        """Set a parameter ($variable)."""
        if not key.startswith("$"):
            key = f"${key}"
        self._params[key] = value

        if self.stream_to_console:
            print_param(key, value)

    def start_step(
        self,
        name: str,
        step_type: str,
        input_data: dict | None = None,
    ) -> str:
        """Start a new step.

        Args:
            name: Name of the step
            step_type: Type of step (NODE_START, TOOL_START, LLM_START, etc.)
            input_data: Input data for the step

        Returns:
            Step ID
        """
        self._step_count += 1
        step_id = f"step_{self._step_count:03d}_{name}"
        self._step_stack.append(step_id)

        step = StepInfo(
            name=name,
            step_type=step_type,
            step_id=step_id,
            input_data=input_data,
            thinking=[],
        )
        self._steps.append(step)
        self._current_step_id = step_id

        if self.stream_to_console:
            print_step_start(name, step_type, step_id, input_data)

        return step_id

    def end_step(
        self,
        step_id: str,
        output_data: dict | None = None,
        status: str = "completed",
    ) -> None:
        """End a step.

        Args:
            step_id: ID of the step to end
            output_data: Output data from the step
            status: Step status (completed, error)
        """
        duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000

        for step in self._steps:
            if step.step_id == step_id:
                step.output_data = output_data
                step.status = status
                step.duration_ms = duration_ms
                if self._step_stack and self._step_stack[-1] == step_id:
                    self._step_stack.pop()
                break

        if self._step_stack:
            self._current_step_id = self._step_stack[-1]
        else:
            self._current_step_id = None

        if self.stream_to_console:
            step = next((s for s in self._steps if s.step_id == step_id), None)
            if step:
                print_step_end(step.name, status, step.duration_ms, output_data)

    def record_thinking(self, step_id: str | None, content: str) -> None:
        """Record thinking content for a step.

        Args:
            step_id: ID of the step (uses current if not provided)
            content: Thinking content
        """
        if step_id is None:
            step_id = self._current_step_id

        self._thinking_count += 1

        for step in self._steps:
            if step.step_id == step_id:
                if step.thinking is None:
                    step.thinking = []
                step.thinking.append(content)
                break

        if self.stream_to_console:
            step_name = next((s.name for s in self._steps if s.step_id == step_id), "unknown")
            print_thinking(step_name, content)

    def save_to_memory(
        self,
        var_name: str,
        value: Any,
        source_step: str | None = None,
    ) -> None:
        """Save to memory pool.

        Args:
            var_name: Variable name (with memory_ prefix for history tracking)
            value: Value to store
            source_step: Step ID that produced this value
        """
        if source_step is None:
            source_step = self._current_step_id or "unknown"

        if var_name not in self._memory:
            self._memory[var_name] = []
        version = len(self._memory[var_name]) + 1
        self._memory[var_name].append(
            {
                "value": value,
                "source_step": source_step,
                "timestamp": datetime.now(),
            }
        )

        if self.stream_to_console:
            print_memory(var_name, value, source_step, version)

    def get_memory_history(self, var_name: str) -> list[dict]:
        """Get history of a memory variable.

        Args:
            var_name: Variable name

        Returns:
            List of entries with value, source_step, timestamp
        """
        return self._memory.get(var_name, [])

    def get_step(self, step_id: str) -> StepInfo | None:
        """Get a step by ID.

        Args:
            step_id: Step ID

        Returns:
            StepInfo or None
        """
        return next((s for s in self._steps if s.step_id == step_id), None)

    @property
    def current_step_id(self) -> str | None:
        """Get current step ID."""
        return self._current_step_id

    @property
    def step_count(self) -> int:
        """Get step count."""
        return self._step_count

    @property
    def thinking_count(self) -> int:
        """Get thinking count."""
        return self._thinking_count


# =============================================================================
# Convenience function for quick tracing
# =============================================================================


@asynccontextmanager
async def traced(
    task_name: str,
    trace_id: str | None = None,
    user_query: str | None = None,
    stream: bool = True,
) -> AsyncGenerator[TracedExecution, None]:
    """Quick context manager for traced execution.

    Usage:
        async with traced("my_task", "run_001") as tracer:
            tracer.set_param("$query", "...")
            step = tracer.start_step("planner", "NODE_START", {...})
            ...
    """
    async with TracedExecution(task_name, trace_id, user_query, stream) as tracer:
        yield tracer


__all__ = [
    "console",
    "TracedExecution",
    "traced",
    "print_header",
    "print_step_start",
    "print_step_end",
    "print_thinking",
    "print_memory",
    "print_param",
    "print_error",
    "print_success",
    "print_info",
    "print_trace_summary",
    "print_execution_path",
]
