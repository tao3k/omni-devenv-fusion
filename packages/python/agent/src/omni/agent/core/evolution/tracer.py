"""
tracer.py - Execution Trace Collection for OmniCell

Collects execution traces from OmniCell and feeds them to the Harvester
for skill crystallization.

UltraRAG-style Integration:
    OmniCell → ExecutionTracer (fine-grained) → TraceCollector (harvest) → Harvester → Factory → Immune → Skill Registry

Integration: OmniCell → Tracer → Harvester → Factory → Immune → Skill Registry
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.evolution.tracer")


@dataclass
class ExecutionTrace:
    """Represents a single execution trace from OmniCell."""

    task_id: str
    task_description: str
    commands: list[str]
    outputs: list[str]
    success: bool
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "commands": self.commands,
            "outputs": self.outputs,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionTrace:
        """Deserialize from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_description=data["task_description"],
            commands=data["commands"],
            outputs=data["outputs"],
            success=data["success"],
            duration_ms=data["duration_ms"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


class TraceCollector:
    """Collects and manages execution traces from OmniCell."""

    def __init__(self, trace_dir: Path | None = None):
        """Initialize the trace collector.

        Args:
            trace_dir: Directory to store traces. Defaults to PRJ_DATA/evolution/traces
        """
        if trace_dir is None:
            from omni.foundation.config.dirs import get_data_dir

            data_dir = get_data_dir()
            if data_dir is not None:
                trace_dir = data_dir / "evolution" / "traces"
            else:
                # Fallback to current directory
                trace_dir = Path(".prj_data/evolution/traces")

        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._trace_count = 0

    async def record(
        self,
        task_id: str,
        task_description: str,
        commands: list[str],
        outputs: list[str],
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record an execution trace.

        Args:
            task_id: Unique identifier for the task
            task_description: Human-readable description of the task
            commands: List of commands executed
            outputs: List of command outputs
            success: Whether the execution was successful
            duration_ms: Execution duration in milliseconds
            metadata: Optional additional metadata

        Returns:
            Trace ID (filename without extension)
        """
        trace = ExecutionTrace(
            task_id=task_id,
            task_description=task_description,
            commands=commands,
            outputs=outputs,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        # Generate trace ID
        trace_id = f"{trace.timestamp.strftime('%Y%m%d_%H%M%S')}_{task_id}_{self._trace_count}"
        self._trace_count += 1

        # Save trace
        trace_file = self.trace_dir / f"{trace_id}.json"
        trace_file.write_text(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))

        logger.info(
            "evolution.trace_recorded",
            task_id=task_id,
            command_count=len(commands),
            success=success,
            trace_file=str(trace_file),
        )

        return trace_id

    async def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        """Retrieve a specific trace by ID."""
        trace_file = self.trace_dir / f"{trace_id}.json"
        if not trace_file.exists():
            return None

        data = json.loads(trace_file.read_text())
        return ExecutionTrace.from_dict(data)

    async def get_traces_by_task(self, task_pattern: str) -> list[ExecutionTrace]:
        """Get all traces matching a task pattern."""
        traces = []
        for trace_file in self.trace_dir.glob("*.json"):
            try:
                data = json.loads(trace_file.read_text())
                if task_pattern.lower() in data.get("task_description", "").lower():
                    traces.append(ExecutionTrace.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to parse trace {trace_file}: {e}")
        return traces

    async def get_recent_traces(self, limit: int = 100) -> list[ExecutionTrace]:
        """Get the most recent traces."""
        traces = []
        for trace_file in sorted(self.trace_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(trace_file.read_text())
                traces.append(ExecutionTrace.from_dict(data))
            except Exception:
                pass
        return traces

    async def get_traces_for_harvester(self) -> list[dict[str, Any]]:
        """Get traces formatted for the Harvester."""
        traces = await self.get_recent_traces(100)
        return [
            {
                "task_description": t.task_description,
                "commands": t.commands,
                "outputs": t.outputs,
                "success": t.success,
                "duration_ms": t.duration_ms,
            }
            for t in traces
        ]

    async def cleanup_old_traces(self, keep_count: int = 500) -> int:
        """Remove old traces, keeping the most recent ones."""
        trace_files = sorted(self.trace_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)

        removed = 0
        for trace_file in trace_files[:-keep_count]:
            trace_file.unlink()
            removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} old traces")

        return removed

    @property
    def trace_count(self) -> int:
        """Get the total number of stored traces."""
        return len(list(self.trace_dir.glob("*.json")))

    async def record_detailed(
        self,
        trace: Any,  # ExecutionTrace from omni.tracer
        task_description: str | None = None,
    ) -> str:
        """Record a detailed execution trace (UltraRAG-style).

        Extracts commands/outputs from the detailed trace and saves
        in the legacy format for harvester compatibility.

        Args:
            trace: ExecutionTrace from omni.tracer
            task_description: Optional human-readable description

        Returns:
            Trace ID
        """
        # Extract commands and outputs from trace steps
        commands = []
        outputs = []

        for step in trace.steps.values():
            if step.step_type.value.startswith("tool_"):
                # Tool calls become commands
                if step.input_data:
                    cmd = f"{step.name}: {step.input_data}"
                    commands.append(cmd)
                if step.output_data:
                    outputs.append(f"{step.name}: {step.output_data}")

        # Generate task description from trace
        if task_description is None:
            task_description = (
                trace.user_query or f"Traced execution with {trace.step_count()} steps"
            )

        # Record in legacy format
        trace_id = await self.record(
            task_id=trace.trace_id,
            task_description=task_description,
            commands=commands,
            outputs=outputs,
            success=trace.success,
            duration_ms=trace.duration_ms or 0,
            metadata={
                "trace_id": trace.trace_id,
                "step_count": trace.step_count(),
                "thinking_steps": trace.thinking_step_count(),
                "memory_pool_summary": trace.memory_pool.summary(),
                "detailed_trace_available": True,
            },
        )

        # Optionally save detailed trace separately
        try:
            from omni.tracer import TraceStorage

            storage = TraceStorage()
            storage.save(trace)
            logger.debug("detailed_trace_saved", trace_id=trace.trace_id)
        except Exception as e:
            logger.warning(f"Failed to save detailed trace: {e}")

        return trace_id
