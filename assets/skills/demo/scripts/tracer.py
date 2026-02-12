"""Demo skill wrapper for packaged graphflow runtime.

This module intentionally keeps only skill-facing command wrappers.
All graph workflow logic lives in the Python package (`omni.tracer`).
"""

from __future__ import annotations

from omni.foundation.api.decorators import skill_command
from omni.tracer import run_graphflow_pipeline


@skill_command(
    name="run_langgraph",
    description=(
        "Execute the packaged graphflow runtime with trace output and configurable quality gates."
    ),
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)
async def run_langgraph(
    scenario: str = "complex",
    quality_threshold: str = "0.8",
    quality_gate_novelty_threshold: str = "0.2",
    quality_gate_coverage_threshold: str = "0.7",
    quality_gate_min_evidence_count: str = "2",
    quality_gate_require_tradeoff: str = "true",
    quality_gate_max_fail_streak: str = "2",
) -> dict[str, object]:
    """Run graphflow scenario via the package runtime.

    Args:
        scenario: Workflow scenario (`simple` or `complex`).
        quality_threshold: Minimum evaluator quality to draft/finalize.
        quality_gate_novelty_threshold: Minimum novelty score in evaluator gate.
        quality_gate_coverage_threshold: Minimum coverage score in evaluator gate.
        quality_gate_min_evidence_count: Minimum evidence snippets required.
        quality_gate_require_tradeoff: Whether trade-off must be present.
        quality_gate_max_fail_streak: Consecutive gate failures before forcing draft.
    """
    return await run_graphflow_pipeline(
        scenario=scenario,
        quality_threshold=quality_threshold,
        quality_gate_novelty_threshold=quality_gate_novelty_threshold,
        quality_gate_coverage_threshold=quality_gate_coverage_threshold,
        quality_gate_min_evidence_count=quality_gate_min_evidence_count,
        quality_gate_require_tradeoff=quality_gate_require_tradeoff,
        quality_gate_max_fail_streak=quality_gate_max_fail_streak,
    )
