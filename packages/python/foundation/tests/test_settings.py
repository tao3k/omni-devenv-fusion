"""
Settings Tests - Simplified

Tests for omni.foundation.config.settings module (basic functionality only).
"""


class TestSettingsClass:
    """Test the Settings singleton class."""

    def test_singleton_pattern(self):
        """Test that Settings is a singleton."""
        from omni.foundation.config.settings import Settings

        # Reset singleton for test
        Settings._instance = None
        Settings._loaded = False

        settings1 = Settings()
        settings2 = Settings()

        assert settings1 is settings2

    def test_get_with_default(self):
        """Test get() method with default value."""
        from omni.foundation.config.settings import Settings

        # Reset singleton
        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        result = settings.get("nonexistent.key", "default_value")

        assert result == "default_value"

    def test_get_path_returns_empty_string_for_missing(self):
        """Test get_path() returns empty string for missing keys."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        result = settings.get_path("missing.key")

        assert result == ""

    def test_get_list_returns_empty_list_for_missing(self):
        """Test get_list() returns empty list for missing keys."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        result = settings.get_list("missing.key")

        assert result == []

    def test_has_setting(self):
        """Test has_setting() method."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        assert settings.has_setting("totally.fake.key") is False

    def test_get_section(self):
        """Test get_section() method."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        section = settings.get_section("nonexistent")

        assert isinstance(section, dict)
        assert section == {}

    def test_list_sections(self):
        """Test list_sections() method."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        sections = settings.list_sections()

        assert isinstance(sections, list)

    def test_conf_dir_property(self):
        """Test conf_dir property."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        conf_dir = settings.conf_dir

        assert isinstance(conf_dir, str)


class TestGetSettingFunction:
    """Test the get_setting() convenience function."""

    def test_get_setting_with_default(self):
        """Test get_setting() with default value."""
        from omni.foundation.config.settings import get_setting

        result = get_setting("nonexistent.key", "default")
        assert result == "default"

    def test_get_setting_missing_returns_default(self):
        """Test get_setting() returns None default for missing keys."""
        from omni.foundation.config.settings import get_setting

        result = get_setting("totally.fake.key")
        assert result is None


class TestConfigPathFunctions:
    """Test configuration path functions."""

    def test_get_config_path(self):
        """Test get_config_path() function."""
        from omni.foundation.config.settings import get_config_path

        result = get_config_path("missing.key")
        assert result == ""

    def test_has_setting_function(self):
        """Test has_setting() function."""
        from omni.foundation.config.settings import has_setting

        result = has_setting("fake.missing.key")
        assert result is False

    def test_get_conf_directory(self):
        """Test get_conf_directory() function."""
        from omni.foundation.config.settings import get_conf_directory

        result = get_conf_directory()
        assert isinstance(result, str)
        assert len(result) > 0


class TestYamlFallback:
    """Test YAML parsing fallback when PyYAML is not available."""

    def test_parse_simple_yaml_basic(self):
        """Test simple YAML parsing for basic structure."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        content = """
config:
  key1: value1
  key2: value2
section2:
  list_key: [item1, item2]
"""
        result = settings._parse_simple_yaml(content)

        assert "config" in result
        assert result["config"]["key1"] == "value1"
        assert result["config"]["key2"] == "value2"

    def test_parse_yaml_empty_content(self):
        """Test parsing empty YAML content."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        result = settings._parse_simple_yaml("")

        assert result == {}

    def test_parse_yaml_with_comments(self):
        """Test parsing YAML with comments."""
        from omni.foundation.config.settings import Settings

        Settings._instance = None
        Settings._loaded = False

        settings = Settings()
        content = """
# This is a comment
config:
  key: value
"""
        result = settings._parse_simple_yaml(content)

        assert "config" in result
        assert result["config"]["key"] == "value"
