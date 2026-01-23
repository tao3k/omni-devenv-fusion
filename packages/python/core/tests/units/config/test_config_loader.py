"""
Tests for omni.core.config.loader
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSkillLimitsConfig:
    """Test SkillLimitsConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        from omni.core.config.loader import SkillLimitsConfig

        config = SkillLimitsConfig()
        assert config.dynamic_tools == 15
        assert config.core_min == 3
        assert config.rerank_threshold == 20
        assert config.schema_cache_ttl == 300
        assert config.auto_optimize is True

    def test_custom_values(self):
        """Test custom values."""
        from omni.core.config.loader import SkillLimitsConfig

        config = SkillLimitsConfig(
            dynamic_tools=20,
            core_min=5,
            rerank_threshold=30,
            schema_cache_ttl=600,
            auto_optimize=False,
        )
        assert config.dynamic_tools == 20
        assert config.core_min == 5
        assert config.rerank_threshold == 30
        assert config.schema_cache_ttl == 600
        assert config.auto_optimize is False


class TestFilterCommandsConfig:
    """Test FilterCommandsConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        from omni.core.config.loader import FilterCommandsConfig

        config = FilterCommandsConfig()
        assert config.commands == []

    def test_custom_values(self):
        """Test custom values."""
        from omni.core.config.loader import FilterCommandsConfig

        config = FilterCommandsConfig(commands=["terminal.run_command", "terminal.run_task"])
        assert len(config.commands) == 2
        assert "terminal.run_command" in config.commands


class TestLoadSkillLimits:
    """Test load_skill_limits function."""

    def test_loads_defaults_on_error(self):
        """Test that defaults are used when settings fail to load."""
        from omni.core.config.loader import load_skill_limits, reset_config

        reset_config()

        with patch(
            "omni.foundation.config.settings.get_settings",
            side_effect=Exception("Settings error"),
        ):
            config = load_skill_limits()
            assert config.dynamic_tools == 15
            assert config.core_min == 3

    def test_singleton_behavior(self):
        """Test that config is cached after first load."""
        from omni.core.config.loader import load_skill_limits, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = [
                25,  # dynamic_tools
                4,  # core_min
                35,  # rerank_threshold
                500,  # schema_cache_ttl
                False,  # auto_optimize
            ]
            mock_settings.return_value = mock_instance

            config1 = load_skill_limits()
            config2 = load_skill_limits()

            # Should be same instance (singleton)
            assert config1 is config2
            # Should only have called get_settings once
            assert mock_settings.call_count == 1


class TestLoadFilterCommands:
    """Test load_filter_commands function."""

    def test_loads_defaults_on_error(self):
        """Test that defaults are used when settings fail to load."""
        from omni.core.config.loader import load_filter_commands, reset_config

        reset_config()

        with patch(
            "omni.foundation.config.settings.get_settings",
            side_effect=Exception("Settings error"),
        ):
            config = load_filter_commands()
            assert config.commands == []

    def test_loads_list_format(self):
        """Test loading filter commands as a list."""
        from omni.core.config.loader import load_filter_commands, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = [
                "terminal.run_command",
                "terminal.run_task",
            ]
            mock_settings.return_value = mock_instance

            config = load_filter_commands()
            assert len(config.commands) == 2
            assert "terminal.run_command" in config.commands


class TestIsFiltered:
    """Test is_filtered function."""

    def test_filters_matching_command(self):
        """Test that matching command is filtered."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = ["terminal.run_command"]
            mock_settings.return_value = mock_instance

            assert is_filtered("terminal.run_command") is True
            assert is_filtered("git.status") is False

    def test_empty_filter_list(self):
        """Test with empty filter list."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = []
            mock_settings.return_value = mock_instance

            assert is_filtered("terminal.run_command") is False


class TestResetConfig:
    """Test reset_config function."""

    def test_resets_singletons(self):
        """Test that reset_config clears cached configs."""
        from omni.core.config.loader import (
            load_skill_limits,
            load_filter_commands,
            reset_config,
        )

        reset_config()

        # Load configs
        limits1 = load_skill_limits()
        filter1 = load_filter_commands()

        # Reset
        reset_config()

        # Load again - should get new instances
        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = [
                30,  # dynamic_tools
                10,  # core_min
                50,  # rerank_threshold
                100,  # schema_cache_ttl
                True,  # auto_optimize
                ["new.filtered.command"],  # filter_commands
            ]
            mock_settings.return_value = mock_instance

            limits2 = load_skill_limits()
            filter2 = load_filter_commands()

            # Should be different instances
            assert limits1 is not limits2
            assert filter1 is not filter2
