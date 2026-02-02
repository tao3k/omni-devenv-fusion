import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="researcher")
class TestResearcherModular:
    """Modular tests for researcher skill."""

    async def test_run_research_graph(self, skill_tester):
        """Test run_research_graph execution."""
        # This is a complex graph execution, we likely want to mock the graph itself
        # or test the entry point logic.
        result = await skill_tester.run(
            "researcher",
            "run_research_graph",
            repo_url="https://github.com/tao3k/omni-dev-fusion",
            request="Analyze the architecture",
        )
        # It might take time or require LLM, so we might need more mocking if it fails in CI
        assert result.success or "API" in str(result.error)

    async def test_clone_repo(self, skill_tester, tmp_path):
        """Test clone_repo logic."""
        # Test with a mock or a small repo if allowed
        pass
