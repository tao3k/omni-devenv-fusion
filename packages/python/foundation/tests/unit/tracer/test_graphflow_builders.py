"""Tests for graphflow workflow builders."""

from __future__ import annotations

from omni.tracer.graphflow.builders import (
    apply_parameter_overrides,
    create_initial_state,
    default_parameters_for_scenario,
)


def test_default_parameters_for_simple_scenario() -> None:
    params = default_parameters_for_scenario("simple")
    assert params["quality_gate_novelty_threshold"] == 0.10
    assert params["quality_gate_coverage_threshold"] == 0.60
    assert params["quality_gate_max_fail_streak"] == 1


def test_default_parameters_fallback_to_complex() -> None:
    params = default_parameters_for_scenario("unknown")
    assert params["quality_gate_novelty_threshold"] == 0.20
    assert params["quality_gate_coverage_threshold"] == 0.80


def test_apply_parameter_overrides_updates_only_specified_values() -> None:
    base = default_parameters_for_scenario("loop")
    updated = apply_parameter_overrides(
        base,
        quality_threshold=0.9,
        quality_gate_min_evidence_count=3,
    )
    assert updated["quality_threshold"] == 0.9
    assert updated["quality_gate_min_evidence_count"] == 3
    assert updated["quality_gate_coverage_threshold"] == base["quality_gate_coverage_threshold"]


def test_create_initial_state_sets_iteration_mode_by_scenario() -> None:
    params = default_parameters_for_scenario("complex")
    simple_state = create_initial_state(params, "simple")
    loop_state = create_initial_state(params, "loop")

    assert simple_state["max_iterations"] == 0
    assert loop_state["max_iterations"] == int(params["max_iterations"])
    assert simple_state["topic"] == "Why use typed languages?"
