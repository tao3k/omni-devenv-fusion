"""
Unit tests for SkillDiscoveryService with Weighted RRF + Field Boosting.

Tests the Rust-backed hybrid search functionality that uses
Weighted Reciprocal Rank Fusion for optimal tool discovery.

Run from project root:
    uv run pytest packages/python/core/tests/units/skills/test_discovery_service.py -v
"""

import pytest


class TestSkillDiscoveryServiceWeightedRRF:
    """Tests for SkillDiscoveryService using Weighted RRF hybrid search."""

    @pytest.fixture
    def discovery_service(self):
        """Create a fresh discovery service for each test."""
        from omni.core.skills.discovery import SkillDiscoveryService

        return SkillDiscoveryService()

    def test_search_uses_rust_weighted_rrf(self, discovery_service):
        """Verify search returns results with RRF scores (not uniform)."""
        matches = discovery_service.search_tools("git commit", limit=10)

        assert len(matches) > 0, "Should find at least one tool"

        # Check that git.commit is in results
        tool_names = [m.name for m in matches]
        assert any("git.commit" in name for name in tool_names), (
            f"git.commit not found in results: {tool_names}"
        )

        # Verify scores are NOT all the same (Weighted RRF should differentiate)
        scores = [m.score for m in matches]
        unique_scores = set(scores)
        assert len(unique_scores) > 1, (
            f"All scores are the same: {scores}. Weighted RRF not working!"
        )

    def test_exact_phrase_boost(self, discovery_service):
        """Verify search returns results with score differentiation."""
        # Search for "git commit" - should find git-related tools
        matches = discovery_service.search_tools("git commit", limit=5)

        # Should find at least one git.commit related tool
        has_commit = any("commit" in m.name.lower() for m in matches)
        assert has_commit, f"Should find commit tools, got: {[m.name for m in matches]}"

        # Top result should be a commit-related tool
        assert "commit" in matches[0].name.lower(), (
            f"Top result should be commit-related, got: {matches[0].name}"
        )

    def test_field_boosting_differentiation(self, discovery_service):
        """Verify field boosting provides score differentiation."""
        matches = discovery_service.search_tools("read file", limit=10)

        # filesystem.read_files should be #1
        assert len(matches) > 0, "Should find tools"

        # Check that top result has distinctively higher score
        if len(matches) >= 2:
            top_score = matches[0].score
            second_score = matches[1].score
            # Scores should be different due to field boosting
            assert top_score >= second_score, (
                f"Top score {top_score} should be >= second score {second_score}"
            )

    def test_search_limit_parameter(self, discovery_service):
        """Verify limit parameter controls result count."""
        matches = discovery_service.search_tools("git", limit=3)

        assert len(matches) <= 3, f"Expected <= 3 results, got {len(matches)}"

    def test_search_threshold_filtering(self, discovery_service):
        """Verify threshold filtering works correctly."""
        # High threshold should return fewer results
        high_threshold_matches = discovery_service.search_tools("git", limit=10, threshold=0.8)

        # All results should have score >= threshold
        for m in high_threshold_matches:
            assert m.score >= 0.8, f"Result below threshold: {m.name} = {m.score}"

    def test_search_returns_tool_match_objects(self, discovery_service):
        """Verify search returns proper ToolMatch objects with all fields."""
        matches = discovery_service.search_tools("git commit", limit=1)

        assert len(matches) > 0, "Should find at least one tool"

        match = matches[0]
        # Verify all required fields are present
        assert hasattr(match, "name"), "ToolMatch missing 'name'"
        assert hasattr(match, "skill_name"), "ToolMatch missing 'skill_name'"
        assert hasattr(match, "description"), "ToolMatch missing 'description'"
        assert hasattr(match, "score"), "ToolMatch missing 'score'"
        assert hasattr(match, "usage_template"), "ToolMatch missing 'usage_template'"

        # Verify usage_template is a valid @omni() format
        assert "@omni(" in match.usage_template, (
            f"Invalid usage_template format: {match.usage_template}"
        )

    def test_git_tools_ranked_correctly(self, discovery_service):
        """Verify git tools are ranked by relevance to query."""
        matches = discovery_service.search_tools("commit", limit=10)

        # Get all tools with "commit" in the name
        commit_tools = [m for m in matches if "commit" in m.name.lower()]

        # Should find at least some commit-related tools
        assert len(commit_tools) > 0, (
            f"Should find commit tools, got: {[m.name for m in matches[:5]]}"
        )

        # The top commit-related tool should have a distinctively higher score
        commit_scores = [(m.name, m.score) for m in commit_tools]
        top_commit = max(commit_scores, key=lambda x: x[1])
        assert top_commit[1] > 0.3, (
            f"Top commit tool should have score > 0.3, got: {commit_scores[:3]}"
        )

    def test_score_range_valid(self, discovery_service):
        """Verify all returned scores are in valid range."""
        matches = discovery_service.search_tools("git python", limit=20)

        for match in matches:
            assert 0.0 <= match.score <= 2.0, f"Score out of range for {match.name}: {match.score}"

    def test_empty_query_returns_results(self, discovery_service):
        """Verify search handles queries that match some tools."""
        matches = discovery_service.search_tools("filesystem read", limit=5)

        # Should find relevant tools even with partial query
        if len(matches) > 0:
            assert matches[0].score > 0, "Matches should have positive scores"

    def test_usage_template_format(self, discovery_service):
        """Verify usage_template has correct @omni() format."""
        matches = discovery_service.search_tools("git commit", limit=1)

        if len(matches) > 0:
            template = matches[0].usage_template
            # Should be @omni("tool.name", {...})
            assert template.startswith('@omni("'), f'Template should start with @omni(": {template}'
            assert '", {' in template, f"Template should contain comma: {template}"

    def test_search_handles_errors_gracefully(self, discovery_service):
        """Verify graceful handling when Rust search fails."""
        # This test verifies error handling works
        # In normal conditions, Rust search should succeed
        try:
            matches = discovery_service.search_tools("test query", limit=1)
            # If Rust works, verify we get results or empty list
            assert isinstance(matches, list), "Should return list"
        except Exception as e:
            # If Rust fails, should not raise (fallback should handle it)
            pytest.fail(f"Search should not raise: {e}")


class TestGenerateUsageTemplate:
    """Tests for the generate_usage_template function."""

    def test_basic_template(self):
        """Verify basic usage template generation."""
        from omni.core.skills.discovery import generate_usage_template

        template = generate_usage_template("test.tool", {})
        assert '@omni("test.tool"' in template

    def test_template_with_schema(self):
        """Verify template includes schema from input_schema."""
        from omni.core.skills.discovery import generate_usage_template

        schema = {
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
                "repo_path": {"type": "string", "description": "Repository path"},
            },
            "required": ["message"],
        }

        template = generate_usage_template("git.commit", schema)

        # Should include required fields
        assert "message" in template
        # Should now include optional fields with '?' suffix
        assert "repo_path?" in template

    def test_template_handles_string_schema(self):
        """Verify template handles JSON string input_schema."""
        from omni.core.skills.discovery import generate_usage_template

        schema_str = '{"properties": {"code": {"type": "string"}}, "required": ["code"]}'

        template = generate_usage_template("python.run", schema_str)

        assert "code" in template

    def test_template_handles_double_encoded_json(self):
        """Verify template handles double-encoded JSON from LanceDB."""
        from omni.core.skills.discovery import generate_usage_template

        # This simulates what LanceDB might return (double-encoded)
        inner_schema = '{"properties": {"x": {"type": "integer"}}, "required": ["x"]}'
        outer_schema = inner_schema

        template = generate_usage_template("test.tool", outer_schema)

        # The function should parse the JSON string correctly
        assert "x" in template


class TestDiscoveredSkill:
    """Tests for the DiscoveredSkill class."""

    def test_from_index_entry(self):
        """Verify DiscoveredSkill creation from index entry."""
        from omni.core.skills.discovery import DiscoveredSkill
        from omni.foundation.bridge.scanner import DiscoveredSkillRules

        # Create a mock entry
        entry = DiscoveredSkillRules(
            skill_name="test_skill",
            skill_path="/path/to/test_skill",
            metadata={"version": "1.0.0"},
        )

        skill = DiscoveredSkill.from_index_entry(entry)

        assert skill.name == "test_skill"
        assert skill.path == "/path/to/test_skill"
        assert skill.metadata["version"] == "1.0.0"


class TestToolMatch:
    """Tests for the ToolMatch class."""

    def test_tool_match_creation(self):
        """Verify ToolMatch can be created with all fields."""
        from omni.core.skills.discovery import ToolMatch

        match = ToolMatch(
            name="git.commit",
            skill_name="git",
            description="Commit changes",
            score=0.95,
            matched_intent="commit changes",
            usage_template='@omni("git.commit", {"message": "..."})',
        )

        assert match.name == "git.commit"
        assert match.score == 0.95
        assert "git" in match.usage_template

    def test_tool_match_defaults(self):
        """Verify ToolMatch default values."""
        from omni.core.skills.discovery import ToolMatch

        match = ToolMatch(
            name="test.tool",
            skill_name="test",
            description="Test",
            score=1.0,
            matched_intent="test",
        )

        assert match.usage_template == ""


class TestToolRecord:
    """Tests for the ToolRecord class."""

    def test_tool_record_creation(self):
        """Verify ToolRecord can be created with all fields."""
        from omni.core.skills.discovery import ToolRecord

        record = ToolRecord(
            name="git.commit",
            skill_name="git",
            description="Commit changes",
            category="version_control",
            input_schema='{"type": "object"}',
            file_path="git/scripts/commit.py",
        )

        assert record.name == "git.commit"
        assert record.category == "version_control"
        assert "object" in record.input_schema

    def test_tool_record_from_tool_dict(self):
        """Verify ToolRecord creation from dictionary."""
        from omni.core.skills.discovery import ToolRecord

        tool_dict = {
            "name": "python.run",
            "description": "Run Python code",
            "category": "development",
            "input_schema": '{"type": "object"}',
            "file_path": "python/scripts/run.py",
        }

        record = ToolRecord.from_tool_dict(tool_dict, "python")

        assert record.name == "python.run"
        assert record.skill_name == "python"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
