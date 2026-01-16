"""
test_dynamic_builder.py
Phase 61: Tests for Dynamic Workflow Builder.

Tests the fluent API for constructing LangGraph state graphs dynamically.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from agent.core.orchestrator.builder import DynamicGraphBuilder, NodeMetadata
from agent.core.state import GraphState


class TestNodeMetadata:
    """Tests for NodeMetadata dataclass."""

    def test_skill_node_metadata(self):
        """Test metadata for a skill node."""
        meta = NodeMetadata(
            name="read_file",
            type="skill",
            target="filesystem.read_file",
            args={"path": "main.py"},
        )
        assert meta.name == "read_file"
        assert meta.type == "skill"
        assert meta.target == "filesystem.read_file"
        assert meta.args["path"] == "main.py"

    def test_function_node_metadata(self):
        """Test metadata for a function node."""

        async def dummy_func():
            pass

        meta = NodeMetadata(
            name="custom",
            type="function",
            target="dummy_func",
        )
        assert meta.type == "function"


class TestDynamicGraphBuilder:
    """Tests for DynamicGraphBuilder fluent API."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="test result")
        return manager

    def test_empty_builder(self, mock_skill_manager):
        """Test creating an empty builder."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        assert builder.nodes == {}
        assert builder._compiled is False

    def test_add_skill_node(self, mock_skill_manager):
        """Test adding a skill node."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node(
            "read_file",
            "filesystem",
            "read_file",
            fixed_args={"path": "main.py"},
        )

        assert "read_file" in builder.nodes
        meta = builder.nodes["read_file"]
        assert meta.type == "skill"
        assert meta.target == "filesystem.read_file"

    def test_add_skill_node_with_state_io(self, mock_skill_manager):
        """Test skill node with state input/output mapping."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node(
            "analyze",
            "code_insight",
            "analyze",
            state_input={"file_path": "path"},
            state_output={"result": "analysis"},
        )

        assert "analyze" in builder.nodes

    def test_add_function_node(self, mock_skill_manager):
        """Test adding a function node."""

        async def custom_node(state):
            return {"output": "custom"}

        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_function_node("custom", custom_node)

        assert "custom" in builder.nodes
        meta = builder.nodes["custom"]
        assert meta.type == "function"

    def test_add_llm_node(self, mock_skill_manager):
        """Test adding an LLM node."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_llm_node(
            "reason",
            prompt_template="Analyze: {{task}}",
            model="gpt-4",
            state_output="reasoning",
        )

        assert "reason" in builder.nodes
        meta = builder.nodes["reason"]
        assert meta.type == "router"
        assert meta.target == "llm:gpt-4"

    def test_set_entry_point(self, mock_skill_manager):
        """Test setting the entry point."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("start", "test", "cmd")
        builder.set_entry_point("start")

        assert builder._entry_point == "start"

    def test_set_entry_point_error(self, mock_skill_manager):
        """Test setting entry point for non-existent node."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        with pytest.raises(ValueError, match="does not exist"):
            builder.set_entry_point("nonexistent")

    def test_add_edge(self, mock_skill_manager):
        """Test adding a direct edge."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("node1", "test", "cmd1")
        builder.add_skill_node("node2", "test", "cmd2")
        builder.add_edge("node1", "node2")

        # Edge added successfully (no exception)
        assert True

    def test_add_edge_to_end(self, mock_skill_manager):
        """Test adding edge to END."""
        from langgraph.graph import END

        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("final", "test", "cmd")
        builder.add_edge("final", END)

        assert True

    def test_add_sequence(self, mock_skill_manager):
        """Test adding a linear sequence."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("step1", "test", "cmd1")
        builder.add_skill_node("step2", "test", "cmd2")
        builder.add_skill_node("step3", "test", "cmd3")
        builder.add_sequence("step1", "step2", "step3")

        # Sequence added successfully
        assert True

    def test_add_sequence_single_node(self, mock_skill_manager):
        """Test sequence with single node (no-op)."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("only", "test", "cmd")
        result = builder.add_sequence("only")

        # Should return self without error
        assert result is builder

    def test_add_conditional_edges(self, mock_skill_manager):
        """Test adding conditional edges."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("decide", "test", "cmd1")
        builder.add_skill_node("path_a", "test", "cmd2")
        builder.add_skill_node("path_b", "test", "cmd3")

        def condition(state):
            return "a" if state.get("choice") == "yes" else "b"

        builder.add_conditional_edges(
            "decide",
            condition,
            {"a": "path_a", "b": "path_b"},
        )

        assert True

    def test_fluent_api_chaining(self, mock_skill_manager):
        """Test fluent API chaining returns self."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        result = builder.add_skill_node("n1", "test", "c1")
        assert result is builder

        result = result.add_skill_node("n2", "test", "c2")
        assert result is builder

        result = result.add_edge("n1", "n2")
        assert result is builder

    def test_duplicate_node_error(self, mock_skill_manager):
        """Test adding duplicate node raises error."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("duplicate", "test", "cmd")

        with pytest.raises(ValueError, match="already exists"):
            builder.add_skill_node("duplicate", "test", "cmd2")


class TestDynamicGraphBuilderCompilation:
    """Tests for graph compilation."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="test result")
        return manager

    def test_compile_single_node(self, mock_skill_manager):
        """Test compiling a single node graph."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node("only", "test", "cmd")
        builder.set_entry_point("only")

        # Should compile without error
        graph = builder.compile()
        assert graph is not None

    def test_compile_linear_graph(self, mock_skill_manager):
        """Test compiling a linear sequence."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node("step1", "test", "cmd1")
        builder.add_skill_node("step2", "test", "cmd2")
        builder.add_sequence("step1", "step2")
        builder.set_entry_point("step1")

        graph = builder.compile()
        assert graph is not None

    def test_compile_already_compiled_error(self, mock_skill_manager):
        """Test compiling twice raises error."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node("only", "test", "cmd")
        builder.set_entry_point("only")

        builder.compile()

        with pytest.raises(RuntimeError, match="already compiled"):
            builder.compile()


class TestDynamicGraphBuilderVisualize:
    """Tests for graph visualization."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="test result")
        return manager

    def test_visualize_empty(self, mock_skill_manager):
        """Test visualizing empty graph."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        diagram = builder.visualize()

        assert "```mermaid" in diagram
        assert "graph TD" in diagram
        assert "```" in diagram

    def test_visualize_with_nodes(self, mock_skill_manager):
        """Test visualizing graph with nodes."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node("read_file", "filesystem", "read_file")
        builder.add_skill_node("analyze", "code_insight", "analyze")

        diagram = builder.visualize()

        assert "read_file" in diagram
        assert "analyze" in diagram


class TestDynamicGraphBuilderExecution:
    """Tests for graph execution (integration tests)."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="test result")
        return manager

    @pytest.mark.asyncio
    async def test_execute_skill_node(self, mock_skill_manager):
        """Test executing a skill node through the graph."""
        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node("test_node", "test", "cmd", fixed_args={"arg": "value"})
        builder.set_entry_point("test_node")

        graph = builder.compile()

        initial_state: GraphState = {
            "messages": [],
            "context_ids": [],
            "current_plan": "",
            "error_count": 0,
            "workflow_state": {},
        }

        result = await graph.ainvoke(initial_state)

        # Verify skill was called
        mock_skill_manager.run.assert_called_once_with("test", "cmd", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_execute_with_state_input(self, mock_skill_manager):
        """Test skill node reads from state."""
        mock_skill_manager.run = AsyncMock(return_value="file content")

        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node(
            "read_file",
            "filesystem",
            "read_file",
            state_input={"current_plan": "path"},  # Use existing GraphState field
        )
        builder.set_entry_point("read_file")

        graph = builder.compile()

        initial_state: GraphState = {
            "messages": [],
            "context_ids": [],
            "current_plan": "/path/to/file.py",
            "error_count": 0,
            "workflow_state": {},
        }

        await graph.ainvoke(initial_state)

        # Verify the state input was used
        mock_skill_manager.run.assert_called_once_with(
            "filesystem", "read_file", {"path": "/path/to/file.py"}
        )

    @pytest.mark.asyncio
    async def test_execute_with_state_output(self, mock_skill_manager):
        """Test skill node writes to state."""
        mock_skill_manager.run = AsyncMock(return_value="analysis result")

        builder = DynamicGraphBuilder(mock_skill_manager)
        builder.add_skill_node(
            "analyze",
            "code_insight",
            "analyze",
        )
        builder.set_entry_point("analyze")

        graph = builder.compile()

        initial_state: GraphState = {
            "messages": [],
            "context_ids": [],
            "current_plan": "",
            "error_count": 0,
            "workflow_state": {},
        }

        result = await graph.ainvoke(initial_state)

        # Verify skill was called
        mock_skill_manager.run.assert_called_once_with("code_insight", "analyze", {})


class TestDynamicGraphBuilderInterrupt:
    """Tests for Human-in-the-Loop interrupt functionality."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="test result")
        return manager

    def test_compile_with_interrupt_before(self, mock_skill_manager):
        """Test compiling graph with interrupt_before."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("step1", "test", "cmd1")
        builder.add_skill_node("step2", "test", "cmd2")
        builder.add_sequence("step1", "step2")
        builder.set_entry_point("step1")

        # Compile with interrupt before step2
        graph = builder.compile(interrupt_before=["step2"])

        assert graph is not None
        # The compiled graph should have interrupt_before configured

    def test_compile_with_multiple_interrupts(self, mock_skill_manager):
        """Test compiling graph with multiple interrupt points."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("step1", "test", "cmd1")
        builder.add_skill_node("step2", "test", "cmd2")
        builder.add_skill_node("step3", "test", "cmd3")
        builder.add_sequence("step1", "step2", "step3")
        builder.set_entry_point("step1")

        # Compile with interrupts before step2 and step3
        graph = builder.compile(interrupt_before=["step2", "step3"])

        assert graph is not None


class TestUpdateCommitScenario:
    """
    Test "Update & Commit" scenario: filesystem read → LLM generate → filesystem write → git stage → git commit

    This tests the core Smart Commit workflow using DynamicGraphBuilder.
    """

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager for Update & Commit scenario."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"content": "test file content"})
        return manager

    def test_build_update_commit_graph(self, mock_skill_manager):
        """Test building the Update & Commit workflow graph."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        # Step 1: Read file
        builder.add_skill_node(
            "read_file",
            "filesystem",
            "read_file",
            fixed_args={"path": "docs/index.md"},
            state_output={"content": "file_content"},
        )

        # Step 2: Generate update (LLM)
        builder.add_llm_node(
            "generate_update",
            prompt_template="""
            Original Content:
            {{file_content}}

            Instruction: Update the status to "Omni-Dev 1.0 is ready."

            Output the FULL updated file content only.
            """,
            model="default",
            state_output="new_content",
        )

        # Step 3: Write file
        builder.add_skill_node(
            "write_file",
            "filesystem",
            "write_file",
            state_input={"content": "new_content"},
        )

        # Step 4: Git prepare (stage and scan)
        builder.add_skill_node(
            "git_prepare",
            "git",
            "stage_and_scan",
            state_output={"diff_preview": "diff"},
        )

        # Step 5: Git commit (with interrupt)
        builder.add_skill_node(
            "git_commit",
            "git",
            "commit",
            fixed_args={"message": "docs: update index with 1.0 status"},
        )

        # Define sequence: read → generate → write → git_prepare → git_commit
        builder.add_sequence(
            "read_file",
            "generate_update",
            "write_file",
            "git_prepare",
            "git_commit",
        )

        builder.set_entry_point("read_file")

        # Compile with interrupt before git_commit (Human-in-the-Loop)
        graph = builder.compile(interrupt_before=["git_commit"])

        assert graph is not None
        assert len(builder.nodes) == 5

    def test_update_commit_visualize(self, mock_skill_manager):
        """Test visualizing the Update & Commit graph."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        # Build simple version of the graph
        builder.add_skill_node("read_file", "filesystem", "read_file")
        builder.add_skill_node("write_file", "filesystem", "write_file")
        builder.add_skill_node("git_commit", "git", "commit")

        builder.add_sequence("read_file", "write_file", "git_commit")
        builder.set_entry_point("read_file")
        builder.compile(interrupt_before=["git_commit"])

        diagram = builder.visualize()

        # Verify Mermaid diagram contains expected nodes
        assert "```mermaid" in diagram
        assert "graph TD" in diagram
        assert "read_file" in diagram
        assert "write_file" in diagram
        assert "git_commit" in diagram

    @pytest.mark.asyncio
    async def test_update_commit_execution_flow(self, mock_skill_manager):
        """Test executing the Update & Commit workflow up to the interrupt point."""
        # Setup mock responses
        mock_skill_manager.run = AsyncMock(
            side_effect=[
                {"content": "# Original\nVersion: 0.9"},  # read_file response
                "# Updated\nVersion: 1.0",  # generate_update response (LLM mock)
                {"success": True},  # write_file response
                {"diff": "docs/index.md | +Version: 1.0"},  # git_prepare response
            ]
        )

        builder = DynamicGraphBuilder(mock_skill_manager)

        # Add nodes
        builder.add_skill_node(
            "read_file",
            "filesystem",
            "read_file",
            fixed_args={"path": "docs/index.md"},
            state_output={"content": "file_content"},
        )

        builder.add_skill_node(
            "write_file",
            "filesystem",
            "write_file",
            fixed_args={"path": "docs/index.md"},
        )

        builder.add_skill_node(
            "git_prepare",
            "git",
            "stage_and_scan",
            state_output={"diff": "diff_result"},
        )

        builder.add_skill_node(
            "git_commit",
            "git",
            "commit",
            fixed_args={"message": "docs: update to 1.0"},
        )

        builder.add_sequence("read_file", "write_file", "git_prepare", "git_commit")
        builder.set_entry_point("read_file")

        graph = builder.compile(interrupt_before=["git_commit"])

        initial_state: GraphState = {
            "messages": [],
            "context_ids": [],
            "current_plan": "",
            "error_count": 0,
            "workflow_state": {},
        }

        # Execute should stop before git_commit due to interrupt
        result = await graph.ainvoke(initial_state)

        # Verify write_file was called (we got past write step)
        write_calls = [c for c in mock_skill_manager.run.call_args_list if c[0][1] == "write_file"]
        assert len(write_calls) == 1


class TestConditionalWorkflow:
    """Test conditional workflow branching based on state."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillManager."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value="result")
        return manager

    def test_conditional_path_based_on_security_scan(self, mock_skill_manager):
        """Test conditional routing based on security scan results."""
        from langgraph.graph import END

        builder = DynamicGraphBuilder(mock_skill_manager)

        # Node 1: Git prepare (returns security_issues in state)
        builder.add_skill_node(
            "git_prepare",
            "git",
            "stage_and_scan",
            state_output={"security_issues": "security_issues"},
        )

        # Node 2: Commit (safe path)
        builder.add_skill_node(
            "git_commit",
            "git",
            "commit",
        )

        # Node 3: Security alert (unsafe path)
        builder.add_function_node(
            "security_alert",
            lambda state: {"workflow_state": {"alert": "Security issues detected"}},
        )

        # Set entry
        builder.set_entry_point("git_prepare")

        # Conditional edge: if security_issues > 0, go to alert; else commit
        builder.add_conditional_edges(
            "git_prepare",
            lambda state: "security_alert" if state.get("security_issues") else "git_commit",
            {"security_alert": "security_alert", "git_commit": "git_commit"},
        )

        # Both paths end
        builder.add_edge("git_commit", END)
        builder.add_edge("security_alert", END)

        graph = builder.compile()

        assert graph is not None
        assert len(builder.nodes) == 3
