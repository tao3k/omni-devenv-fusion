"""Tests for demo tracer skill command wrapper."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_run_langgraph_delegates_to_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skill command should delegate execution to packaged demo runtime."""
    import demo.scripts.tracer as tracer_module

    captured: dict[str, object] = {}

    async def fake_run_graphflow_pipeline(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "success", "scenario": kwargs["scenario"]}

    monkeypatch.setattr(tracer_module, "run_graphflow_pipeline", fake_run_graphflow_pipeline)

    result = await tracer_module.run_langgraph(
        scenario="loop",
        quality_threshold=0.75,
        quality_gate_novelty_threshold=0.2,
        quality_gate_coverage_threshold=0.8,
        quality_gate_min_evidence_count=2,
        quality_gate_require_tradeoff=True,
        quality_gate_max_fail_streak=3,
    )

    assert result == {"status": "success", "scenario": "loop"}
    assert captured == {
        "scenario": "loop",
        "quality_threshold": 0.75,
        "quality_gate_novelty_threshold": 0.2,
        "quality_gate_coverage_threshold": 0.8,
        "quality_gate_min_evidence_count": 2,
        "quality_gate_require_tradeoff": True,
        "quality_gate_max_fail_streak": 3,
    }
