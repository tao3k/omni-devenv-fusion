"""Tests for memory evolution complex scenario fixtures and runner evidence fields."""

from __future__ import annotations

import importlib.util
import sys
from typing import TYPE_CHECKING

from omni.foundation.runtime.gitops import get_project_root

if TYPE_CHECKING:
    from types import ModuleType


def _load_module() -> ModuleType:
    root = get_project_root()
    script_path = root / "scripts" / "channel" / "test_omni_agent_complex_scenarios.py"
    spec = importlib.util.spec_from_file_location(
        "omni_agent_complex_scenarios_memory", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_memory_evolution_fixture_contains_behavior_steps() -> None:
    module = _load_module()
    fixture_path = (
        get_project_root()
        / "scripts"
        / "channel"
        / "fixtures"
        / "memory_evolution_complex_scenarios.json"
    )

    scenarios = module.load_scenarios(fixture_path)
    assert len(scenarios) == 1

    scenario = scenarios[0]
    assert scenario.scenario_id == "memory_self_correction_high_complexity_dag"
    assert len(scenario.steps) >= 18
    assert scenario.required_quality is not None
    assert scenario.required_quality.min_successful_corrections >= 2
    assert scenario.required_quality.min_recall_credit_events >= 1
    assert scenario.required_quality.min_decay_events >= 1

    natural_language_steps = [step for step in scenario.steps if not step.prompt.startswith("/")]
    assert len(natural_language_steps) >= 10
    assert any(step.expect_bot_regexes for step in natural_language_steps)
    assert any(step.expect_log_regexes for step in natural_language_steps)
    assert any("error_signal" in step.tags for step in scenario.steps)
    assert any("correction_check" in step.tags for step in scenario.steps)


def test_memory_evolution_fixture_complexity_gate() -> None:
    module = _load_module()
    fixture_path = (
        get_project_root()
        / "scripts"
        / "channel"
        / "fixtures"
        / "memory_evolution_complex_scenarios.json"
    )

    scenario = module.load_scenarios(fixture_path)[0]
    requirement = scenario.required_complexity
    assert requirement is not None

    profile = module.compute_complexity_profile(scenario)
    passed, failures = module.evaluate_complexity(profile, requirement)
    assert passed is True
    assert failures == ()


def test_extract_bot_excerpt_prefers_observed_outbound_line() -> None:
    module = _load_module()
    stdout = "\n".join(
        [
            "Blackbox probe succeeded.",
            "Observed outbound bot log:",
            '  2026-02-19 INFO omni_agent: → Bot: "ACK VALKEY POSTGRES"',
        ]
    )
    excerpt = module.extract_bot_excerpt(stdout)
    assert excerpt is not None
    assert "ACK VALKEY POSTGRES" in excerpt


def test_detect_memory_event_flags_sets_expected_bits() -> None:
    module = _load_module()
    stdout = " ".join(
        [
            'event="agent.memory.recall.planned"',
            'event="agent.memory.recall.injected"',
            'event="agent.memory.recall.feedback_updated"',
        ]
    )
    flags = module.detect_memory_event_flags(stdout)
    assert flags == (True, True, False, True)
