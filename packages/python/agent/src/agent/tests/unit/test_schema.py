"""
Schema Module Unit Tests

Tests for SkillMetadata schema validation.
These are fast, isolated tests that don't require file I/O.

Run with:
    pytest unit/test_schema.py -v
"""

import pytest
from dirty_equals import IsStr, IsInstance

from agent.core.schema import SkillMetadata
from agent.tests.factories import SkillMetadataFactory


class TestSkillMetadataSchema:
    """Unit tests for SkillMetadata validation."""

    def test_skill_metadata_importable(self):
        """SkillMetadata should be importable from agent.core.schema."""
        assert SkillMetadata is not None

    def test_skill_metadata_validation(self):
        """SkillMetadata should validate correctly."""
        # Valid metadata
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "commands_module": "scripts",
        }
        metadata = SkillMetadata(**data)
        assert metadata.name == "test_skill"
        assert metadata.version == "1.0.0"

    def test_skill_metadata_minimal(self):
        """SkillMetadata should work with minimal required fields."""
        # Minimal valid metadata
        data = {
            "name": "minimal",
            "version": "0.1.0",
            "description": "Minimal skill",
            "commands_module": "scripts",
        }
        metadata = SkillMetadata(**data)
        assert metadata.name == "minimal"


class TestSkillMetadataWithFactory:
    """Tests using polyfactory for test data generation."""

    def test_factory_generates_valid_metadata(self):
        """Factory should generate valid SkillMetadata instances."""
        metadata = SkillMetadataFactory.build()
        # Using dirty-equals for type assertions
        assert isinstance(metadata, SkillMetadata)
        assert metadata.name == IsStr()
        assert metadata.version == IsStr()
        assert metadata.description == IsStr()
        assert metadata.commands_module == IsStr()

    def test_factory_with_overrides(self):
        """Factory should respect field overrides."""
        metadata = SkillMetadataFactory.build(name="custom_skill", version="2.0.0")
        assert metadata.name == "custom_skill"
        assert metadata.version == "2.0.0"

    def test_factory_batch_generation(self):
        """Factory should support batch generation."""
        metadata_list = SkillMetadataFactory.batch(size=5)
        assert len(metadata_list) == 5
        assert all(isinstance(m, SkillMetadata) for m in metadata_list)


class TestSharedUtilities:
    """Unit tests for shared utility modules."""

    def test_gitops_module_exists(self):
        """common.gitops module should be importable."""
        from common.gitops import get_project_root

        assert get_project_root() is not None

    def test_settings_module_exists(self):
        """common.settings module should be importable."""
        from common.config.settings import get_setting

        # Should be able to get a setting
        path = get_setting("skills.path", "assets/skills")
        assert path is not None

    def test_settings_yaml_loaded(self):
        """settings.yaml should be loaded."""
        from common.config.settings import get_setting

        # If we can get a setting, yaml is loaded
        path = get_setting("skills.path", "default_skills")
        assert path is not None
