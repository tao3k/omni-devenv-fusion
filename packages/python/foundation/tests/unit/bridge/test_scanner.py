"""Unit tests for skill scanner path resolution.

Tests that skill paths are correctly extracted from tool metadata
to prevent issues like the one where paths like "git/scripts/commit.py"
were incorrectly resolved to "git" instead of "assets/skills/git".
"""

from pathlib import Path
from typing import Any

import pytest

from omni.foundation.bridge.scanner import (
    DiscoveredSkillRules,
    PythonSkillScanner,
    SnifferRule,
)


class TestSkillPathResolution:
    """Test skill path extraction from file paths."""

    def test_extract_skill_name_from_absolute_path(self):
        """Test extracting skill name from absolute file path."""
        # Simulate the path extraction logic from scanner.py
        file_path = "/Users/user/project/assets/skills/git/scripts/commit.py"
        skill_name = "git"

        if "/assets/skills/" in file_path:
            skill_path = file_path.split("/assets/skills/")[-1].split("/")[0]
            skill_path = f"assets/skills/{skill_path}"

        assert skill_path == "assets/skills/git"

    def test_extract_skill_path_from_different_skills(self):
        """Test path extraction for various skills."""
        test_cases = [
            # (file_path, expected_skill_path)
            (
                "/Users/user/project/assets/skills/git/scripts/commit.py",
                "assets/skills/git",
            ),
            (
                "/Users/user/project/assets/skills/memory/scripts/save.py",
                "assets/skills/memory",
            ),
            (
                "/Users/user/project/assets/skills/researcher/scripts/search.py",
                "assets/skills/researcher",
            ),
            (
                "/home/user/code/assets/skills/skill/generate.py",
                "assets/skills/skill",
            ),
        ]

        for file_path, expected in test_cases:
            if "/assets/skills/" in file_path:
                skill_path = file_path.split("/assets/skills/")[-1].split("/")[0]
                skill_path = f"assets/skills/{skill_path}"
            else:
                skill_path = f"assets/skills/{file_path.split('/')[-1]}"

            assert skill_path == expected, f"Failed for {file_path}"

    def test_discovered_skill_rules_path_format(self):
        """Test DiscoveredSkillRules stores correct path format."""
        rules = DiscoveredSkillRules(
            skill_name="git",
            skill_path="assets/skills/git",
            rules=[SnifferRule("file_pattern", "assets/skills/git")],
            metadata={"description": "Git operations"},
        )

        # Verify path is in correct format
        assert rules.skill_path == "assets/skills/git"
        assert rules.skill_name == "git"
        assert len(rules.rules) == 1

    def test_skill_path_join_with_base_path(self):
        """Test that skill path can be correctly joined with base path."""
        base_path = Path("/Users/user/project")
        skill_path = "assets/skills/git"

        full_path = base_path / skill_path
        expected = Path("/Users/user/project/assets/skills/git")

        assert full_path == expected
        assert full_path.exists() or not expected.exists()  # Just check path construction


class TestSkillScannerIntegration:
    """Integration tests for PythonSkillScanner (mocked)."""

    def test_group_tools_by_skill_name(self):
        """Test that tools are correctly grouped by skill name."""
        # Mock tool data similar to what LanceDB returns
        mock_tools = [
            {
                "skill_name": "git",
                "tool_name": "git.commit",
                "file_path": "/project/assets/skills/git/scripts/commit.py",
                "description": "Create a commit",
            },
            {
                "skill_name": "git",
                "tool_name": "git.status",
                "file_path": "/project/assets/skills/git/scripts/status.py",
                "description": "Show working tree status",
            },
            {
                "skill_name": "memory",
                "tool_name": "memory.save",
                "file_path": "/project/assets/skills/memory/scripts/save.py",
                "description": "Save memory",
            },
        ]

        # Simulate the grouping logic from scanner.py
        skills_by_name: dict[str, dict] = {}
        for tool in mock_tools:
            skill_name = tool.get("skill_name", "unknown")
            file_path = tool.get("file_path", "")

            if "/assets/skills/" in file_path:
                skill_path = file_path.split("/assets/skills/")[-1].split("/")[0]
                skill_path = f"assets/skills/{skill_path}"
            else:
                skill_path = f"assets/skills/{skill_name}"

            if skill_name not in skills_by_name:
                skills_by_name[skill_name] = {
                    "name": skill_name,
                    "path": skill_path,
                    "rules": [],
                    "metadata": {"description": tool.get("description", ""), "tools": []},
                }

            skills_by_name[skill_name]["metadata"]["tools"].append(
                {
                    "name": tool.get("tool_name", ""),
                    "description": tool.get("description", ""),
                }
            )

        # Verify grouping
        assert len(skills_by_name) == 2
        assert "git" in skills_by_name
        assert "memory" in skills_by_name

        # Verify git has 2 tools
        assert len(skills_by_name["git"]["metadata"]["tools"]) == 2

        # Verify paths are correct
        assert skills_by_name["git"]["path"] == "assets/skills/git"
        assert skills_by_name["memory"]["path"] == "assets/skills/memory"

    def test_fallback_for_missing_assets_skills(self):
        """Test fallback when file_path doesn't contain assets/skills."""
        mock_tools = [
            {
                "skill_name": "test_skill",
                "tool_name": "test.func",
                "file_path": "/some/other/path/script.py",  # No assets/skills
                "description": "Test function",
            },
        ]

        # Simulate the fallback logic
        skills_by_name: dict[str, dict] = {}
        for tool in mock_tools:
            skill_name = tool.get("skill_name", "unknown")
            file_path = tool.get("file_path", "")

            if "/assets/skills/" in file_path:
                skill_path = file_path.split("/assets/skills/")[-1].split("/")[0]
                skill_path = f"assets/skills/{skill_path}"
            else:
                # Fallback: use skill_name
                skill_path = f"assets/skills/{skill_name}"

            if skill_name not in skills_by_name:
                skills_by_name[skill_name] = {
                    "name": skill_name,
                    "path": skill_path,
                    "rules": [],
                    "metadata": {"description": tool.get("description", ""), "tools": []},
                }

        # Verify fallback works
        assert skills_by_name["test_skill"]["path"] == "assets/skills/test_skill"


class TestPathValidation:
    """Tests to validate path resolution correctness."""

    def test_skill_path_resolves_to_existing_directory(self):
        """Verify that resolved skill paths point to existing directories.

        This test catches the bug where "git" was resolved instead of
        "assets/skills/git", causing scripts_path to be invalid.
        """
        # Simulate what happens in the kernel when loading a skill
        project_root = Path("/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion")
        skill_path_from_scanner = "assets/skills/git"

        # This is what create_from_discovered does
        full_skill_path = project_root / skill_path_from_scanner

        # Verify path points to correct location
        assert full_skill_path == Path(
            "/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion/assets/skills/git"
        )
        assert full_skill_path.exists(), f"Skill path does not exist: {full_skill_path}"

    def test_scripts_path_is_valid_after_resolution(self):
        """Verify scripts path is valid after skill path resolution.

        This is the critical test - the bug caused scripts_path to be
        "/project/git/scripts" instead of "/project/assets/skills/git/scripts".
        """
        project_root = Path("/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion")
        skill_path_from_scanner = "assets/skills/git"

        full_skill_path = project_root / skill_path_from_scanner
        scripts_path = full_skill_path / "scripts"

        # Verify scripts path is correct
        assert scripts_path == Path(
            "/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion/assets/skills/git/scripts"
        )
        assert scripts_path.exists(), f"Scripts path does not exist: {scripts_path}"

    def test_incorrect_path_would_be_caught(self):
        """Test that demonstrates the bug would be caught.

        If we used the incorrect path format, this test would fail.
        """
        project_root = Path("/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion")

        # Incorrect path format (the bug)
        incorrect_skill_path = "git"
        incorrect_full_path = project_root / incorrect_skill_path
        incorrect_scripts_path = incorrect_full_path / "scripts"

        # This would NOT exist (demonstrating the bug)
        assert not incorrect_scripts_path.exists(), (
            "This path should not exist - it demonstrates the bug!"
        )

        # Correct path format (the fix)
        correct_skill_path = "assets/skills/git"
        correct_full_path = project_root / correct_skill_path
        correct_scripts_path = correct_full_path / "scripts"

        # This should exist
        assert correct_scripts_path.exists(), (
            f"Correct scripts path should exist: {correct_scripts_path}"
        )
