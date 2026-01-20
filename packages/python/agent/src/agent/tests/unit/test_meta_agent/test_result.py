"""test_result.py - GenerationResult Tests"""

import pytest
from dataclasses import is_dataclass

from agent.core.meta_agent import GenerationResult


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_is_dataclass(self):
        """GenerationResult should be a dataclass."""
        assert is_dataclass(GenerationResult)

    def test_minimal_creation(self):
        """Should be able to create with minimal required fields."""
        result = GenerationResult(success=True, skill_name="test_skill")
        assert result.success is True
        assert result.skill_name == "test_skill"
        assert result.skill_code is None
        assert result.test_code is None
        assert result.validation_attempts == 0
        assert result.validation_success is False
        assert result.duration_ms == 0.0
        assert result.error is None

    def test_full_creation(self):
        """Should be able to create with all fields."""
        result = GenerationResult(
            success=True,
            skill_name="csv_parser",
            skill_code="import csv",
            test_code="import pytest",
            validation_attempts=2,
            validation_success=True,
            duration_ms=1500.5,
            error=None,
        )
        assert result.success is True
        assert result.skill_name == "csv_parser"
        assert result.skill_code == "import csv"
        assert result.test_code == "import pytest"
        assert result.validation_attempts == 2
        assert result.validation_success is True
        assert result.duration_ms == 1500.5
        assert result.error is None

    def test_error_state(self):
        """Should handle error state correctly."""
        result = GenerationResult(
            success=False,
            skill_name="failed_skill",
            error="Syntax error in generated code",
        )
        assert result.success is False
        assert result.error == "Syntax error in generated code"
