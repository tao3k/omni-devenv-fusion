"""Graphflow shared types and state schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypedDict


class StepType(Enum):
    """Execution step types."""

    CHAIN_START = "CHAIN_START"
    CHAIN_END = "CHAIN_END"
    NODE_START = "NODE_START"
    NODE_END = "NODE_END"
    CONDITIONAL = "CONDITIONAL"
    LOOP_ITERATION = "LOOP_ITERATION"
    LLM_CALL = "LLM_CALL"


@dataclass
class ExecutionStep:
    """A single execution step."""

    step_id: str
    step_type: StepType
    name: str
    parent_id: str | None = None
    input_data: dict | None = None
    output_data: dict | None = None
    reasoning: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float | None = None
    status: str = "pending"


@dataclass
class ExecutionTrace:
    """Complete execution trace."""

    trace_id: str
    thread_id: str
    scenario: str
    steps: list[ExecutionStep] = field(default_factory=list)
    memory_pool: dict[str, list] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    status: str = "running"

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "thread_id": self.thread_id,
            "scenario": self.scenario,
            "status": self.status,
            "step_count": len(self.steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type.value,
                    "name": s.name,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                }
                for s in self.steps
            ],
            "memory_pool": {k: len(v) for k, v in self.memory_pool.items()},
        }


# =============================================================================
# State Definitions
# =============================================================================


class DemoState(TypedDict):
    """LangGraph state with structured reflection labels for cross-node context."""

    topic: str
    iterations: int
    max_iterations: int
    quality_score: float
    analysis: str
    analysis_history: list[str]
    # Structured reflection labels in XML format for cross-node context.
    # Each entry example: <issue id="1" status="open">specific issue text</issue>
    reflection_labels: list[str]
    draft: str
    final: str
    quality_evaluations: list[str]
    ready_to_draft: bool
    duplicate_streak: int
    quality_delta_streak: int
    last_quality_score: float
    routing_reason: str
    no_improvement_rewrite_used: bool
    quality_threshold: float
    quality_gate_novelty_threshold: float
    quality_gate_coverage_threshold: float
    quality_gate_min_evidence_count: int
    quality_gate_require_tradeoff: bool
    quality_gate_max_fail_streak: int
    quality_gate_fail_streak: int


__all__ = ["StepType", "ExecutionStep", "ExecutionTrace", "DemoState"]
