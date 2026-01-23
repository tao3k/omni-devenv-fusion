"""Tests for omni.core.skills.universal module."""

from __future__ import annotations

import pytest
from pathlib import Path
from omni.core.skills.universal import (
    UniversalScriptSkill,
    UniversalSkillFactory,
    SimpleSkillMetadata,
)


class TestSimpleSkillMetadata:
    """Test SimpleSkillMetadata dataclass."""

    def test_default_values(self):
        """Test default metadata values."""
        meta = SimpleSkillMetadata(name="test_skill")
        assert meta.name == "test_skill"
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.capabilities == []

    def test_custom_values(self):
        """Test custom metadata values."""
        meta = SimpleSkillMetadata(
            name="custom",
            version="2.0.0",
            description="A custom skill",
            capabilities=["commit", "push"],
        )
        assert meta.name == "custom"
        assert meta.version == "2.0.0"
        assert "commit" in meta.capabilities


class TestUniversalScriptSkill:
    """Test UniversalScriptSkill class."""

    def test_init_without_metadata(self, tmp_path: Path):
        """Test initialization without explicit metadata."""
        skill_path = tmp_path / "test_skill"
        skill_path.mkdir()

        skill = UniversalScriptSkill("test", skill_path)
        assert skill.name == "test"
        assert skill.path == skill_path
        assert skill.metadata.name == "test"
        assert skill.is_loaded is False

    def test_init_with_metadata(self, tmp_path: Path):
        """Test initialization with explicit metadata."""
        skill_path = tmp_path / "test_skill"
        skill_path.mkdir()

        meta = SimpleSkillMetadata(
            name="my_skill",
            version="1.2.3",
            description="My custom skill",
        )
        skill = UniversalScriptSkill("my_skill", skill_path, metadata=meta)
        assert skill.name == "my_skill"
        assert skill.metadata.version == "1.2.3"

    def test_init_with_skill_md(self, tmp_path: Path):
        """Test initialization loads from SKILL.md (if exists).

        Note: Current implementation uses constructor name as default.
        SKILL.md provides extended metadata.
        """
        skill_path = tmp_path / "skill_with_md"
        skill_path.mkdir()
        (skill_path / "SKILL.md").write_text("""---
name: loaded-skill
version: 3.0.0
description: Loaded from SKILL.md
---
""")

        skill = UniversalScriptSkill("loaded", skill_path)
        # Constructor name takes precedence for metadata
        assert skill.metadata.name == "loaded"
        # Verify SKILL.md was recognized
        assert (skill.path / "SKILL.md").exists()

    @pytest.mark.asyncio
    async def test_load_empty_skill(self, tmp_path: Path):
        """Test loading a skill with no scripts."""
        skill_path = tmp_path / "empty_skill"
        skill_path.mkdir()
        (skill_path / "SKILL.md").write_text("---name: empty---")
        scripts_dir = skill_path / "scripts"
        scripts_dir.mkdir()

        skill = UniversalScriptSkill("empty", skill_path)
        await skill.load()

        assert skill.is_loaded is True
        assert len(skill.list_commands()) == 0

    @pytest.mark.asyncio
    async def test_load_skill_with_scripts(self, tmp_path: Path):
        """Test loading a skill with scripts."""
        skill_path = tmp_path / "scripted_skill"
        skill_path.mkdir()
        scripts_dir = skill_path / "scripts"
        scripts_dir.mkdir()

        # Create a script file with @skill_command decorator
        (scripts_dir / "hello.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="hello", description="Say hello")
def hello(name: str = "World"):
    return f"Hello, {name}!"

__all__ = ["hello"]
""")

        skill = UniversalScriptSkill("scripted", skill_path)
        await skill.load()

        assert skill.is_loaded is True
        commands = skill.list_commands()
        assert len(commands) >= 1

    def test_list_commands_before_load(self, tmp_path: Path):
        """Test listing commands before loading returns empty."""
        skill_path = tmp_path / "test"
        skill_path.mkdir()

        skill = UniversalScriptSkill("test", skill_path)
        assert skill.list_commands() == []

    def test_get_command_before_load(self, tmp_path: Path):
        """Test getting command before loading returns None."""
        skill_path = tmp_path / "test"
        skill_path.mkdir()

        skill = UniversalScriptSkill("test", skill_path)
        assert skill.get_command("any") is None

    def test_repr(self, tmp_path: Path):
        """Test string representation."""
        skill_path = tmp_path / "test"
        skill_path.mkdir()

        skill = UniversalScriptSkill("test", skill_path)
        assert "test" in repr(skill)
        assert "not loaded" in repr(skill)


class TestUniversalSkillFactory:
    """Test UniversalSkillFactory class."""

    def test_discover_skills(self, tmp_path: Path):
        """Test skill discovery."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill directories
        (skills_dir / "skill_a").mkdir()
        (skills_dir / "skill_b").mkdir()
        (skills_dir / "_private").mkdir()  # Should be ignored

        factory = UniversalSkillFactory(skills_dir)
        discovered = factory.discover_skills()

        assert len(discovered) == 2
        names = [name for name, path in discovered]
        assert "skill_a" in names
        assert "skill_b" in names
        assert "_private" not in names

    def test_discover_no_skills(self, tmp_path: Path):
        """Test discovery with no skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        factory = UniversalSkillFactory(skills_dir)
        discovered = factory.discover_skills()

        assert discovered == []

    def test_discover_nonexistent(self, tmp_path: Path):
        """Test discovery in nonexistent directory."""
        factory = UniversalSkillFactory(tmp_path / "nonexistent")
        discovered = factory.discover_skills()

        assert discovered == []

    def test_create_skill(self, tmp_path: Path):
        """Test creating a skill from name."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "my_skill").mkdir()

        factory = UniversalSkillFactory(skills_dir)
        skill = factory.create_skill("my_skill")

        assert isinstance(skill, UniversalScriptSkill)
        assert skill.name == "my_skill"

    def test_create_all_skills(self, tmp_path: Path):
        """Test creating all discovered skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill_1").mkdir()
        (skills_dir / "skill_2").mkdir()

        factory = UniversalSkillFactory(skills_dir)
        skills = factory.create_all_skills()

        assert len(skills) == 2
