"""
interfaces.py - Core type definitions for the execution tracing system

UltraRAG-style fine-grained execution tracing for LangGraph + MCP.

Defines:
- StepType: Enumeration of step types (LLM, TOOL, RETRIEVAL, REASONING, etc.)
- ExecutionStep: A single step in the execution trace
- ExecutionTrace: Complete execution trace with memory pool
- MemoryPool: Variable history tracking (UltraRAG concept)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class StepType(Enum):
    """Types of steps in the execution trace.

    Mirrors LangGraph callback events with additional UltraRAG-style types.
    """

    # Lifecycle
    CHAIN_START = "chain_start"
    CHAIN_END = "chain_end"

    # LLM operations
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    LLM_STREAM = "llm_stream"  # Real-time token streaming (thinking)

    # Tool operations
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"

    # Retrieval operations
    RETRIEVAL = "retrieval"

    # Reasoning/Thinking
    REASONING = "reasoning"

    # Graph nodes
    NODE_START = "node_start"
    NODE_END = "node_end"

    # Error handling
    ERROR = "error"


@dataclass
class ExecutionStep:
    """A single step in the execution trace.

    Captures the complete execution context including input, output,
    and reasoning content for debugging and analysis.
    """

    step_id: str
    step_type: StepType
    name: str  # Node/tool name (e.g., "plan", "execute", "omni.search")
    parent_id: str | None = None  # Parent step ID for hierarchical tracing

    # Data
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None

    # Reasoning/Thinking content (UltraRAG memory concept)
    reasoning_content: str | None = None

    # Timing
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float | None = None

    # Status
    status: str = "pending"  # pending, running, completed, error

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "name": self.name,
            "parent_id": self.parent_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "reasoning_content": self.reasoning_content,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionStep:
        """Deserialize from dictionary."""
        return cls(
            step_id=data["step_id"],
            step_type=StepType(data["step_type"]),
            name=data["name"],
            parent_id=data.get("parent_id"),
            input_data=data.get("input_data"),
            output_data=data.get("output_data"),
            reasoning_content=data.get("reasoning_content"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            duration_ms=data.get("duration_ms"),
            status=data.get("status", "completed"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MemoryEntry:
    """A single entry in the memory pool.

    Tracks variable state changes over time.
    """

    var_name: str
    value: Any
    source_step: str  # step_id that created/modified this entry
    timestamp: datetime = field(default_factory=datetime.now)


class MemoryPool:
    """UltraRAG-style memory pool for tracking variable history.

    Maintains a history of all variable changes during execution.
    Each variable can have multiple entries, allowing full reconstruction
    of the execution state at any point.
    """

    def __init__(self):
        self._pool: dict[str, list[MemoryEntry]] = {}

    def save(
        self,
        var_name: str,
        value: Any,
        source_step: str,
    ) -> None:
        """Save a variable to memory.

        Args:
            var_name: Name of the variable
            value: Value to store
            source_step: Step ID that produced this value
        """
        entry = MemoryEntry(var_name=var_name, value=value, source_step=source_step)
        if var_name not in self._pool:
            self._pool[var_name] = []
        self._pool[var_name].append(entry)

    def get(self, var_name: str) -> list[MemoryEntry] | None:
        """Get all entries for a variable."""
        return self._pool.get(var_name)

    def get_latest(self, var_name: str) -> MemoryEntry | None:
        """Get the latest value of a variable."""
        entries = self._pool.get(var_name)
        if entries:
            return entries[-1]
        return None

    def get_history(self, var_name: str) -> list[tuple[datetime, Any, str]]:
        """Get variable history as (timestamp, value, source_step) tuples."""
        entries = self._pool.get(var_name, [])
        return [(e.timestamp, e.value, e.source_step) for e in entries]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Serialize to dictionary."""
        return {
            var_name: [
                {
                    "var_name": entry.var_name,
                    "value": self._serialize_value(entry.value),
                    "source_step": entry.source_step,
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in entries
            ]
            for var_name, entries in self._pool.items()
        }

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON storage."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, list):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        # For complex objects, try to get a useful representation
        try:
            return str(value)
        except Exception:
            return f"<{type(value).__name__}>"

    def summary(self) -> dict[str, int]:
        """Get a summary of memory pool contents."""
        return {var_name: len(entries) for var_name, entries in self._pool.items()}


@dataclass
class ExecutionTrace:
    """Complete execution trace with all steps and memory pool.

    UltraRAG-style trace that captures the full execution trajectory
    including thinking process, tool calls, and variable history.
    """

    trace_id: str
    root_step_id: str | None = None  # Entry point step

    # Execution data
    steps: dict[str, ExecutionStep] = field(default_factory=dict)
    memory_pool: MemoryPool = field(default_factory=MemoryPool)

    # Global variables (inputs, outputs)
    global_vars: dict[str, Any] = field(default_factory=dict)

    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    # Execution metadata
    user_query: str | None = None
    thread_id: str | None = None
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trace_id": self.trace_id,
            "root_step_id": self.root_step_id,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "memory_pool": self.memory_pool.to_dict(),
            "global_vars": self.global_vars,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "user_query": self.user_query,
            "thread_id": self.thread_id,
            "success": self.success,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionTrace:
        """Deserialize from dictionary."""
        trace = cls(
            trace_id=data["trace_id"],
            root_step_id=data.get("root_step_id"),
            global_vars=data.get("global_vars", {}),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            user_query=data.get("user_query"),
            thread_id=data.get("thread_id"),
            success=data.get("success", True),
            error_message=data.get("error_message"),
        )
        trace.steps = {k: ExecutionStep.from_dict(v) for k, v in data.get("steps", {}).items()}
        # Note: MemoryPool deserialization would need additional logic
        return trace

    @property
    def duration_ms(self) -> float | None:
        """Calculate total execution duration."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def get_execution_path(self) -> list[ExecutionStep]:
        """Get the execution path as an ordered list of steps."""
        # Simple approach: sort by timestamp
        return sorted(self.steps.values(), key=lambda s: s.timestamp)

    def get_thinking_steps(self) -> list[ExecutionStep]:
        """Get all steps that have reasoning content."""
        return [s for s in self.steps.values() if s.reasoning_content]

    def step_count(self) -> int:
        """Get total step count."""
        return len(self.steps)

    def thinking_step_count(self) -> int:
        """Get count of steps with thinking content."""
        return len(self.get_thinking_steps())


__all__ = [
    "StepType",
    "ExecutionStep",
    "MemoryEntry",
    "MemoryPool",
    "ExecutionTrace",
]
