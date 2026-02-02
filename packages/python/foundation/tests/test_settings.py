"""
Settings Tests - Simplified

Tests for omni.foundation.config.settings module (basic functionality only).
Uses clean_settings fixture for isolation.
"""

import pytest


class TestSettingsClass:
    """Test the Settings singleton class."""

    def test_singleton_pattern(self, clean_settings):
        """Test that Settings is a singleton."""
        from omni.foundation.config.settings import Settings

        # clean_settings is one instance
        settings1 = Settings()
        assert settings1 is clean_settings

        settings2 = Settings()
        assert settings1 is settings2

    def test_get_with_default(self, clean_settings):
        """Test get() method with default value."""
        result = clean_settings.get("nonexistent.key", "default_value")
        assert result == "default_value"

    def test_get_path_returns_empty_string_for_missing(self, clean_settings):
        """Test get_path() returns empty string for missing keys."""
        result = clean_settings.get_path("missing.key")
        assert result == ""

    def test_get_list_returns_empty_list_for_missing(self, clean_settings):
        """Test get_list() returns empty list for missing keys."""
        result = clean_settings.get_list("missing.key")
        assert result == []

    def test_has_setting(self, clean_settings):
        """Test has_setting() method."""
        assert clean_settings.has_setting("totally.fake.key") is False

    def test_get_section(self, clean_settings):
        """Test get_section() method."""
        section = clean_settings.get_section("nonexistent")
        assert isinstance(section, dict)
        assert section == {}

    def test_list_sections(self, clean_settings):
        """Test list_sections() method."""
        sections = clean_settings.list_sections()
        assert isinstance(sections, list)

    def test_conf_dir_property(self, clean_settings):
        """Test conf_dir property."""
        conf_dir = clean_settings.conf_dir
        assert isinstance(conf_dir, str)


class TestGetSettingFunction:
    """Test the get_setting() convenience function."""

    def test_get_setting_with_default(self, clean_settings):
        """Test get_setting() with default value."""
        from omni.foundation.config.settings import get_setting

        result = get_setting("nonexistent.key", "default")
        assert result == "default"

    def test_get_setting_missing_returns_default(self, clean_settings):
        """Test get_setting() returns None default for missing keys."""
        from omni.foundation.config.settings import get_setting

        result = get_setting("totally.fake.key")
        assert result is None


class TestConfigPathFunctions:
    """Test configuration path functions."""

    def test_get_config_path(self, clean_settings):
        """Test get_config_path() function."""
        from omni.foundation.config.settings import get_config_path

        result = get_config_path("missing.key")
        assert result == ""

    def test_has_setting_function(self, clean_settings):
        """Test has_setting() function."""
        from omni.foundation.config.settings import has_setting

        result = has_setting("fake.missing.key")
        assert result is False

    def test_get_conf_directory(self, clean_settings):
        """Test get_conf_directory() function."""
        from omni.foundation.config.settings import get_conf_directory

        result = get_conf_directory()
        assert isinstance(result, str)
        assert len(result) > 0


class TestYamlFallback:
    """Test YAML parsing fallback when PyYAML is not available."""

    def test_parse_simple_yaml_basic(self, clean_settings):
        """Test simple YAML parsing for basic structure."""
        content = """
config:
  key1: value1
  key2: value2
section2:
  list_key: [item1, item2]
"""
        result = clean_settings._parse_simple_yaml(content)

        assert "config" in result
        assert result["config"]["key1"] == "value1"
        assert result["config"]["key2"] == "value2"

    def test_parse_yaml_empty_content(self, clean_settings):
        """Test parsing empty YAML content."""
        result = clean_settings._parse_simple_yaml("")
        assert result == {}

    def test_parse_yaml_with_comments(self, clean_settings):
        """Test parsing YAML with comments."""
        content = """
# This is a comment
config:
  key: value
"""
        result = clean_settings._parse_simple_yaml(content)
        assert "config" in result
        assert result["config"]["key"] == "value"
