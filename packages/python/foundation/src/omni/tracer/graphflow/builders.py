"""Graphflow workflow builders and state initializers."""

from __future__ import annotations

from typing import Literal, cast

from .nodes import llm_analyze, llm_draft, llm_evaluate, llm_finalize, llm_reflect
from .tracer import LangGraphTracer
from .types import DemoState


def default_parameters_for_scenario(scenario: str) -> dict[str, object]:
    """Return default pipeline parameters with scenario-specific quality gates."""
    base = {
        "topic": "Why use typed languages?",
        "max_iterations": 3,
        "quality_threshold": 0.8,
        "quality_gate_novelty_threshold": 0.20,
        "quality_gate_coverage_threshold": 0.80,
        "quality_gate_min_evidence_count": 1,
        "quality_gate_require_tradeoff": True,
        "quality_gate_max_fail_streak": 2,
    }
    overrides = {
        "simple": {
            "quality_gate_novelty_threshold": 0.10,
            "quality_gate_coverage_threshold": 0.60,
            "quality_gate_max_fail_streak": 1,
        },
        "loop": {
            "quality_gate_novelty_threshold": 0.15,
            "quality_gate_coverage_threshold": 0.75,
            "quality_gate_max_fail_streak": 2,
        },
        "complex": {
            "quality_gate_novelty_threshold": 0.20,
            "quality_gate_coverage_threshold": 0.80,
            "quality_gate_max_fail_streak": 2,
        },
    }
    base.update(overrides.get(scenario, overrides["complex"]))
    return base


def apply_parameter_overrides(
    parameters: dict[str, object],
    *,
    quality_threshold: float | None = None,
    quality_gate_novelty_threshold: float | None = None,
    quality_gate_coverage_threshold: float | None = None,
    quality_gate_min_evidence_count: int | None = None,
    quality_gate_require_tradeoff: bool | None = None,
    quality_gate_max_fail_streak: int | None = None,
) -> dict[str, object]:
    """Apply runtime parameter overrides and return a copied mapping."""
    updated = dict(parameters)
    runtime_overrides = {
        "quality_threshold": quality_threshold,
        "quality_gate_novelty_threshold": quality_gate_novelty_threshold,
        "quality_gate_coverage_threshold": quality_gate_coverage_threshold,
        "quality_gate_min_evidence_count": quality_gate_min_evidence_count,
        "quality_gate_require_tradeoff": quality_gate_require_tradeoff,
        "quality_gate_max_fail_streak": quality_gate_max_fail_streak,
    }
    for key, value in runtime_overrides.items():
        if value is not None:
            updated[key] = value
    return updated


def create_initial_state(parameters: dict[str, object], scenario: str) -> DemoState:
    """Create initial state for a scenario."""
    max_iterations = 0 if scenario == "simple" else int(parameters["max_iterations"])
    return cast(
        DemoState,
        {
            "topic": str(parameters["topic"]),
            "iterations": 0,
            "max_iterations": max_iterations,
            "quality_score": 0.0,
            "analysis": "",
            "analysis_history": [],
            "reflection_labels": [],
            "quality_evaluations": [],
            "draft": "",
            "final": "",
            "ready_to_draft": False,
            "duplicate_streak": 0,
            "quality_delta_streak": 0,
            "last_quality_score": 0.0,
            "routing_reason": "",
            "no_improvement_rewrite_used": False,
            "quality_threshold": float(parameters["quality_threshold"]),
            "quality_gate_novelty_threshold": float(parameters["quality_gate_novelty_threshold"]),
            "quality_gate_coverage_threshold": float(parameters["quality_gate_coverage_threshold"]),
            "quality_gate_min_evidence_count": int(parameters["quality_gate_min_evidence_count"]),
            "quality_gate_require_tradeoff": bool(parameters["quality_gate_require_tradeoff"]),
            "quality_gate_max_fail_streak": int(parameters["quality_gate_max_fail_streak"]),
            "quality_gate_fail_streak": 0,
        },
    )


def register_scenario_graph(
    workflow: object, scenario: str, tracer: LangGraphTracer, end_marker: object
) -> None:
    """Register scenario-specific nodes and edges on a StateGraph-like object."""

    async def analyze_wrapper(state: DemoState) -> DemoState:
        return await llm_analyze(state, tracer)

    async def evaluate_wrapper(state: DemoState) -> DemoState:
        return await llm_evaluate(state, tracer)

    async def reflect_wrapper(state: DemoState) -> DemoState:
        return await llm_reflect(state, tracer)

    async def draft_wrapper(state: DemoState) -> DemoState:
        return await llm_draft(state, tracer)

    async def finalize_wrapper(state: DemoState) -> DemoState:
        return await llm_finalize(state, tracer)

    if scenario == "simple":
        workflow.add_node("analyzer.analyze", analyze_wrapper)
        workflow.add_node("drafter.draft", draft_wrapper)
        workflow.add_node("drafter.finalize", finalize_wrapper)
        workflow.set_entry_point("analyzer.analyze")
        workflow.add_edge("analyzer.analyze", "drafter.draft")
        workflow.add_edge("drafter.draft", "drafter.finalize")
        workflow.add_edge("drafter.finalize", end_marker)
        return

    if scenario == "loop":
        workflow.add_node("analyzer.analyze", analyze_wrapper)
        workflow.add_node("evaluator.evaluate", evaluate_wrapper)
        workflow.add_node("reflector.reflect", reflect_wrapper)
        workflow.add_node("drafter.finalize", finalize_wrapper)
        workflow.set_entry_point("analyzer.analyze")

        def should_reflect_or_finalize(
            state: DemoState,
        ) -> Literal["analyzer.analyze", "reflector.reflect", "drafter.finalize"]:
            if state.get("routing_reason", "") == "force_reanalyze_after_no_improvement":
                return "analyzer.analyze"
            if state.get("ready_to_draft", False):
                return "drafter.finalize"
            return "reflector.reflect"

        workflow.add_edge("analyzer.analyze", "evaluator.evaluate")
        workflow.add_conditional_edges("evaluator.evaluate", should_reflect_or_finalize)
        workflow.add_edge("reflector.reflect", "analyzer.analyze")
        workflow.add_edge("drafter.finalize", end_marker)
        return

    workflow.add_node("analyzer.analyze", analyze_wrapper)
    workflow.add_node("evaluator.evaluate", evaluate_wrapper)
    workflow.add_node("reflector.reflect", reflect_wrapper)
    workflow.add_node("drafter.draft", draft_wrapper)
    workflow.add_node("drafter.finalize", finalize_wrapper)
    workflow.set_entry_point("analyzer.analyze")

    def should_reflect_or_draft(
        state: DemoState,
    ) -> Literal["analyzer.analyze", "reflector.reflect", "drafter.draft"]:
        if state.get("routing_reason", "") == "force_reanalyze_after_no_improvement":
            return "analyzer.analyze"
        if state.get("ready_to_draft", False):
            return "drafter.draft"
        return "reflector.reflect"

    def always_analyze(state: DemoState) -> Literal["analyzer.analyze"]:
        del state
        return "analyzer.analyze"

    workflow.add_edge("analyzer.analyze", "evaluator.evaluate")
    workflow.add_conditional_edges("evaluator.evaluate", should_reflect_or_draft)
    workflow.add_conditional_edges("reflector.reflect", always_analyze)
    workflow.add_edge("drafter.draft", "drafter.finalize")
    workflow.add_edge("drafter.finalize", end_marker)


__all__ = [
    "default_parameters_for_scenario",
    "apply_parameter_overrides",
    "create_initial_state",
    "register_scenario_graph",
]
