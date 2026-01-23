"""
test_core_graph_skill.py - Tests for GraphSkill Base Class

Tests for:
- GraphSkill base class functionality
- GraphSkill validation methods
- create_graph_skill_from_blueprint factory
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from omni.langgraph.skills.graph_skill import GraphSkill, create_graph_skill_from_blueprint


class SimpleTestSkill(GraphSkill):
    """A simple GraphSkill for testing."""

    name = "test_skill"
    description = "A test skill"

    def build_graph(self, builder):
        """Build a simple two-node graph."""
        builder.add_skill_node("step1", "skill1", "cmd1")
        builder.add_skill_node("step2", "skill2", "cmd2")
        builder.add_sequence("step1", "step2")
        builder.set_entry_point("step1")


class GraphSkillWithValidation(GraphSkill):
    """A GraphSkill with input/output validation."""

    name = "validation_skill"
    description = "A skill with validation"

    input_schema = {
        "type": "object",
        "required": ["task"],
        "properties": {
            "task": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "required": ["result"],
        "properties": {
            "result": {"type": "string"},
        },
    }

    def build_graph(self, builder):
        """Build a simple graph."""
        builder.add_skill_node("do_task", "skill1", "cmd1")
        builder.set_entry_point("do_task")


class TestGraphSkill:
    """Tests for GraphSkill base class."""

    @pytest.fixture
    def mock_skill_runner(self):
        """Create a mock skill runner."""
        mock = MagicMock()
        mock.run = AsyncMock(return_value="result")
        return mock

    def test_create_graph_skill(self, mock_skill_runner):
        """Should create a GraphSkill instance."""
        skill = SimpleTestSkill(skill_runner=mock_skill_runner)

        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.get_skill_runner() is mock_skill_runner

    def test_set_skill_runner(self, mock_skill_runner):
        """Should set skill runner."""
        skill = SimpleTestSkill()
        skill.set_skill_runner(mock_skill_runner)

        assert skill.get_skill_runner() is mock_skill_runner

    def test_compile(self, mock_skill_runner):
        """Should compile the graph."""
        skill = SimpleTestSkill(skill_runner=mock_skill_runner)

        compiled = skill.compile()

        assert compiled is not None
        assert skill._compiled_graph is compiled

    def test_validate_input_valid(self, mock_skill_runner):
        """Should validate valid input."""
        skill = GraphSkillWithValidation(skill_runner=mock_skill_runner)

        result = skill.validate_input({"task": "do something"})

        assert result is True

    def test_validate_input_invalid(self, mock_skill_runner):
        """Should reject invalid input."""
        skill = GraphSkillWithValidation(skill_runner=mock_skill_runner)

        # Missing required field
        result = skill.validate_input({})
        assert result is False

    def test_validate_output_valid(self, mock_skill_runner):
        """Should validate valid output."""
        skill = GraphSkillWithValidation(skill_runner=mock_skill_runner)

        result = skill.validate_output({"result": "done"})
        assert result is True

    def test_validate_output_invalid(self, mock_skill_runner):
        """Should reject invalid output."""
        skill = GraphSkillWithValidation(skill_runner=mock_skill_runner)

        # Missing required field
        result = skill.validate_output({})
        assert result is False

    def test_validate_no_schema(self, mock_skill_runner):
        """Should accept any input when no schema defined."""
        skill = SimpleTestSkill(skill_runner=mock_skill_runner)

        # No schema means always valid
        assert skill.validate_input({}) is True
        assert skill.validate_output({}) is True

    def test_get_info(self, mock_skill_runner):
        """Should return skill information."""
        skill = SimpleTestSkill(skill_runner=mock_skill_runner)

        info = skill.get_info()

        assert info["name"] == "test_skill"
        assert info["description"] == "A test skill"
        assert info["type"] == "graph_skill"


class TestCreateGraphSkillFromBlueprint:
    """Tests for create_graph_skill_from_blueprint factory."""

    @pytest.fixture
    def mock_skill_runner(self):
        """Create a mock skill runner."""
        mock = MagicMock()
        mock.run = AsyncMock(return_value="result")
        return mock

    def test_create_from_blueprint(self, mock_skill_runner):
        """Should create a GraphSkill from a blueprint."""

        # Create a mock blueprint
        class MockBlueprint:
            name = "my_blueprint"
            description = "A blueprint skill"
            required_skills = ["skill1", "skill2"]
            nodes = []
            edges = []
            entry_point = None

        blueprint = MockBlueprint()

        skill = create_graph_skill_from_blueprint(blueprint, mock_skill_runner)

        assert skill.name == "my_blueprint"
        assert skill.description == "A blueprint skill"
        assert skill.required_skills == ["skill1", "skill2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
