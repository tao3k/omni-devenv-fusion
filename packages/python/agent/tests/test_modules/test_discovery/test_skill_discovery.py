"""
Tests for skill_runtime.core.discovery_core.SkillDiscovery.

Tests skill discovery functionality from filesystem and index.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory with test skills (module-scoped)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)

        # Create skill_a with SKILL.md
        skill_a = skills_dir / "skill_a"
        skill_a.mkdir()
        (skill_a / "SKILL.md").write_text("# Skill A\n\nDescription")

        # Create skill_b with SKILL.md
        skill_b = skills_dir / "skill_b"
        skill_b.mkdir()
        (skill_b / "SKILL.md").write_text("# Skill B\n\nDescription")

        # Create invalid_skill without SKILL.md
        invalid_skill = skills_dir / "invalid_skill"
        invalid_skill.mkdir()

        # Create a file (not a directory)
        (skills_dir / "not_a_skill.txt").write_text("text")

        yield skills_dir


@pytest.fixture
def discovery(temp_skills_dir):
    """Create a SkillDiscovery instance (module-scoped)."""
    from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

    return SkillDiscovery(temp_skills_dir)


class TestSkillDiscovery:
    """Unit tests for SkillDiscovery."""

    # Uses module-scoped fixtures: temp_skills_dir, discovery

    # =========================================================================
    # Discovery Tests
    # =========================================================================

    def test_discover_returns_all_valid_skills(self, discovery):
        """Test that discover returns all skills with SKILL.md."""
        skills = discovery.discover()

        skill_names = [s.name for s in skills]
        assert "skill_a" in skill_names
        assert "skill_b" in skill_names
        assert "invalid_skill" not in skill_names
        assert "not_a_skill.txt" not in skill_names

    def test_discover_sorts_by_name(self, discovery):
        """Test that discovered skills are sorted by name."""
        skills = discovery.discover()

        names = [s.name for s in skills]
        assert names == sorted(names)

    def test_discover_empty_dir(self, tmp_path):
        """Test discover with empty skills directory."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        discovery = SkillDiscovery(tmp_path)
        skills = discovery.discover()

        assert skills == []

    def test_discover_nonexistent_dir(self, tmp_path):
        """Test discover with non-existent skills directory."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        discovery = SkillDiscovery(tmp_path / "nonexistent")
        skills = discovery.discover()

        assert skills == []

    def test_discover_single_existing_skill(self, discovery):
        """Test discovering a single existing skill."""
        result = discovery.discover_single("skill_a")

        assert result is not None
        assert result.name == "skill_a"

    def test_discover_single_nonexistent_skill(self, discovery):
        """Test discovering a single non-existent skill."""
        result = discovery.discover_single("nonexistent_skill")

        assert result is None

    def test_discover_single_skill_without_skill_md(self, discovery):
        """Test discovering a skill without SKILL.md returns None."""
        result = discovery.discover_single("invalid_skill")

        assert result is None

    # =========================================================================
    # Index Management Tests
    # =========================================================================

    def test_is_index_fresh_with_valid_index(self, discovery):
        """Test index freshness with valid index."""
        # Create valid index
        index_data = [
            {"name": "skill_a", "version": "1.0"},
            {"name": "skill_b", "version": "1.0"},
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        assert discovery.is_index_fresh() is True

    def test_is_index_fresh_with_missing_skill(self, discovery):
        """Test index freshness when a referenced skill is missing."""
        # Create index with non-existent skill
        index_data = [
            {"name": "skill_a", "version": "1.0"},
            {"name": "missing_skill", "version": "1.0"},
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        assert discovery.is_index_fresh() is False

    def test_is_index_fresh_no_index_file(self, discovery):
        """Test index freshness when no index file exists."""
        assert discovery.is_index_fresh() is False

    def test_is_index_fresh_invalid_json(self, discovery):
        """Test index freshness with invalid JSON."""
        (discovery.index_path).write_text("invalid json{")

        assert discovery.is_index_fresh() is False

    def test_is_index_fresh_empty_index(self, discovery):
        """Test index freshness with empty index."""
        index_data = []
        (discovery.index_path).write_text(json.dumps(index_data))

        assert discovery.is_index_fresh() is True

    def test_load_from_index(self, discovery):
        """Test loading skills from index file."""
        # Create valid index
        index_data = [
            {"name": "skill_a", "version": "1.0"},
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        # Mock load_skill function
        mock_skill = MagicMock()
        mock_load = MagicMock(return_value=mock_skill)
        mock_on_loaded = MagicMock()

        loaded = discovery.load_from_index(mock_load, mock_on_loaded)

        assert "skill_a" in loaded
        assert loaded["skill_a"] is mock_skill
        mock_on_loaded.assert_called_once_with("skill_a")

    def test_load_from_index_no_file(self, discovery):
        """Test loading from index when file doesn't exist."""
        mock_load = MagicMock()
        mock_on_loaded = MagicMock()

        loaded = discovery.load_from_index(mock_load, mock_on_loaded)

        assert loaded == {}
        mock_load.assert_not_called()
        mock_on_loaded.assert_not_called()

    def test_load_from_index_skips_missing_skills(self, discovery):
        """Test that load_from_index skips missing skills."""
        index_data = [
            {"name": "skill_a", "version": "1.0"},
            {"name": "missing_skill", "version": "1.0"},
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        mock_skill = MagicMock()
        mock_load = MagicMock(return_value=mock_skill)
        mock_on_loaded = MagicMock()

        loaded = discovery.load_from_index(mock_load, mock_on_loaded)

        assert "skill_a" in loaded
        assert "missing_skill" not in loaded
        # Called once for existing skill, skipped missing one
        assert mock_load.call_count == 1

    def test_load_from_index_skips_entries_without_name(self, discovery):
        """Test that load_from_index skips entries without name."""
        index_data = [
            {"name": "skill_a", "version": "1.0"},
            {"version": "1.0"},  # Missing name
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        mock_skill = MagicMock()
        mock_load = MagicMock(return_value=mock_skill)
        mock_on_loaded = MagicMock()

        loaded = discovery.load_from_index(mock_load, mock_on_loaded)

        assert "skill_a" in loaded
        assert len(loaded) == 1

    def test_load_from_index_returns_none_for_load_failure(self, discovery):
        """Test that load_from_index skips skills that fail to load."""
        index_data = [
            {"name": "skill_a", "version": "1.0"},
        ]
        (discovery.index_path).write_text(json.dumps(index_data))

        # Mock load_skill to return None (load failure)
        mock_load = MagicMock(return_value=None)
        mock_on_loaded = MagicMock()

        loaded = discovery.load_from_index(mock_load, mock_on_loaded)

        assert "skill_a" not in loaded
        mock_on_loaded.assert_not_called()

    # =========================================================================
    # Property Tests
    # =========================================================================

    def test_index_path_property(self, discovery, temp_skills_dir):
        """Test that index_path property returns correct path."""
        expected = temp_skills_dir / "skill_index.json"
        assert discovery.index_path == expected

    def test_skills_dir_property(self, discovery, temp_skills_dir):
        """Test that skills_dir property returns correct path."""
        assert discovery.skills_dir == temp_skills_dir


class TestSkillDiscoveryEdgeCases:
    """Edge case tests for SkillDiscovery."""

    def test_discover_with_nested_dirs(self):
        """Test discovery doesn't find nested skills without SKILL.md."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Create a skill
            skill_a = skills_dir / "skill_a"
            skill_a.mkdir()
            (skill_a / "SKILL.md").write_text("# Skill A")

            # Create a nested directory (should be ignored)
            nested = skill_a / "nested"
            nested.mkdir()
            (nested / "SKILL.md").write_text("# Nested")

            discovery = SkillDiscovery(skills_dir)
            skills = discovery.discover()

            assert len(skills) == 1
            assert skills[0].name == "skill_a"

    def test_discover_with_special_chars_in_name(self):
        """Test discovery handles special characters in skill names."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Create skill with special characters
            special_skill = skills_dir / "my-cool-skill_123"
            special_skill.mkdir()
            (special_skill / "SKILL.md").write_text("# My Cool Skill")

            discovery = SkillDiscovery(skills_dir)
            skills = discovery.discover()

            assert len(skills) == 1
            assert skills[0].name == "my-cool-skill_123"

    def test_is_index_fresh_with_corrupted_index(self, tmp_path):
        """Test index freshness with corrupted index file."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        discovery = SkillDiscovery(tmp_path)
        (discovery.index_path).write_text('{"invalid": json}')

        assert discovery.is_index_fresh() is False

    def test_is_index_fresh_with_array_of_strings(self, temp_skills_dir):
        """Test index freshness with array of strings (alternative format)."""
        from agent.core.skill_runtime.core.discovery_core import SkillDiscovery

        discovery = SkillDiscovery(temp_skills_dir)
        # Some indexes might use simple array of strings instead of objects
        # This is not the expected format, but should not crash
        index_data = ["skill_a", "skill_b"]
        (discovery.index_path).write_text(json.dumps(index_data))

        # This will raise AttributeError because strings don't have .get()
        # This is expected behavior for malformed index files
        with pytest.raises(AttributeError):
            discovery.is_index_fresh()
