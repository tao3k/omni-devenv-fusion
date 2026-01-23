"""
test_core_builder.py - Tests for DynamicGraphBuilder

Tests for:
- DynamicGraphBuilder node and edge building
- Graph compilation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from omni.langgraph.orchestrator.builder import DynamicGraphBuilder, NodeMetadata


class TestDynamicGraphBuilder:
    """Tests for DynamicGraphBuilder."""

    @pytest.fixture
    def mock_skill_runner(self):
        """Create a mock skill runner."""
        mock = MagicMock()
        mock.run = AsyncMock(return_value="Skill result")
        return mock

    def test_create_builder(self, mock_skill_runner):
        """Should create a builder with skill runner."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)
        assert builder.skill_runner is mock_skill_runner
        assert builder.nodes == {}
        assert builder._entry_point is None

    def test_add_skill_node(self, mock_skill_runner):
        """Should add a skill node."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_skill_node(
            node_name="read_file",
            skill_name="filesystem",
            command_name="read_file",
            fixed_args={"encoding": "utf-8"},
        )

        assert "read_file" in builder.nodes
        node = builder.nodes["read_file"]
        assert node.type == "skill"
        assert node.target == "filesystem.read_file"

    def test_add_skill_node_with_state_mappings(self, mock_skill_runner):
        """Should add a skill node with state input/output mappings."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_skill_node(
            node_name="analyze",
            skill_name="code_insight",
            command_name="analyze",
            state_input={"file_path": "path"},
            state_output={"result": "analysis"},
        )

        assert "analyze" in builder.nodes

    def test_add_function_node(self, mock_skill_runner):
        """Should add a function node."""

        async def my_func(state: Dict[str, Any]) -> Dict[str, Any]:
            return {"result": "processed"}

        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_function_node(
            node_name="process",
            func=my_func,
        )

        assert "process" in builder.nodes
        node = builder.nodes["process"]
        assert node.type == "function"
        assert node.target == "my_func"

    def test_add_sequence(self, mock_skill_runner):
        """Should add sequential edges between nodes."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_skill_node("node_a", "skill1", "cmd1")
        builder.add_skill_node("node_b", "skill2", "cmd2")

        builder.add_sequence("node_a", "node_b")
        builder.set_entry_point("node_a")

        # Verify edges were added
        assert builder._entry_point == "node_a"

    def test_add_conditional_edges(self, mock_skill_runner):
        """Should add conditional edges."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_skill_node("decision", "skill1", "cmd1")
        builder.add_skill_node("fix", "skill2", "cmd2")
        builder.add_skill_node("end", "skill3", "cmd3")

        def should_continue(state: Dict[str, Any]) -> str:
            needs_fix = state.get("scratchpad", [{}])[-1].get("needs_fix", False)
            return "fix" if needs_fix else "__end__"

        builder.add_conditional_edges(
            "decision",
            should_continue,
            {
                "fix": "fix",
                "__end__": "__end__",
            },
        )
        builder.set_entry_point("decision")

    def test_set_entry_point(self, mock_skill_runner):
        """Should set the entry point."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)
        builder.add_skill_node("start_node", "skill1", "cmd1")

        builder.set_entry_point("start_node")

        assert builder._entry_point == "start_node"

    def test_compile_creates_graph(self, mock_skill_runner):
        """Should compile to a CompiledGraph."""
        builder = DynamicGraphBuilder(skill_runner=mock_skill_runner)

        builder.add_skill_node("start", "skill1", "cmd1")
        builder.add_skill_node("end", "skill2", "cmd2")
        builder.add_sequence("start", "end")
        builder.set_entry_point("start")

        graph = builder.compile()

        assert graph is not None


class TestNodeMetadata:
    """Tests for NodeMetadata."""

    def test_create_node_metadata(self):
        """Should create valid node metadata."""
        metadata = NodeMetadata(
            name="test_node",
            type="skill",
            target="filesystem.read_file",
        )

        assert metadata.name == "test_node"
        assert metadata.type == "skill"
        assert metadata.target == "filesystem.read_file"

    def test_node_metadata_with_args(self):
        """Should handle arguments."""
        metadata = NodeMetadata(
            name="test_node",
            type="skill",
            target="filesystem.read_file",
            args={"encoding": "utf-8", "max_lines": 100},
        )

        assert metadata.args["encoding"] == "utf-8"
        assert metadata.args["max_lines"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
