"""
tests/unit/test_skill_manifest.py
Phase 33: Unit tests for SKILL.md Standardization (Pure SKILL.md)

Tests for:
- SkillManifestLoader
- SkillMetadata
- SkillDefinition
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.skills.core.skill_manifest import (
    ExecutionMode,
    RoutingStrategy,
    SkillDefinition,
    SkillMetadata,
    SkillManifestModel,
    SKILL_FILE,
)
from agent.skills.core.skill_manifest_loader import SkillManifestLoader


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skill directory."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    return skill_dir


@pytest.fixture
def sample_skill_md(temp_skill_dir: Path) -> Path:
    """Create a sample SKILL.md file."""
    content = """---
name: test-skill
version: 1.2.0
description: A test skill for unit testing
execution_mode: library
routing_keywords: ["test", "sample", "demo"]
routing_strategy: keyword
intents: ["test", "verify"]
authors: ["test-team"]
dependencies:
  python: {}
permissions:
  network: false
---

# Test Skill Instructions

Use this skill for testing purposes.
This is the system prompt content.
"""
    (temp_skill_dir / SKILL_FILE).write_text(content)
    return temp_skill_dir


# =============================================================================
# SkillMetadata Tests
# =============================================================================


class TestSkillMetadata:
    """Tests for SkillMetadata dataclass."""

    def test_create_minimal(self):
        """Test creating SkillMetadata with minimal fields."""
        meta = SkillMetadata(name="test", version="1.0.0")

        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.execution_mode == ExecutionMode.LIBRARY

    def test_create_full(self):
        """Test creating SkillMetadata with all fields."""
        meta = SkillMetadata(
            name="git-expert",
            version="2.1.0",
            description="Advanced Git operations",
            authors=["omni-team"],
            execution_mode=ExecutionMode.LIBRARY,
            routing_strategy=RoutingStrategy.KEYWORD,
            routing_keywords=["git", "commit"],
            intents=["version-control"],
            dependencies={"python": {}},
            permissions={"network": True},
        )

        assert meta.name == "git-expert"
        assert meta.version == "2.1.0"
        assert meta.authors == ["omni-team"]
        assert meta.permissions.get("network") is True

    def test_to_dict(self):
        """Test converting SkillMetadata to dictionary."""
        meta = SkillMetadata(
            name="test",
            version="1.0.0",
            execution_mode=ExecutionMode.SUBPROCESS,
        )

        result = meta.to_dict()

        assert result["name"] == "test"
        assert result["version"] == "1.0.0"
        assert result["execution_mode"] == "subprocess"


# =============================================================================
# SkillManifestModel Tests
# =============================================================================


class TestSkillManifestModel:
    """Tests for SkillManifestModel Pydantic model."""

    def test_valid_model(self):
        """Test creating valid Pydantic model."""
        model = SkillManifestModel(
            name="test-skill",
            version="1.0.0",
            description="Test description",
            authors=["test-team"],
        )

        assert model.name == "test-skill"
        assert model.version == "1.0.0"

    def test_to_metadata(self):
        """Test converting Pydantic model to SkillMetadata."""
        model = SkillManifestModel(
            name="test",
            version="1.0.0",
            execution_mode=ExecutionMode.SUBPROCESS,
        )

        metadata = model.to_metadata()

        assert isinstance(metadata, SkillMetadata)
        assert metadata.name == "test"
        assert metadata.execution_mode == ExecutionMode.SUBPROCESS

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(Exception):
            SkillManifestModel(description="No name or version")


# =============================================================================
# SkillManifestLoader Tests
# =============================================================================


class TestSkillManifestLoader:
    """Tests for SkillManifestLoader (SKILL.md only)."""

    def test_skill_file_exists_true(self, temp_skill_dir: Path):
        """Test SKILL.md file exists check."""
        (temp_skill_dir / SKILL_FILE).touch()
        loader = SkillManifestLoader()

        assert loader.skill_file_exists(temp_skill_dir) is True

    def test_skill_file_exists_false(self, temp_skill_dir: Path):
        """Test SKILL.md file does not exist."""
        loader = SkillManifestLoader()

        assert loader.skill_file_exists(temp_skill_dir) is False

    @pytest.mark.asyncio
    async def test_load_metadata(self, sample_skill_md: Path):
        """Test loading metadata from SKILL.md."""
        loader = SkillManifestLoader()
        metadata = await loader.load_metadata(sample_skill_md)

        assert metadata is not None
        assert metadata.name == "test-skill"
        assert metadata.version == "1.2.0"
        assert metadata.description == "A test skill for unit testing"
        assert metadata.execution_mode == ExecutionMode.LIBRARY
        assert "test" in metadata.routing_keywords

    async def test_load_definition(self, sample_skill_md: Path):
        """Test loading complete definition from SKILL.md."""
        loader = SkillManifestLoader()

        definition = await loader.load_definition(sample_skill_md)

        assert definition is not None
        assert "Test Skill Instructions" in definition.system_prompt
        assert definition.metadata.name == "test-skill"

    async def test_missing_required_field(self, temp_skill_dir: Path):
        """Test error when required field is missing."""
        content = """---
name: test-skill
---
"""
        (temp_skill_dir / SKILL_FILE).write_text(content)
        loader = SkillManifestLoader()

        metadata = await loader.load_metadata(temp_skill_dir)

        assert metadata is None

    async def test_empty_directory(self, temp_skill_dir: Path):
        """Test handling empty directory."""
        loader = SkillManifestLoader()

        metadata = await loader.load_metadata(temp_skill_dir)

        assert metadata is None

    async def test_missing_version_field(self, temp_skill_dir: Path):
        """Test error when version field is missing."""
        content = """---
name: test-skill
description: No version
---
"""
        (temp_skill_dir / SKILL_FILE).write_text(content)
        loader = SkillManifestLoader()

        metadata = await loader.load_metadata(temp_skill_dir)

        assert metadata is None

    async def test_invalid_yaml_frontmatter(self, temp_skill_dir: Path):
        """Test handling invalid YAML frontmatter."""
        content = """---
invalid yaml: [[[
---

# Content
"""
        (temp_skill_dir / SKILL_FILE).write_text(content)
        loader = SkillManifestLoader()

        metadata = await loader.load_metadata(temp_skill_dir)

        assert metadata is None


# =============================================================================
# Version Comparison Tests
# =============================================================================


class TestVersionComparison:
    """Tests for version parsing and comparison."""

    def test_parse_version_simple(self):
        """Test parsing simple version string."""
        result = SkillManifestLoader.parse_version("1.2.0")

        assert result == (1, 2, 0)

    def test_parse_version_partial(self):
        """Test parsing version with fewer parts."""
        result = SkillManifestLoader.parse_version("2.0")

        assert result == (2, 0, 0)

    def test_parse_version_single(self):
        """Test parsing single-part version."""
        result = SkillManifestLoader.parse_version("3")

        assert result == (3, 0, 0)

    def test_compare_versions_equal(self):
        """Test comparing equal versions."""
        result = SkillManifestLoader.compare_versions("1.2.0", "1.2.0")

        assert result == 0

    def test_compare_versions_greater(self):
        """Test comparing when v1 > v2."""
        result = SkillManifestLoader.compare_versions("2.0.0", "1.0.0")

        assert result == 1

    def test_compare_versions_less(self):
        """Test comparing when v1 < v2."""
        result = SkillManifestLoader.compare_versions("1.0.0", "2.0.0")

        assert result == -1

    def test_compare_versions_minor(self):
        """Test comparing minor version differences."""
        result = SkillManifestLoader.compare_versions("1.2.0", "1.3.0")

        assert result == -1

    def test_compare_versions_patch(self):
        """Test comparing patch version differences."""
        result = SkillManifestLoader.compare_versions("1.2.1", "1.2.0")

        assert result == 1
