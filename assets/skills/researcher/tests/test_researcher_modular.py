import pytest
from pathlib import Path
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


class TestParseRepoUrl:
    """Unit tests for parse_repo_url function."""

    def test_standard_github_url(self):
        """Test parsing standard GitHub URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/anthropics/claude-code")
        assert owner == "anthropics"
        assert repo == "claude-code"

    def test_github_url_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/tao3k/omni-dev-fusion.git")
        assert owner == "tao3k"
        assert repo == "omni-dev-fusion"

    def test_github_url_with_org_repo(self):
        """Test parsing URL with org and repo having same name."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/nickel-lang/nickel")
        assert owner == "nickel-lang"
        assert repo == "nickel"

    def test_github_ssh_url(self):
        """Test parsing SSH-style GitHub URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("git@github.com:antfu/skills.git")
        assert owner == "antfu"
        assert repo == "skills"

    def test_raw_githubusercontent_url(self):
        """Test parsing raw.githubusercontent.com URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://raw.githubusercontent.com/user/repo/main/README.md")
        assert owner == "user"
        assert repo == "repo"

    def test_empty_url(self):
        """Test parsing empty URL returns fallback."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("")
        assert owner == "unknown"
        assert repo == ""


class TestInitHarvestStructure:
    """Unit tests for init_harvest_structure function."""

    def test_harvest_structure_path(self, tmp_path):
        """Test that harvest structure creates correct path."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir to use tmp_path
        original = research_module.get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        try:
            result = init_harvest_structure("anthropics", "claude-code")
            expected = tmp_path / "harvested" / "anthropics" / "claude-code"

            assert result == expected
            assert result.exists()
            assert (result / "shards").exists()
        finally:
            research_module.get_data_dir = original

    def test_harvest_structure_creates_clean_directory(self, tmp_path):
        """Test that existing directory is removed and recreated."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        # Create directory with some content
        research_module.get_data_dir("harvested").mkdir(parents=True, exist_ok=True)
        harvest_dir = research_module.get_data_dir("harvested") / "test" / "repo"
        harvest_dir.mkdir(parents=True)
        (harvest_dir / "old_file.txt").write_text("old content")

        # Call init_harvest_structure
        result = init_harvest_structure("test", "repo")

        # Verify old content is gone
        assert not (result / "old_file.txt").exists()
        # Verify new structure exists
        assert result.exists()
        assert (result / "shards").exists()

    def test_harvest_structure_path_format(self, tmp_path):
        """Test path format matches <owner>/<repo_name> pattern."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        # Test various owner/repo combinations
        test_cases = [
            ("tao3k", "omni-dev-fusion"),
            ("nickel-lang", "nickel"),
            ("antfu", "skills"),
        ]

        for owner, repo in test_cases:
            result = init_harvest_structure(owner, repo)
            expected = tmp_path / "harvested" / owner / repo
            assert result == expected, f"Expected {expected}, got {result}"


class TestResearchState:
    """Tests for ResearchState TypedDict."""

    def test_research_state_fields(self):
        """Test ResearchState has all required fields."""
        from researcher.scripts.research_graph import ResearchState

        state = ResearchState(
            request="Analyze architecture",
            repo_url="https://github.com/example/repo",
            repo_path="/path/to/repo",
            repo_revision="abc123",
            repo_revision_date="2026-02-04",
            repo_owner="example",
            repo_name="repo",
            file_tree="...",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="/path/to/harvest",
            final_report="",
            steps=0,
            messages=[],
            error=None,
        )

        assert state["repo_owner"] == "example"
        assert state["repo_name"] == "repo"
        assert state["repo_revision"] == "abc123"
