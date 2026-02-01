"""Tests for evolution schemas module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omni.agent.core.evolution.schemas import (
    CandidateSkill,
    SkillTemplateContext,
    CrystallizationResult,
    HarvesterAnalysisResult,
)


class TestCandidateSkill:
    """Tests for CandidateSkill model."""

    def test_create_candidate_skill(self):
        """Test creating a valid CandidateSkill."""
        skill = CandidateSkill(
            suggested_name="batch_file_rename",
            description="Rename files matching a pattern",
            category="file",
            nushell_script="for f in (glob $pattern) { mv $f ($f | str replace $old $new) }",
            parameters={
                "pattern": "File pattern to match",
                "old": "Extension to replace",
                "new": "New extension",
            },
            original_task="Rename all .txt to .md",
            trace_id="trace_123",
            reasoning="Frequently used task",
        )

        assert skill.suggested_name == "batch_file_rename"
        assert skill.category == "file"
        assert len(skill.parameters) == 3
        assert skill.confidence_score == 0.8  # default

    def test_candidate_skill_with_custom_confidence(self):
        """Test creating with custom confidence score."""
        skill = CandidateSkill(
            suggested_name="test_skill",
            description="Test skill",
            category="automation",
            nushell_script="echo test",
            parameters={},
            original_task="test",
            trace_id="t1",
            reasoning="test",
            confidence_score=0.95,
        )

        assert skill.confidence_score == 0.95

    def test_candidate_skill_complexity(self):
        """Test complexity field."""
        skill = CandidateSkill(
            suggested_name="complex_skill",
            description="Complex skill",
            category="data",
            nushell_script="complex script",
            parameters={},
            original_task="task",
            trace_id="t1",
            reasoning="reason",
            estimated_complexity="high",
        )

        assert skill.estimated_complexity == "high"

    def test_candidate_skill_invalid_name(self):
        """Test that invalid names are rejected."""
        with pytest.raises(ValidationError):
            CandidateSkill(
                suggested_name="Invalid Name!",  # Contains invalid chars
                description="Test",
                category="test",
                nushell_script="echo",
                parameters={},
                original_task="task",
                trace_id="t1",
                reasoning="reason",
            )

    def test_candidate_skill_short_description(self):
        """Test that descriptions must be at least 10 chars."""
        with pytest.raises(ValidationError):
            CandidateSkill(
                suggested_name="test_skill",
                description="Short",  # Too short
                category="test",
                nushell_script="echo",
                parameters={},
                original_task="task",
                trace_id="t1",
                reasoning="reason",
            )


class TestSkillTemplateContext:
    """Tests for SkillTemplateContext model."""

    def test_to_template_vars(self):
        """Test conversion to template variables."""
        ctx = SkillTemplateContext(
            skill_name="test_skill",
            skill_description="A test skill",
            category="automation",
            nushell_script="echo test",
            parameters={"param1": "Description"},
            original_task="Test task",
            trace_id="t1",
            reasoning="Testing",
        )

        vars = ctx.to_template_vars()

        assert vars["skill_name"] == "test_skill"
        assert vars["param_names"] == ["param1"]
        assert "param1" in vars["parameters"]


class TestCrystallizationResult:
    """Tests for CrystallizationResult model."""

    def test_success_result(self):
        """Test successful crystallization result."""
        result = CrystallizationResult(
            success=True,
            skill_path="/skills/test",
            skill_name="test_skill",
            files_created=["test.py", "SKILL.md"],
        )

        assert result.success is True
        assert result.skill_path == "/skills/test"
        assert len(result.files_created) == 2
        assert result.error is None

    def test_failure_result(self):
        """Test failed crystallization result."""
        result = CrystallizationResult(
            success=False,
            error="Failed to write file",
        )

        assert result.success is False
        assert result.error == "Failed to write file"
        assert result.skill_path is None

    def test_default_files(self):
        """Test default empty files list."""
        result = CrystallizationResult(success=True)

        assert result.files_created == []


class TestHarvesterAnalysisResult:
    """Tests for HarvesterAnalysisResult model."""

    def test_worthy_analysis(self):
        """Test analysis result for worthy trace."""
        result = HarvesterAnalysisResult(
            trace_id="t1",
            is_worthy=True,
            candidate=CandidateSkill(
                suggested_name="test",
                description="A test skill",
                category="test",
                nushell_script="echo",
                parameters={},
                original_task="task",
                trace_id="t1",
                reasoning="reason",
            ),
            confidence=0.9,
        )

        assert result.is_worthy is True
        assert result.candidate is not None
        assert result.skip_reason is None

    def test_unworthy_analysis(self):
        """Test analysis result for unworthy trace."""
        result = HarvesterAnalysisResult(
            trace_id="t2",
            is_worthy=False,
            skip_reason="Too trivial",
            confidence=0.5,
        )

        assert result.is_worthy is False
        assert result.candidate is None
        assert result.skip_reason == "Too trivial"
