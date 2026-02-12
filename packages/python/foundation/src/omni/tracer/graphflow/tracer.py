"""Graphflow execution tracer with memory persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from omni.foundation.config.prj import PRJ_CACHE

from .types import ExecutionStep, ExecutionTrace, StepType


class LangGraphTracer:
    """Traces LangGraph execution with UltraRAG conventions."""

    def __init__(self, trace_id: str, thread_id: str, scenario: str):
        self.trace = ExecutionTrace(
            trace_id=trace_id,
            thread_id=thread_id,
            scenario=scenario,
        )
        self._step_counter = 0
        self._step_start_times: dict[str, datetime] = {}

    def start_step(
        self,
        name: str,
        step_type: StepType,
        input_data: dict | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Mark step as started."""
        self._step_counter += 1
        step_id = f"step_{self._step_counter:03d}_{name}"
        self._step_start_times[step_id] = datetime.now()

        step = ExecutionStep(
            step_id=step_id,
            step_type=step_type,
            name=name,
            parent_id=parent_id,
            input_data=input_data,
            status="running",
        )
        self.trace.steps.append(step)
        return step_id

    def end_step(
        self,
        step_id: str,
        output_data: dict | None = None,
        reasoning: str | None = None,
        status: str = "completed",
    ) -> None:
        """Mark step as completed."""
        if step_id in self._step_start_times:
            duration = (datetime.now() - self._step_start_times[step_id]).total_seconds() * 1000
            self.trace.steps[-1].duration_ms = round(duration, 2)

        self.trace.steps[-1].output_data = output_data
        self.trace.steps[-1].reasoning = reasoning
        self.trace.steps[-1].status = status

    def record_reflection(self, reflection: str) -> None:
        """Record a reflection in memory pool."""
        self.record_memory(
            key="reflection_labels",
            value=reflection,
            step="reflector.reflect",
            metadata={"kind": "reflection_label"},
        )

    def record_memory(
        self,
        key: str,
        value: str,
        step: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Record a structured memory value with context metadata."""
        if key not in self.trace.memory_pool:
            self.trace.memory_pool[key] = []
        self.trace.memory_pool[key].append(
            {
                "step": step,
                "content": value,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )

    def write_memory_output(self, output_dir: str | None = None) -> str:
        """Persist full memory pool snapshot to JSON for offline analysis."""
        # Use PRJ_CACHE if no explicit output_dir provided
        if output_dir is None:
            output_path = PRJ_CACHE("ultrarag")
        else:
            output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        payload = {
            "trace_id": self.trace.trace_id,
            "thread_id": self.trace.thread_id,
            "scenario": self.trace.scenario,
            "timestamp": datetime.now().isoformat(),
            "memory_pool": self.trace.memory_pool,
        }
        file_path = output_path / f"{self.trace.trace_id}_memory.json"
        file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return str(file_path)

    def finalize(self) -> None:
        """Finalize the trace."""
        self.trace.end_time = datetime.now()
        self.trace.status = "completed"


__all__ = ["LangGraphTracer"]
