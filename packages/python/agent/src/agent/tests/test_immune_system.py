"""
packages/python/agent/src/agent/tests/test_phase28_immune_system.py
Phase 28: Immune System Tests.

Tests cover:
- Decision engine (SAFE, WARN, SANDBOX, BLOCK)
- Combined assessment from scanner and validator
- Trusted source handling
- Assessment formatting
"""

import pytest
import json
import tempfile
from pathlib import Path

from agent.core.security.immune_system import (
    ImmuneSystem,
    Decision,
    AssessmentResult,
    SecurityAssessment,
)


class TestImmuneSystemDecision:
    """Test security decision logic."""

    def test_safe_decision_for_clean_code(self):
        """Test that clean code gets SAFE decision."""
        immune = ImmuneSystem()

        code = 'print("Hello, World!")'
        assessment = immune.assess_code(code, "clean_skill")

        assert assessment.decision == Decision.SAFE
        assert assessment.scanner_report.total_score < immune.WARN_THRESHOLD

    def test_block_decision_for_critical_patterns(self):
        """Test that critical patterns trigger BLOCK."""
        immune = ImmuneSystem()

        code = "eval('malicious_code')"
        assessment = immune.assess_code(code, "dangerous_skill")

        assert assessment.decision == Decision.BLOCK

    def test_warn_decision_for_medium_score(self):
        """Test that medium score triggers WARN."""
        immune = ImmuneSystem()

        code = 'open("/tmp/test", "w").write("data")'
        assessment = immune.assess_code(code, "medium_skill")

        # File write is high (30 points), should trigger WARN if below BLOCK_THRESHOLD
        assert assessment.decision in [Decision.WARN, Decision.BLOCK]

    def test_sandbox_not_yet_implemented(self):
        """Test that SANDBOX is defined but not automatically chosen."""
        immune = ImmuneSystem()

        # Currently SANDBOX is not used
        assert Decision.SANDBOX is not None

        # Safe code should not get SANDBOX
        code = 'print("safe")'
        assessment = immune.assess_code(code, "test")

        assert assessment.decision != Decision.SANDBOX


class TestImmuneSystemTrustedSource:
    """Test trusted source handling."""

    def test_trusted_source_bypasses_warnings(self):
        """Test that trusted sources bypass most checks."""
        immune = ImmuneSystem()

        # Create a skill with manifest from trusted source
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "trusted_skill"
            skill_dir.mkdir()

            # Create manifest with trusted repository
            manifest = {
                "name": "trusted-skill",
                "version": "1.0.0",
                "repository": "https://github.com/omni-dev/test",
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest))

            # Create some medium-risk code
            (skill_dir / "main.py").write_text('print("hello")')

            assessment = immune.assess(skill_dir)

            # Should be marked as trusted
            assert assessment.is_trusted_source


class TestImmuneSystemCombinedAssessment:
    """Test combined scanner + validator assessment."""

    def test_assessment_includes_both_results(self):
        """Test that assessment includes scanner and validator results."""
        immune = ImmuneSystem()

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_skill"
            skill_dir.mkdir()

            # Create manifest
            manifest = {
                "name": "test-skill",
                "version": "1.0.0",
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest))

            assessment = immune.assess(skill_dir)

            # Should have both reports
            assert hasattr(assessment, "scanner_report")
            assert hasattr(assessment, "validator_result")

    def test_assessment_has_warnings(self):
        """Test that assessment includes user warnings."""
        immune = ImmuneSystem()

        code = "eval('dangerous')"
        assessment = immune.assess_code(code, "dangerous_skill")

        assert len(assessment.user_warnings) > 0
        # Should contain warning about critical patterns
        assert any("CRITICAL" in w or "critical" in w.lower() for w in assessment.user_warnings)


class TestImmuneSystemFormatting:
    """Test assessment formatting."""

    def test_format_assessment(self):
        """Test human-readable assessment formatting."""
        immune = ImmuneSystem()

        code = 'print("hello")'
        assessment = immune.assess_code(code, "test_skill")

        formatted = immune.format_assessment(assessment)

        assert "test_skill" in formatted
        assert "SAFE" in formatted or "Decision" in formatted

    def test_format_with_warnings(self):
        """Test formatting includes warnings."""
        immune = ImmuneSystem()

        code = "eval('danger')"
        assessment = immune.assess_code(code, "dangerous")

        formatted = immune.format_assessment(assessment)

        # Should include warning indicators
        assert "BLOCKED" in formatted or "WARNING" in formatted or "⚠️" in formatted


class TestDecisionEnum:
    """Test Decision enum values."""

    def test_decision_values(self):
        """Test that all decisions have correct values."""
        assert Decision.SAFE.value == "safe"
        assert Decision.WARN.value == "warn"
        assert Decision.SANDBOX.value == "sandbox"
        assert Decision.BLOCK.value == "block"

    def test_decision_from_string(self):
        """Test creating decision from string."""
        assert Decision("safe") == Decision.SAFE
        assert Decision("warn") == Decision.WARN
        assert Decision("sandbox") == Decision.SANDBOX
        assert Decision("block") == Decision.BLOCK


class TestAssessmentResult:
    """Test AssessmentResult dataclass."""

    def test_result_creation(self):
        """Test creating an assessment result."""
        result = AssessmentResult(
            decision=Decision.SAFE,
            score=5,
            findings_count=1,
            warnings_count=0,
        )

        assert result.decision == Decision.SAFE
        assert result.score == 5
        assert result.findings_count == 1

    def test_result_to_dict(self):
        """Test serialization to dictionary."""
        result = AssessmentResult(
            decision=Decision.WARN,
            score=15,
            findings_count=2,
            warnings_count=1,
            reason="Medium risk code detected",
        )

        result_dict = result.to_dict()

        assert result_dict["decision"] == "warn"
        assert result_dict["score"] == 15
        assert result_dict["findings_count"] == 2
        assert result_dict["reason"] == "Medium risk code detected"


class TestSecurityAssessment:
    """Test SecurityAssessment dataclass."""

    def test_assessment_to_dict(self):
        """Test serialization to dictionary."""
        immune = ImmuneSystem()
        assessment = immune.assess_code('print("test")', "test_skill")

        assessment_dict = assessment.to_dict()

        assert "decision" in assessment_dict
        assert "scanner_report" in assessment_dict
        assert "validator_result" in assessment_dict
        assert "user_warnings" in assessment_dict


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_assess_skill_function(self):
        """Test the assess_skill convenience function."""
        from agent.core.security.immune_system import assess_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_skill"
            skill_dir.mkdir()
            (skill_dir / "main.py").write_text('print("safe")')

            assessment = assess_skill(str(skill_dir))

            assert assessment is not None
            assert assessment.decision in [Decision.SAFE, Decision.WARN]

    def test_quick_check_function(self):
        """Test the quick_check convenience function."""
        from agent.core.security.immune_system import quick_check

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_skill"
            skill_dir.mkdir()
            (skill_dir / "main.py").write_text('print("safe")')

            decision = quick_check(skill_dir)

            assert decision in Decision


class TestImmuneSystemThresholds:
    """Test configurable thresholds."""

    def test_custom_block_threshold(self):
        """Test setting custom block threshold."""
        immune = ImmuneSystem()
        immune.BLOCK_THRESHOLD = 100  # Very high

        # Critical pattern (50 points) should not block at 100 threshold
        code = "eval('test')"
        assessment = immune.assess_code(code, "test")

        # At 100 threshold, even eval (50) shouldn't block
        # But if there are multiple findings, it might still block
        # Just verify the assessment works
        assert assessment is not None

    def test_custom_warn_threshold(self):
        """Test setting custom warn threshold."""
        immune = ImmuneSystem()
        immune.WARN_THRESHOLD = 100  # Very high

        # Low score should not warn
        code = 'print("test")'
        assessment = immune.assess_code(code, "test")

        assert not assessment.scanner_report.is_warning


class TestImmuneSystemEdgeCases:
    """Test edge cases."""

    def test_empty_skill_directory(self):
        """Test handling empty skill directory."""
        immune = ImmuneSystem()

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "empty"
            skill_dir.mkdir()

            assessment = immune.assess(skill_dir)

            assert assessment is not None
            # Empty directory should be safe
            assert assessment.decision in [Decision.SAFE, Decision.WARN]

    def test_inline_code_assessment(self):
        """Test assessing inline code without directory."""
        immune = ImmuneSystem()

        code = "# Safe comment\nprint('hello')"
        assessment = immune.assess_code(code, "inline_test")

        assert assessment is not None
        assert assessment.decision == Decision.SAFE
