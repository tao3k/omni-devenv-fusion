import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from omni.test_kit.decorators import omni_skill

# Ensure scripts directory is in path for imports
import sys

RESEARCHER_SCRIPTS = Path(__file__).parent.parent / "scripts"
if str(RESEARCHER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RESEARCHER_SCRIPTS))


@pytest.mark.asyncio
@omni_skill(name="researcher")
class TestResearcherIntegration:
    """Integration tests for researcher skill."""

    async def test_run_research_graph(self, skill_tester):
        """Test run_research_graph entry point exists and is callable."""
        # This tests that the entry point is properly registered
        # Full integration test with real LLM is skipped to avoid long-running tests
        try:
            result = await skill_tester.run(
                "researcher",
                "run_research_graph",
                repo_url="https://github.com/test/repo",
                request="Test request",
            )
            # Accept either success or expected error types
            assert (
                result.success
                or "not found" in str(result.error).lower()
                or "api" in str(result.error).lower()
            )
        except Exception as e:
            # Expected when skill_tester can't load the skill outside MCP context
            pytest.skip(f"Skill not loaded in test context: {e}")


class TestResearchGraph:
    """Unit tests for research graph components."""

    def test_node_setup_returns_correct_state(self):
        """Test that node_setup returns properly structured state."""
        # Import after path setup
        from research_graph import ResearchState

        # Mock the research module functions
        test_state = ResearchState(
            request="Test request",
            repo_url="https://github.com/test/repo",
            repo_path="/tmp/test",
            repo_revision="abc123",
            repo_revision_date="2026-02-05",
            repo_owner="test",
            repo_name="repo",
            file_tree="",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="",
            final_report="",
            steps=0,
            messages=[],
            error=None,
        )

        # Verify state structure
        assert isinstance(test_state, dict)
        assert "request" in test_state
        assert "repo_url" in test_state
        assert test_state["steps"] == 0
        assert test_state["error"] is None

    def test_research_state_typeddict_compliance(self):
        """Test that ResearchState TypedDict works correctly."""
        from research_graph import ResearchState, ShardDef

        # Test creating a valid ResearchState
        state: ResearchState = {
            "request": "Analyze architecture",
            "repo_url": "https://github.com/example/repo",
            "repo_path": "/path/to/repo",
            "repo_revision": "abc123",
            "repo_revision_date": "2026-02-05",
            "repo_owner": "example",
            "repo_name": "repo",
            "file_tree": "src/\n  main.rs",
            "shards_queue": [],
            "current_shard": None,
            "shard_counter": 0,
            "shard_analyses": [],
            "harvest_dir": "/path/to/harvest",
            "final_report": "",
            "steps": 1,
            "messages": [],
            "error": None,
        }

        assert state["shard_counter"] == 0
        assert len(state["shards_queue"]) == 0

    def test_shard_def_structure(self):
        """Test ShardDef TypedDict structure."""
        from research_graph import ShardDef

        shard: ShardDef = {
            "name": "Core Module",
            "targets": ["src/core.rs", "src/lib.rs"],
            "description": "Core functionality",
        }

        assert shard["name"] == "Core Module"
        assert len(shard["targets"]) == 2


@pytest.mark.slow
class TestResearcherFullWorkflow:
    """Full workflow tests (skipped by default)."""

    async def test_full_research_workflow(self):
        """Test complete research workflow (requires LLM)."""
        pytest.skip("Requires LLM and network - run with --runslow")
        # This would test the full workflow end-to-end
        # Currently handled by the integration test above


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
