"""Tests for evolution skill factory templates."""

from __future__ import annotations

from omni.agent.core.evolution.factory import SkillFactory
from omni.agent.core.evolution.schemas import CandidateSkill


def _candidate() -> CandidateSkill:
    return CandidateSkill(
        suggested_name="typed_language_helper",
        description="Generate concise guidance for typed language adoption.",
        category="knowledge",
        nushell_script='echo "typed languages"',
        parameters={"topic": "Target topic"},
        original_task="Summarize typed language benefits",
        trace_id="trace_123",
        reasoning="High-frequency query with reusable pattern.",
    )


def test_render_python_skill_uses_shared_async_runner(tmp_path) -> None:
    factory = SkillFactory(skills_dir=tmp_path / "skills", quarantine_dir=tmp_path / "quarantine")
    rendered = factory._render_python_skill(
        _candidate(), "typed_language_helper", "2026-02-12T00:00:00"
    )

    assert "from omni.foundation.utils import run_async_blocking" in rendered
    assert "run_async_blocking(typed_language_helper())" in rendered
    assert "asyncio.run(" not in rendered
