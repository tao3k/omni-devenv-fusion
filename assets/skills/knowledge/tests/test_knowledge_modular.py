import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestKnowledgeModular:
    """Modular tests for knowledge skill."""

    async def test_get_development_context(self, skill_tester):
        """Test get_development_context execution."""
        result = await skill_tester.run("knowledge", "get_development_context")
        assert result.success
        assert isinstance(result.output, str)
        assert "Frameworks" in result.output

    async def test_get_best_practice(self, skill_tester):
        """Test get_best_practice execution."""
        result = await skill_tester.run("knowledge", "get_best_practice", topic="git commit")
        assert result.success
        assert "Theory" in result.output
        assert "Practice" in result.output

    async def test_recall(self, skill_tester):
        """Test recall execution."""
        result = await skill_tester.run("knowledge", "recall", query="how to use advanced search")
        assert result.success
        # Should return a string or list of results
        assert result.output is not None
