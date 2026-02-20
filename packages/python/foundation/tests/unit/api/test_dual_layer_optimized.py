"""
Test Dual-Layer Configuration Loading - Optimized.

Uses clean_settings fixture to test configuration loading in-process.
"""

import os
import sys
from unittest.mock import patch


class TestDualLayerConfig:
    def test_defaults_loaded(self, clean_settings, tmp_path):
        """Test 1: Defaults loaded from packages/conf/settings.yaml."""
        # Create packages/conf with defaults (not assets/)
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)
        (conf_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        # Empty user config
        user_conf = tmp_path / ".config"
        user_conf.mkdir()
        app_conf = user_conf / "omni-dev-fusion"
        app_conf.mkdir()

        # Mock environment and project root
        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            # Re-initialize settings (clean_settings fixture handles cleanup)
            # We need to manually trigger load because clean_settings gives us an already initialized empty one?
            # clean_settings yields a fresh Settings(), but it initialized with default env.
            # We need to re-init AFTER patching env.

            # Reset again inside the patch context
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False

            settings = Settings()

            assert settings.get("core.timeout") == 30
            assert settings.get("core.mode") == "default"

    def test_user_override(self, clean_settings, tmp_path):
        """Test 2: User config overrides defaults."""
        # Create packages/conf with defaults
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)
        (conf_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        # User config with override
        user_conf = tmp_path / ".config"
        user_conf.mkdir()
        app_conf = user_conf / "omni-dev-fusion"
        app_conf.mkdir()
        (app_conf / "settings.yaml").write_text("core:\n  mode: turbo")

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "turbo"
            assert settings.get("core.timeout") == 30

    def test_deep_merge(self, clean_settings, tmp_path):
        """Test 3: Deep merge preserves nested structure."""
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)
        (conf_dir / "settings.yaml").write_text(
            "api:\n  base_url: https://api.example.com\n  timeout: 10"
        )

        user_conf = tmp_path / ".config"
        user_conf.mkdir()
        app_conf = user_conf / "omni-dev-fusion"
        app_conf.mkdir()
        (app_conf / "settings.yaml").write_text("api:\n  timeout: 60")

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("api.timeout") == 60
            assert settings.get("api.base_url") == "https://api.example.com"

    def test_cli_conf_flag(self, clean_settings, tmp_path):
        """Test 4: CLI --conf flag has highest priority."""
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)
        (conf_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        custom_conf = tmp_path / "custom_conf"
        custom_conf.mkdir()
        (custom_conf / "omni-dev-fusion").mkdir(parents=True)
        (custom_conf / "omni-dev-fusion" / "settings.yaml").write_text("core:\n  mode: from-cli")

        test_args = ["app.py", "--conf", str(custom_conf)]

        with (
            patch.object(sys, "argv", test_args),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "from-cli"
            assert settings.get("core.timeout") == 30
            # Note: Settings logic sets PRJ_CONFIG_HOME env var when --conf is used
            assert os.environ.get("PRJ_CONFIG_HOME") == str(custom_conf)

    def test_cli_conf_takes_precedence_over_env(self, clean_settings, tmp_path):
        """Explicit --conf in argv should win over existing PRJ_CONFIG_HOME."""
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)
        (conf_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        env_conf = tmp_path / "env_conf"
        env_conf.mkdir()
        (env_conf / "omni-dev-fusion").mkdir(parents=True)
        (env_conf / "omni-dev-fusion" / "settings.yaml").write_text("core:\n  mode: from-env")

        cli_conf = tmp_path / "cli_conf"
        cli_conf.mkdir()
        (cli_conf / "omni-dev-fusion").mkdir(parents=True)
        (cli_conf / "omni-dev-fusion" / "settings.yaml").write_text("core:\n  mode: from-cli")

        test_args = ["app.py", "--conf", str(cli_conf)]

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(env_conf)}),
            patch.object(sys, "argv", test_args),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "from-cli"

    def test_wendao_config_is_loaded_from_dedicated_yaml(self, clean_settings, tmp_path):
        """LinkGraph config should be loaded from wendao.yaml (system + user overlay)."""
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)

        (conf_dir / "settings.yaml").write_text("core:\n  mode: default\n", encoding="utf-8")
        (conf_dir / "wendao.yaml").write_text(
            ('link_graph:\n  backend: "wendao"\n  cache:\n    ttl_seconds: 300\n'),
            encoding="utf-8",
        )

        user_conf = tmp_path / ".config"
        app_conf = user_conf / "omni-dev-fusion"
        app_conf.mkdir(parents=True)
        (app_conf / "settings.yaml").write_text("core:\n  mode: user\n", encoding="utf-8")
        (app_conf / "wendao.yaml").write_text(
            "link_graph:\n  cache:\n    ttl_seconds: 900\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "user"
            assert settings.get("link_graph.backend") == "wendao"
            assert settings.get("link_graph.cache.ttl_seconds") == 900

    def test_wendao_yaml_has_higher_priority_than_settings_yaml_for_link_graph(
        self,
        clean_settings,
        tmp_path,
    ):
        """For link_graph keys, user wendao.yaml must win over user settings.yaml."""
        packages_dir = tmp_path / "packages"
        conf_dir = packages_dir / "conf"
        conf_dir.mkdir(parents=True)

        (conf_dir / "settings.yaml").write_text(
            "link_graph:\n  cache:\n    ttl_seconds: 100\n",
            encoding="utf-8",
        )
        (conf_dir / "wendao.yaml").write_text(
            "link_graph:\n  cache:\n    ttl_seconds: 300\n",
            encoding="utf-8",
        )

        user_conf = tmp_path / ".config"
        app_conf = user_conf / "omni-dev-fusion"
        app_conf.mkdir(parents=True)
        (app_conf / "settings.yaml").write_text(
            "link_graph:\n  cache:\n    ttl_seconds: 600\n",
            encoding="utf-8",
        )
        (app_conf / "wendao.yaml").write_text(
            "link_graph:\n  cache:\n    ttl_seconds: 900\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("link_graph.cache.ttl_seconds") == 900
