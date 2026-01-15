"""
test_graph_skill.py
Phase 62: Tests for GraphSkill Base Class (Standardized Subgraph Skills).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from agent.core.skill_manager.graph_skill import GraphSkill, create_graph_skill_from_blueprint
from agent.core.orchestrator.dynamic_builder import DynamicGraphBuilder


class SimpleGraphSkill(GraphSkill):
    """A simple test graph skill."""

    name = "simple_test"
    description = "A simple test skill"

    def build_graph(self, builder: DynamicGraphBuilder) -> None:
        builder.add_skill_node("echo", "filesystem", "echo")
        builder.set_entry_point("echo")


class MultiStepGraphSkill(GraphSkill):
    """A multi-step test graph skill."""

    name = "multi_step_test"
    description = "A multi-step test skill"

    def build_graph(self, builder: DynamicGraphBuilder) -> None:
        builder.add_skill_node("step1", "filesystem", "echo")
        builder.add_skill_node("step2", "filesystem", "echo")
        builder.add_edge("step1", "step2")
        builder.set_entry_point("step1")


class TestGraphSkill:
    """Tests for GraphSkill base class."""

    def test_graph_skill_creation(self):
        """Test creating a graph skill instance."""
        skill = SimpleGraphSkill()
        assert skill.name == "simple_test"
        assert skill.description == "A simple test skill"

    def test_graph_skill_default_values(self):
        """Test default attribute values."""
        # GraphSkill is abstract, so we test the class attributes directly
        assert GraphSkill.name == "graph_skill"
        assert GraphSkill.description == "A composite skill"
        assert GraphSkill.required_skills == []
        assert GraphSkill.input_schema == {}
        assert GraphSkill.output_schema == {}

    def test_graph_skill_with_skill_manager(self):
        """Test graph skill with skill manager."""
        mock_manager = MagicMock()
        skill = SimpleGraphSkill(skill_manager=mock_manager)
        assert skill.get_skill_manager() is mock_manager

    def test_graph_skill_set_skill_manager(self):
        """Test setting skill manager."""
        skill = SimpleGraphSkill()
        mock_manager = MagicMock()
        skill.set_skill_manager(mock_manager)
        assert skill.get_skill_manager() is mock_manager

    def test_get_info(self):
        """Test get_info returns correct data."""
        skill = SimpleGraphSkill()
        info = skill.get_info()

        assert info["name"] == "simple_test"
        assert info["description"] == "A simple test skill"
        assert info["type"] == "graph_skill"
        assert info["required_skills"] == []
        assert info["input_schema"] == {}
        assert info["output_schema"] == {}

    def test_validate_input_no_schema(self):
        """Test validation passes with no schema."""
        skill = SimpleGraphSkill()
        assert skill.validate_input({"any": "data"}) is True

    def test_validate_input_with_required_fields(self):
        """Test input validation with required fields."""
        skill = MultiStepGraphSkill()
        skill.input_schema = {"required": ["file_path"]}

        # Should pass
        assert skill.validate_input({"file_path": "main.py"}) is True

        # Should fail - missing required field
        assert skill.validate_input({"other": "value"}) is False

    def test_validate_output_no_schema(self):
        """Test output validation passes with no schema."""
        skill = SimpleGraphSkill()
        assert skill.validate_output({"any": "data"}) is True

    def test_validate_output_with_required_fields(self):
        """Test output validation with required fields."""
        skill = MultiStepGraphSkill()
        skill.output_schema = {"required": ["result"]}

        # Should pass
        assert skill.validate_output({"result": "success"}) is True

        # Should fail - missing required field
        assert skill.validate_output({"other": "value"}) is False


class TestGraphSkillCompilation:
    """Tests for GraphSkill graph compilation."""

    def test_compile_simple_graph(self):
        """Test compiling a simple graph."""
        mock_manager = MagicMock()
        skill = SimpleGraphSkill(skill_manager=mock_manager)

        graph = skill.compile()

        # Should return a compiled graph
        assert graph is not None
        assert skill._compiled_graph is not None


class TestDynamicGraphSkill:
    """Tests for dynamically created graph skills from blueprints."""

    def test_create_from_empty_blueprint(self):
        """Test creating a graph skill from an empty blueprint."""
        from agent.core.planner.schemas import WorkflowBlueprint

        mock_manager = MagicMock()

        # Create an empty blueprint
        blueprint = WorkflowBlueprint(
            name="empty_workflow",
            description="Empty test workflow",
            nodes=[],
            edges=[],
            entry_point="",
        )

        # This should create a skill that compiles successfully
        skill = create_graph_skill_from_blueprint(blueprint, mock_manager)

        assert skill.name == "empty_workflow"
        assert skill.description == "Empty test workflow"

    def test_create_from_simple_blueprint(self):
        """Test creating a graph skill from a simple blueprint."""
        from agent.core.planner.schemas import WorkflowBlueprint, WorkflowNode, WorkflowEdge

        mock_manager = MagicMock()

        blueprint = WorkflowBlueprint(
            name="simple_workflow",
            description="Simple test workflow",
            nodes=[
                WorkflowNode(
                    id="read_file",
                    type="skill",
                    target="filesystem.read_file",
                    fixed_args={"path": "main.py"},
                ),
            ],
            edges=[],
            entry_point="read_file",
        )

        skill = create_graph_skill_from_blueprint(blueprint, mock_manager)

        assert skill.name == "simple_workflow"
        assert skill.description == "Simple test workflow"

        # Should be able to compile
        graph = skill.compile()
        assert graph is not None

    def test_create_from_multi_node_blueprint(self):
        """Test creating a graph skill from a multi-node blueprint."""
        from agent.core.planner.schemas import WorkflowBlueprint, WorkflowNode, WorkflowEdge

        mock_manager = MagicMock()

        blueprint = WorkflowBlueprint(
            name="multi_node_workflow",
            description="Multi-node test workflow",
            nodes=[
                WorkflowNode(
                    id="step1",
                    type="skill",
                    target="filesystem.echo",
                ),
                WorkflowNode(
                    id="step2",
                    type="skill",
                    target="filesystem.echo",
                ),
                WorkflowNode(
                    id="step3",
                    type="skill",
                    target="filesystem.echo",
                ),
            ],
            edges=[
                WorkflowEdge(source="step1", target="step2"),
                WorkflowEdge(source="step2", target="step3"),
            ],
            entry_point="step1",
        )

        skill = create_graph_skill_from_blueprint(blueprint, mock_manager)

        assert skill.name == "multi_node_workflow"

        # Should be able to compile
        graph = skill.compile()
        assert graph is not None


class TestGraphSkillExecution:
    """Tests for GraphSkill execution (mocked)."""

    @pytest.mark.asyncio
    async def test_run_with_mocked_graph(self):
        """Test running a graph skill with mocked graph."""
        mock_manager = MagicMock()

        skill = SimpleGraphSkill(skill_manager=mock_manager)

        # Mock the compiled graph
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=MagicMock(workflow_state={"result": "success"}))
        skill._compiled_graph = mock_graph

        result = await skill.run({"test": "input"})

        # Graph should have been invoked
        mock_graph.ainvoke.assert_called_once()

        # Result should be returned
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_with_precompiled_graph(self):
        """Test running a graph skill with pre-compiled graph."""
        mock_manager = MagicMock()

        skill = SimpleGraphSkill(skill_manager=mock_manager)

        # Pre-compile the graph
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            return_value=MagicMock(workflow_state={"precompiled": "success"})
        )
        skill._compiled_graph = mock_graph

        # Run should use the pre-compiled graph
        result = await skill.run({"test": "input"})

        # Result should be returned
        assert result == {"precompiled": "success"}
