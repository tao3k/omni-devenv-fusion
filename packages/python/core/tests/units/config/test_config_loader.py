"""
Tests for omni.core.config.loader
"""

from unittest.mock import MagicMock, patch


class TestCommandOverride:
    """Test CommandOverride dataclass."""

    def test_defaults(self):
        """Test default values."""
        from omni.core.config.loader import CommandOverride

        config = CommandOverride()
        assert config.alias is None
        assert config.append_doc is None

    def test_custom_values(self):
        """Test custom values."""
        from omni.core.config.loader import CommandOverride

        config = CommandOverride(
            alias="save_memory", append_doc="Use this to persist important rules."
        )
        assert config.alias == "save_memory"
        assert "persist" in config.append_doc


class TestOverridesConfig:
    """Test OverridesConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        from omni.core.config.loader import OverridesConfig

        config = OverridesConfig()
        assert config.commands == {}

    def test_aliases_property(self):
        """Test aliases property builds reverse lookup."""
        from omni.core.config.loader import OverridesConfig, CommandOverride

        config = OverridesConfig(
            commands={
                "memory.remember_insight": CommandOverride(alias="save_memory"),
                "git.commit": CommandOverride(alias="git_commit"),
            }
        )

        aliases = config.aliases
        assert aliases["save_memory"] == "memory.remember_insight"
        assert aliases["git_commit"] == "git.commit"

    def test_aliases_skips_none(self):
        """Test aliases property skips commands without alias."""
        from omni.core.config.loader import OverridesConfig, CommandOverride

        config = OverridesConfig(
            commands={
                "memory.remember_insight": CommandOverride(alias="save_memory"),
                "git.status": CommandOverride(alias=None),  # No alias
            }
        )

        aliases = config.aliases
        assert "save_memory" in aliases
        assert "git.status" not in aliases


class TestLoadCommandOverrides:
    """Test load_command_overrides function."""

    def test_loads_defaults_on_error(self):
        """Test that defaults are used when settings fail to load."""
        from omni.core.config.loader import load_command_overrides, reset_config

        reset_config()

        with patch(
            "omni.foundation.config.settings.get_settings",
            side_effect=Exception("Settings error"),
        ):
            config = load_command_overrides()
            assert config.commands == {}

    def test_loads_from_settings(self):
        """Test loading overrides from settings.yaml."""
        from omni.core.config.loader import load_command_overrides, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "memory.remember_insight": {
                    "alias": "save_memory",
                    "append_doc": "Persist important context.",
                },
                "git.commit": {
                    "alias": "git_commit",
                },
            }
            mock_settings.return_value = mock_instance

            config = load_command_overrides()
            assert len(config.commands) == 2

            # Check memory.remember_insight override
            mem_override = config.commands["memory.remember_insight"]
            assert mem_override.alias == "save_memory"
            assert "Persist" in mem_override.append_doc

            # Check git.commit override
            git_override = config.commands["git.commit"]
            assert git_override.alias == "git_commit"
            assert git_override.append_doc is None

    def test_singleton_behavior(self):
        """Test that config is cached after first load."""
        from omni.core.config.loader import load_command_overrides, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {"memory.remember_insight": {"alias": "save_memory"}}
            mock_settings.return_value = mock_instance

            config1 = load_command_overrides()
            config2 = load_command_overrides()

            # Should be same instance (singleton)
            assert config1 is config2
            # Should only have called get_settings once
            assert mock_settings.call_count == 1


class TestResolveAlias:
    """Test resolve_alias function."""

    def test_resolves_existing_alias(self):
        """Test resolving an existing alias."""
        from omni.core.config.loader import resolve_alias, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {"memory.remember_insight": {"alias": "save_memory"}}
            mock_settings.return_value = mock_instance

            result = resolve_alias("save_memory")
            assert result == "memory.remember_insight"

    def test_returns_none_for_unknown_alias(self):
        """Test that unknown aliases return None."""
        from omni.core.config.loader import resolve_alias, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {}
            mock_settings.return_value = mock_instance

            result = resolve_alias("unknown_alias")
            assert result is None


class TestGetCommandDisplay:
    """Test get_command_display function."""

    def test_returns_override(self):
        """Test that overrides are applied."""
        from omni.core.config.loader import get_command_display, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "memory.remember_insight": {
                    "alias": "save_memory",
                    "append_doc": "Persist important context.",
                }
            }
            mock_settings.return_value = mock_instance

            name, desc = get_command_display("memory.remember_insight")
            assert name == "save_memory"
            assert "Persist" in desc

    def test_returns_original_for_no_override(self):
        """Test that non-overridden commands return original."""
        from omni.core.config.loader import get_command_display, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {}
            mock_settings.return_value = mock_instance

            name, desc = get_command_display("git.status")
            assert name == "git.status"
            assert desc == "Execute git.status"


class TestBAMThreeModes:
    """Test all three Bi-directional Alias Mapping modes."""

    def test_mode1_verb_simplification(self):
        """Mode 1: Verb Simplification - Short verb alias for LLM attention.

        Config:
            memory.remember_insight:
              alias: "save_memory"

        LLM sees: "save_memory"
        Kernel executes: "memory.remember_insight"
        """
        from omni.core.config.loader import (
            load_command_overrides,
            resolve_alias,
            get_command_display,
            reset_config,
        )

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "memory.remember_insight": {
                    "alias": "save_memory",
                    "append_doc": "\n\nCRITICAL: Persist user preferences.",
                }
            }
            mock_settings.return_value = mock_instance

            # Test resolve_alias (incoming call_tool)
            canonical = resolve_alias("save_memory")
            assert canonical == "memory.remember_insight"

            # Test get_command_display (outgoing list_tools)
            name, desc = get_command_display("memory.remember_insight")
            assert name == "save_memory"
            assert "CRITICAL" in desc

    def test_mode2_namespace_rename(self):
        """Mode 2: Namespace Rename - Semantic correction with new namespace.

        Config:
            code_tools.replace_in_file:
              alias: "code.smart_edit"

        LLM sees: "code.smart_edit"
        Kernel executes: "code_tools.replace_in_file"
        """
        from omni.core.config.loader import (
            load_command_overrides,
            resolve_alias,
            get_command_display,
            reset_config,
        )

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "code_tools.replace_in_file": {
                    "alias": "code.smart_edit",
                    "append_doc": "\n\nPreferred for precise code modifications.",
                }
            }
            mock_settings.return_value = mock_instance

            # Test resolve_alias (incoming call_tool)
            canonical = resolve_alias("code.smart_edit")
            assert canonical == "code_tools.replace_in_file"

            # Test get_command_display (outgoing list_tools)
            name, desc = get_command_display("code_tools.replace_in_file")
            assert name == "code.smart_edit"
            assert "precise" in desc

    def test_mode3_documentation_only(self):
        """Mode 3: Documentation-only - No alias, just append_doc.

        Config:
            git.status:
              append_doc: "\n\nUse for structured git status."

        LLM sees: "git.status" (original name)
        Kernel executes: "git.status"
        Description: Enhanced with append_doc
        """
        from omni.core.config.loader import (
            load_command_overrides,
            resolve_alias,
            get_command_display,
            reset_config,
        )

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "git.status": {"append_doc": "\n\nUse this for structured git status output."}
            }
            mock_settings.return_value = mock_instance

            # Test resolve_alias - should return None (no alias)
            canonical = resolve_alias("git.status")
            assert canonical is None

            # Test get_command_display - name unchanged, desc enhanced
            name, desc = get_command_display("git.status")
            assert name == "git.status"  # Original name preserved
            assert "structured" in desc  # append_doc injected

    def test_mixed_modes_all_together(self):
        """Test all three modes loaded simultaneously."""
        from omni.core.config.loader import (
            load_command_overrides,
            resolve_alias,
            get_command_display,
            reset_config,
        )

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                # Mode 1: Verb simplification
                "memory.remember_insight": {"alias": "save_memory"},
                # Mode 2: Namespace rename
                "code_tools.replace_in_file": {"alias": "code.edit"},
                # Mode 3: Documentation-only
                "git.status": {"append_doc": "\n\nStructured status."},
            }
            mock_settings.return_value = mock_instance

            config = load_command_overrides()
            assert len(config.commands) == 3

            # Mode 1: Alias resolves
            assert resolve_alias("save_memory") == "memory.remember_insight"

            # Mode 2: Alias resolves
            assert resolve_alias("code.edit") == "code_tools.replace_in_file"

            # Mode 3: No alias, returns None
            assert resolve_alias("git.status") is None

            # Display names
            name1, _ = get_command_display("memory.remember_insight")
            assert name1 == "save_memory"

            name2, _ = get_command_display("code_tools.replace_in_file")
            assert name2 == "code.edit"

            name3, _ = get_command_display("git.status")
            assert name3 == "git.status"

    def test_alias_collision_detection(self):
        """Test that duplicate aliases are handled (last one wins)."""
        from omni.core.config.loader import load_command_overrides, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "command1": {"alias": "duplicate_alias"},
                "command2": {"alias": "duplicate_alias"},  # Duplicate!
            }
            mock_settings.return_value = mock_instance

            config = load_command_overrides()

            # Last one wins in dict iteration
            aliases = config.aliases
            assert aliases.get("duplicate_alias") == "command2"

    def test_empty_override_values(self):
        """Test that empty string alias/append_doc are handled."""
        from omni.core.config.loader import (
            load_command_overrides,
            resolve_alias,
            get_command_display,
            reset_config,
        )

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {
                "memory.remember_insight": {
                    "alias": "",  # Empty string
                    "append_doc": "",  # Empty string
                }
            }
            mock_settings.return_value = mock_instance

            # Empty alias should be treated as no alias
            canonical = resolve_alias("")
            assert canonical is None

            # Empty append_doc should not affect description
            name, desc = get_command_display("memory.remember_insight")
            assert name == "memory.remember_insight"
            assert desc == "Execute memory.remember_insight"


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
        assert config.patterns == []

    def test_custom_values(self):
        """Test custom values."""
        from omni.core.config.loader import FilterCommandsConfig

        config = FilterCommandsConfig(patterns=["terminal.*", "!terminal.run_task"])
        assert len(config.patterns) == 2
        assert "terminal.*" in config.patterns


class TestSkillsConfig:
    """Test SkillsConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        from omni.core.config.loader import SkillsConfig

        config = SkillsConfig()
        assert config.preload == []
        assert config.cli_extend == []

    def test_custom_values(self):
        """Test custom values."""
        from omni.core.config.loader import SkillsConfig

        config = SkillsConfig(
            preload=["git", "memory"],
            cli_extend=["terminal", "filesystem"],
        )
        assert len(config.preload) == 2
        assert len(config.cli_extend) == 2


class TestGetActivePreloadSkills:
    """Test get_active_preload_skills function."""

    def test_default_mode(self):
        """Test default mode returns base preload only."""
        from omni.core.config.loader import get_active_preload_skills, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = [
                ["git", "memory"],  # preload
                {"extend": ["terminal"]},  # cli config
            ]
            mock_settings.return_value = mock_instance

            skills = get_active_preload_skills(mode="default")
            assert "git" in skills
            assert "memory" in skills
            assert "terminal" not in skills

    def test_cli_mode(self):
        """Test CLI mode includes extensions."""
        from omni.core.config.loader import get_active_preload_skills, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = [
                ["git", "memory"],  # preload
                {"extend": ["terminal", "filesystem"]},  # cli config
            ]
            mock_settings.return_value = mock_instance

            skills = get_active_preload_skills(mode="cli")
            assert "git" in skills
            assert "memory" in skills
            assert "terminal" in skills
            assert "filesystem" in skills

    def test_deduplication(self):
        """Test that skills are deduplicated."""
        from omni.core.config.loader import get_active_preload_skills, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = [
                ["git", "git"],  # preload with duplicate
                {"extend": ["terminal", "terminal"]},  # cli with duplicate
            ]
            mock_settings.return_value = mock_instance

            skills = get_active_preload_skills(mode="cli")
            # Should have unique skills only
            assert len(skills) == len(set(skills))


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
            assert config.patterns == []

    def test_loads_list_format(self):
        """Test loading filter commands as a list."""
        from omni.core.config.loader import load_filter_commands, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = ["terminal.*", "filesystem.*"]
            mock_settings.return_value = mock_instance

            config = load_filter_commands()
            assert len(config.patterns) == 2
            assert "terminal.*" in config.patterns

    def test_loads_dict_format(self):
        """Test loading filter commands as a dict with patterns."""
        from omni.core.config.loader import load_filter_commands, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = {"patterns": ["terminal.*", "!terminal.run_task"]}
            mock_settings.return_value = mock_instance

            config = load_filter_commands()
            assert len(config.patterns) == 2
            assert "terminal.*" in config.patterns
            assert "!terminal.run_task" in config.patterns


class TestIsFiltered:
    """Test is_filtered function with glob patterns."""

    def test_filters_glob_pattern(self):
        """Test that glob pattern filters matching commands."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = ["terminal.*"]
            mock_settings.return_value = mock_instance

            assert is_filtered("terminal.run_command") is True
            assert is_filtered("terminal.run_task") is True
            assert is_filtered("git.status") is False

    def test_whitelist_exception(self):
        """Test that whitelist exception allows filtered command."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = ["terminal.*", "!terminal.run_task"]
            mock_settings.return_value = mock_instance

            # terminal.* blocks all terminal commands
            assert is_filtered("terminal.run_command") is True
            # But terminal.run_task is whitelisted
            assert is_filtered("terminal.run_task") is False

    def test_empty_filter_list(self):
        """Test with empty filter list."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = []
            mock_settings.return_value = mock_instance

            assert is_filtered("terminal.run_command") is False

    def test_git_raw_filter(self):
        """Test git raw commands are filtered."""
        from omni.core.config.loader import is_filtered, reset_config

        reset_config()

        with patch("omni.foundation.config.settings.get_settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = ["git.raw_*"]
            mock_settings.return_value = mock_instance

            assert is_filtered("git.raw_commit") is True
            assert is_filtered("git.status") is False


class TestResetConfig:
    """Test reset_config function."""

    def test_resets_singletons(self):
        """Test that reset_config clears cached configs."""
        from omni.core.config.loader import (
            load_filter_commands,
            load_skill_limits,
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
