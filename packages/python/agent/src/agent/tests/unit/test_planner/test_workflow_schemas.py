"""
test_workflow_schemas.py
Phase 61: Tests for Dynamic Workflow Schemas (WorkflowNode, WorkflowEdge, WorkflowBlueprint).
"""

import pytest

from agent.core.planner.schemas import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowBlueprint,
)


class TestWorkflowNode:
    """Tests for WorkflowNode."""

    def test_skill_node_creation(self):
        """Test creating a skill node."""
        node = WorkflowNode(
            id="read_file",
            type="skill",
            target="filesystem.read_file",
            fixed_args={"path": "main.py"},
        )
        assert node.id == "read_file"
        assert node.type == "skill"
        assert node.target == "filesystem.read_file"
        assert node.fixed_args["path"] == "main.py"

    def test_node_with_state_inputs(self):
        """Test node with state input mapping."""
        node = WorkflowNode(
            id="analyze",
            type="skill",
            target="code_insight.analyze",
            state_inputs={"file_content": "code"},
        )
        assert node.state_inputs["file_content"] == "code"

    def test_node_defaults(self):
        """Test node default values."""
        node = WorkflowNode(id="test", type="skill", target="test.cmd")
        assert node.fixed_args == {}
        assert node.state_inputs == {}


class TestWorkflowEdge:
    """Tests for WorkflowEdge."""

    def test_simple_edge(self):
        """Test creating a simple edge."""
        edge = WorkflowEdge(source="node_a", target="node_b")
        assert edge.source == "node_a"
        assert edge.target == "node_b"
        assert edge.condition is None

    def test_edge_with_condition(self):
        """Test edge with condition."""
        edge = WorkflowEdge(
            source="analyze",
            target="fix",
            condition="result.needs_fix",
        )
        assert edge.condition == "result.needs_fix"


class TestWorkflowBlueprint:
    """Tests for WorkflowBlueprint."""

    def test_blueprint_creation(self):
        """Test creating a workflow blueprint."""
        nodes = [
            WorkflowNode(id="read", type="skill", target="filesystem.read_file"),
            WorkflowNode(id="analyze", type="skill", target="code_insight.analyze"),
        ]
        edges = [
            WorkflowEdge(source="read", target="analyze"),
        ]

        blueprint = WorkflowBlueprint(
            name="read_and_analyze",
            description="Read file and analyze it",
            nodes=nodes,
            edges=edges,
            entry_point="read",
        )

        assert blueprint.name == "read_and_analyze"
        assert len(blueprint.nodes) == 2
        assert len(blueprint.edges) == 1
        assert blueprint.entry_point == "read"

    def test_blueprint_to_dict(self):
        """Test blueprint serialization to dictionary."""
        blueprint = WorkflowBlueprint(
            name="test",
            description="Test workflow",
            nodes=[
                WorkflowNode(id="n1", type="skill", target="test.cmd1"),
            ],
            edges=[
                WorkflowEdge(source="n1", target="n2"),
            ],
            entry_point="n1",
        )

        data = blueprint.to_dict()

        assert data["name"] == "test"
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["entry_point"] == "n1"

    def test_empty_blueprint(self):
        """Test blueprint with no nodes (edge case)."""
        blueprint = WorkflowBlueprint(
            name="empty",
            description="Empty workflow",
            nodes=[],
            edges=[],
            entry_point="",
        )
        assert len(blueprint.nodes) == 0
        assert len(blueprint.edges) == 0


class TestWorkflowSchemaIntegration:
    """Integration tests for workflow schemas."""

    def test_complex_workflow_blueprint(self):
        """Test a complex workflow with multiple nodes and branching."""
        nodes = [
            WorkflowNode(
                id="fetch_1",
                type="skill",
                target="filesystem.read_file",
                fixed_args={"path": "file1.py"},
            ),
            WorkflowNode(
                id="fetch_2",
                type="skill",
                target="filesystem.read_file",
                fixed_args={"path": "file2.py"},
            ),
            WorkflowNode(
                id="analyze",
                type="skill",
                target="code_insight.analyze",
                state_inputs={"content": "code"},
            ),
            WorkflowNode(
                id="fix",
                type="skill",
                target="omni_edit.apply_fix",
            ),
        ]

        edges = [
            WorkflowEdge(source="fetch_1", target="analyze"),
            WorkflowEdge(source="fetch_2", target="analyze"),
            WorkflowEdge(
                source="analyze",
                target="fix",
                condition="analysis.needs_fix",
            ),
        ]

        blueprint = WorkflowBlueprint(
            name="parallel_fetch_and_analyze",
            description="Fetch multiple files in parallel, then analyze",
            nodes=nodes,
            edges=edges,
            entry_point="fetch_1",
        )

        assert len(blueprint.nodes) == 4
        assert len(blueprint.edges) == 3

        # Verify node by ID
        analyze_node = next(n for n in blueprint.nodes if n.id == "analyze")
        assert analyze_node.type == "skill"
        assert analyze_node.target == "code_insight.analyze"
