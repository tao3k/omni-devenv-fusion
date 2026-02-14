"""
Test for command_name parsing to avoid skill prefix duplication.

Verifies that when Rust returns tool_name in "skill.command" format,
the command_name is correctly extracted without duplicating the skill prefix.

See: https://github.com/tao3k/omni-dev-fusion/issues/xxx
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


def create_mock_search(mock_matches):
    """Helper to create a mock async search function that returns specified matches."""

    async def mock_search(query, limit=5, min_score=0.0):
        del query, limit, min_score
        return mock_matches

    return mock_search


class TestCommandNameParsing:
    """Test that command_name is correctly extracted from tool_name."""

    @pytest.mark.asyncio
    async def test_tool_name_with_skill_prefix_parsed_correctly(self):
        """Verify tool_name 'git.commit' is parsed to skill='git', command='commit'."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.8,
                "final_score": 0.8,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.commit",  # Full format from Rust
                "file_path": "assets/skills/git/scripts/commit.py",
            }
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("commit code", use_cache=False)

        assert len(results) == 1
        assert results[0].skill_name == "git"
        assert results[0].command_name == "commit"  # Not "git.commit"

    @pytest.mark.asyncio
    async def test_command_without_skill_prefix_preserved(self):
        """Verify command_name without prefix is preserved."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.75,
                "final_score": 0.75,
                "confidence": "medium",
                "skill_name": "memory",
                "tool_name": "save",  # No skill prefix
                "file_path": "assets/skills/memory/scripts/save.py",
            }
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("save memory", use_cache=False)

        assert len(results) == 1
        assert results[0].skill_name == "memory"
        assert results[0].command_name == "save"

    @pytest.mark.asyncio
    async def test_meta_entries_without_file_path_skipped(self):
        """Verify entries where skill_name == command_name are filtered out (prevents 'git.git')."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.9,
                "final_score": 0.9,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git",  # Skill-level metadata, not a command
                "file_path": "assets/skills/git/SKILL.md",  # Has file_path but is skill-level entry
            }
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("git", use_cache=False)

        # Should be empty - skill-level entry where skill_name == command_name
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_multiple_commands_same_skill(self):
        """Verify multiple commands from same skill are parsed correctly."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.85,
                "final_score": 0.85,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.commit",
                "file_path": "assets/skills/git/scripts/commit.py",
            },
            {
                "score": 0.8,
                "final_score": 0.8,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.status",
                "file_path": "assets/skills/git/scripts/status.py",
            },
            {
                "score": 0.75,
                "final_score": 0.75,
                "confidence": "medium",
                "skill_name": "git",
                "tool_name": "git.push",
                "file_path": "assets/skills/git/scripts/push.py",
            },
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("git operations", use_cache=False)

        assert len(results) == 3
        for r in results:
            assert r.skill_name == "git"
            assert r.command_name in ["commit", "status", "push"]

    @pytest.mark.asyncio
    async def test_different_skills_parsed_correctly(self):
        """Verify commands from different skills are parsed correctly."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.9,
                "final_score": 0.9,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.commit",
                "file_path": "assets/skills/git/scripts/commit.py",
            },
            {
                "score": 0.85,
                "final_score": 0.85,
                "confidence": "high",
                "skill_name": "memory",
                "tool_name": "memory.save",
                "file_path": "assets/skills/memory/scripts/save.py",
            },
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("save and commit", use_cache=False)

        assert len(results) == 2

        # Check git.commit
        git_result = next(r for r in results if r.skill_name == "git")
        assert git_result.command_name == "commit"

        # Check memory.save
        memory_result = next(r for r in results if r.skill_name == "memory")
        assert memory_result.command_name == "save"


class TestNoDuplicateSkillPrefix:
    """Regression tests for issue: git.git.commit instead of git.commit."""

    @pytest.mark.asyncio
    async def test_full_command_display_format(self):
        """Verify full command displays as 'skill.command' not 'skill.skill.command'."""
        from omni.core.router.main import OmniRouter

        mock_matches = [
            {
                "score": 0.9,
                "final_score": 0.9,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.commit",
                "file_path": "assets/skills/git/scripts/commit.py",
            }
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("commit", use_cache=False)

        assert len(results) == 1
        r = results[0]

        # The combined display should be "git.commit", not "git.git.commit"
        full_name = f"{r.skill_name}.{r.command_name}"
        assert full_name == "git.commit"
        assert full_name != "git.git.commit"

    @pytest.mark.asyncio
    async def test_actual_rust_output_format(self):
        """Test with actual Rust output format (skill.command from LanceDB)."""
        from omni.core.router.main import OmniRouter

        # This simulates actual Rust output structure
        mock_matches = [
            {
                "score": 0.82,
                "final_score": 0.82,
                "confidence": "high",
                "skill_name": "git",
                "tool_name": "git.commit",
                "command": "commit",  # Alternative field name
                "file_path": "assets/skills/git/scripts/commit.py",
                "description": "Commit changes to repository",
            },
            {
                "score": 0.78,
                "final_score": 0.78,
                "confidence": "medium",
                "skill_name": "git",
                "tool_name": "git.smart_commit",
                "command": "smart_commit",
                "file_path": "assets/skills/git/scripts/smart_commit.py",
                "description": "Smart commit with conventionalCommits",
            },
        ]

        router = OmniRouter(storage_path=":memory:")
        router._initialized = True
        router._hybrid.search = create_mock_search(mock_matches)

        results = await router.route_hybrid("git commit", use_cache=False)

        # Verify no duplication
        for r in results:
            full_name = f"{r.skill_name}.{r.command_name}"
            # Should NOT contain double skill prefix
            parts = full_name.split(".")
            assert parts[0] == r.skill_name
            assert parts[1] != r.skill_name, f"Duplicate skill prefix in {full_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
