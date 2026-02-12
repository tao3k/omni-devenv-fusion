import pytest
import json
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestZkSearchCommands:
    """Tests for ZK search commands."""

    async def test_zk_toc(self, skill_tester):
        """Test zk_toc returns Table of Contents."""
        result = await skill_tester.run("knowledge", "zk_toc")
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "total" in output
        assert "notes" in output
        assert isinstance(output["notes"], list)

    async def test_zk_stats(self, skill_tester):
        """Test zk_stats returns knowledge base statistics."""
        result = await skill_tester.run("knowledge", "zk_stats")
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "stats" in output

    async def test_zk_search(self, skill_tester):
        """Test zk_search returns search results."""
        result = await skill_tester.run(
            "knowledge", "zk_search", query="architecture", max_results=5
        )
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "results" in output
        assert isinstance(output["results"], list)

    async def test_zk_links(self, skill_tester):
        """Test zk_links returns link information."""
        result = await skill_tester.run(
            "knowledge", "zk_links", note_id="architecture", direction="both"
        )
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "incoming" in output
        assert "outgoing" in output

    async def test_zk_find_related(self, skill_tester):
        """Test zk_find_related returns related notes."""
        result = await skill_tester.run(
            "knowledge", "zk_find_related", note_id="architecture", max_distance=2, limit=10
        )
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "results" in output

    async def test_zk_hybrid_search(self, skill_tester):
        """Test zk_hybrid_search returns merged results."""
        result = await skill_tester.run(
            "knowledge",
            "zk_hybrid_search",
            query="architecture MCP",
            max_results=5,
            use_hybrid=True,
        )
        assert result.success

        output = result.output if isinstance(result.output, dict) else json.loads(result.output)
        assert output["success"]
        assert "zk_total" in output
        assert "merged" in output
        assert isinstance(output["merged"], list)


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestKnowledgeModular:
    """Modular tests for knowledge skill."""

    async def test_get_development_context(self, skill_tester):
        """Test get_development_context execution."""
        result = await skill_tester.run("knowledge", "get_development_context")
        assert result.success
        assert isinstance(result.output, str)

        # Parse JSON output
        context = json.loads(result.output)
        assert "project" in context
        assert "git_rules" in context
        assert "guardrails" in context
        assert "architecture" in context

    async def test_get_best_practice(self, skill_tester):
        """Test get_best_practice execution."""
        result = await skill_tester.run("knowledge", "get_best_practice", topic="git commit")
        assert result.success

        # Handle both string and dict output
        if isinstance(result.output, str):
            output = json.loads(result.output)
        else:
            output = result.output

        assert "success" in output
        assert "topic" in output
        assert "theory" in output
        assert "practice" in output

    async def test_recall(self, skill_tester):
        """Test recall execution."""
        result = await skill_tester.run("knowledge", "recall", query="how to use advanced search")
        assert result.success
        # Should return a string or list of results
        assert result.output is not None
