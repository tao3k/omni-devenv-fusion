"""
Test Dual-Layer Configuration Loading - Optimized.

Uses clean_settings fixture to test configuration loading in-process.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestDualLayerConfig:
    def test_defaults_loaded(self, clean_settings, tmp_path):
        """Test 1: Defaults loaded from assets."""
        # Create assets with defaults
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        # Empty user config
        user_conf = tmp_path / ".config"
        user_conf.mkdir()

        # Mock environment and project root
        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path),
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
        # Create assets
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        # User config with override
        user_conf = tmp_path / ".config"
        user_conf.mkdir()
        (user_conf / "settings.yaml").write_text("core:\n  mode: turbo")

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "turbo"
            assert settings.get("core.timeout") == 30

    def test_deep_merge(self, clean_settings, tmp_path):
        """Test 3: Deep merge preserves nested structure."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "settings.yaml").write_text(
            "api:\n  base_url: https://api.example.com\n  timeout: 10"
        )

        user_conf = tmp_path / ".config"
        user_conf.mkdir()
        (user_conf / "settings.yaml").write_text("api:\n  timeout: 60")

        with (
            patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}),
            patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("api.timeout") == 60
            assert settings.get("api.base_url") == "https://api.example.com"

    def test_cli_conf_flag(self, clean_settings, tmp_path):
        """Test 4: CLI --conf flag has highest priority."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "settings.yaml").write_text("core:\n  timeout: 30\n  mode: default")

        custom_conf = tmp_path / "custom_conf"
        custom_conf.mkdir()
        (custom_conf / "settings.yaml").write_text("core:\n  mode: from-cli")

        test_args = ["app.py", "--conf", str(custom_conf)]

        with (
            patch.object(sys, "argv", test_args),
            patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path),
        ):
            from omni.foundation.config.settings import Settings

            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "from-cli"
            assert settings.get("core.timeout") == 30
            # Note: Settings logic sets PRJ_CONFIG_HOME env var when --conf is used
            assert os.environ.get("PRJ_CONFIG_HOME") == str(custom_conf)
