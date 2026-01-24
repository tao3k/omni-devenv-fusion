"""
Skills Utilities Tests - Simplified

Tests for omni.foundation.utils.skills module.
"""

from pathlib import Path


class TestSkillUtilities:
    """Test omni.foundation.utils.skills functions."""

    def test_current_skill_dir_exists(self):
        """Test that current_skill_dir function exists."""
        from omni.foundation.utils.skills import current_skill_dir

        assert callable(current_skill_dir)

    def test_skill_path_exists(self):
        """Test that skill_path function exists."""
        from omni.foundation.utils.skills import skill_path

        assert callable(skill_path)

    def test_skill_asset_exists(self):
        """Test that skill_asset function exists."""
        from omni.foundation.utils.skills import skill_asset

        assert callable(skill_asset)

    def test_skill_command_exists(self):
        """Test that skill_command function exists."""
        from omni.foundation.utils.skills import skill_command

        assert callable(skill_command)

    def test_skill_reference_exists(self):
        """Test that skill_reference function exists."""
        from omni.foundation.utils.skills import skill_reference

        assert callable(skill_reference)

    def test_skill_data_exists(self):
        """Test that skill_data function exists."""
        from omni.foundation.utils.skills import skill_data

        assert callable(skill_data)


class TestSkillPathBuilding:
    """Test skill path building with explicit skill_dir."""

    def test_skill_path_with_explicit_dir(self, tmp_path: Path):
        """Test skill_path with explicit skill_dir."""
        from omni.foundation.utils.skills import skill_path

        # Use tmp_path instead of hardcoded /test/skills/git
        test_skill_dir = tmp_path / "skills" / "git"
        result = skill_path("scripts/status.py", skill_dir=test_skill_dir)

        assert str(result) == str(test_skill_dir / "scripts/status.py")

    def test_skill_asset_with_explicit_dir(self, tmp_path: Path):
        """Test skill_asset with explicit skill_dir."""
        from omni.foundation.utils.skills import skill_asset

        test_skill_dir = tmp_path / "skills" / "git"
        result = skill_asset("guide.md", skill_dir=test_skill_dir)

        assert str(result) == str(test_skill_dir / "assets/guide.md")

    def test_skill_command_with_explicit_dir(self, tmp_path: Path):
        """Test skill_command with explicit skill_dir."""
        from omni.foundation.utils.skills import skill_command

        test_skill_dir = tmp_path / "skills" / "git"
        result = skill_command("workflow.py", skill_dir=test_skill_dir)

        assert str(result) == str(test_skill_dir / "scripts/workflow.py")

    def test_skill_reference_with_explicit_dir(self, tmp_path: Path):
        """Test skill_reference with explicit skill_dir."""
        from omni.foundation.utils.skills import skill_reference

        test_skill_dir = tmp_path / "skills" / "git"
        result = skill_reference("docs.md", skill_dir=test_skill_dir)

        assert str(result) == str(test_skill_dir / "references/docs.md")

    def test_skill_data_with_explicit_dir(self, tmp_path: Path):
        """Test skill_data with explicit skill_dir."""
        from omni.foundation.utils.skills import skill_data

        test_skill_dir = tmp_path / "skills" / "git"
        result = skill_data("config.json", skill_dir=test_skill_dir)

        assert str(result) == str(test_skill_dir / "data/config.json")
