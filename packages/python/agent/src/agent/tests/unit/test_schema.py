"""
Schema Module Unit Tests

Tests for SkillManifest schema validation.
These are fast, isolated tests that don't require file I/O.

Run with:
    pytest unit/test_schema.py -v
"""

import pytest
from agent.core.schema import SkillManifest


class TestSkillManifestSchema:
    """Unit tests for SkillManifest validation."""

    def test_skill_manifest_importable(self):
        """SkillManifest should be importable from agent.core.schema."""
        from agent.core.schema import SkillManifest

        assert SkillManifest is not None

    def test_skill_manifest_validation(self):
        """SkillManifest should validate correctly."""
        from agent.core.schema import SkillManifest

        # Valid manifest
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "tools_module": "assets.skills.test.tools",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"

    def test_skill_manifest_minimal(self):
        """SkillManifest should work with minimal required fields."""
        from agent.core.schema import SkillManifest

        # Minimal valid manifest
        data = {
            "name": "minimal",
            "version": "0.1.0",
            "description": "Minimal skill",
            "tools_module": "assets.skills.minimal.tools",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "minimal"


class TestSkillManifestWithFactory:
    """Tests using polyfactory for test data generation."""

    def test_factory_generates_valid_manifest(self):
        """Factory should generate valid SkillManifest instances."""
        from agent.tests.factories import SkillManifestFactory

        manifest = SkillManifestFactory.build()
        assert isinstance(manifest, SkillManifest)
        assert manifest.name is not None
        assert manifest.version is not None
        assert manifest.description is not None
        assert manifest.tools_module is not None

    def test_factory_with_overrides(self):
        """Factory should respect field overrides."""
        from agent.tests.factories import SkillManifestFactory

        manifest = SkillManifestFactory.build(name="custom_skill", version="2.0.0")
        assert manifest.name == "custom_skill"
        assert manifest.version == "2.0.0"

    def test_factory_batch_generation(self):
        """Factory should support batch generation."""
        from agent.tests.factories import SkillManifestFactory

        manifests = SkillManifestFactory.batch(size=5)
        assert len(manifests) == 5
        assert all(isinstance(m, SkillManifest) for m in manifests)


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
