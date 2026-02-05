import pytest
from omni.test_kit.decorators import omni_skill
from git.scripts.smart_commit_graphflow.workflow import _build_workflow


@omni_skill(name="git")
class TestSmartCommitLangGraph:
    """Test the LangGraph definitions within smart_commit workflow."""

    def test_graph_structure(self, test_tracer):
        """Verify graph nodes and edges with traceability."""
        test_tracer.log_step("building_workflow")
        graph = _build_workflow()

        test_tracer.log_step("compiling_graph")
        compiled = graph.compile()

        # Verify nodes
        test_tracer.log_step("verifying_nodes")
        assert "check" in compiled.nodes
        assert "empty" in compiled.nodes
        assert "lefthook_error" in compiled.nodes
        assert "security_warning" in compiled.nodes
        assert "prepared" in compiled.nodes

        test_tracer.assert_step_occurred("verifying_nodes")

    @pytest.mark.asyncio
    async def test_workflow_visualization_traceable(self, skill_tester, test_tracer):
        """Verify visualization with trace."""
        test_tracer.log_step("requesting_visualization")
        result = await skill_tester.run("git", "smart_commit", action="visualize")

        assert result.success
        assert "graph TD" in str(result.output)
        test_tracer.log_step("visualization_verified")
