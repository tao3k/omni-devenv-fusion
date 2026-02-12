from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_paths_singleton():
    from omni.foundation.config import paths as paths_module

    paths_module.ConfigPaths._instance = None
    paths_module._paths_instance = None
    yield
    paths_module.ConfigPaths._instance = None
    paths_module._paths_instance = None


def test_anthropic_settings_path_resolves_relative_to_project_root(monkeypatch: pytest.MonkeyPatch):
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting
    import omni.foundation.config.settings as settings_module

    def _fake_get_setting(key: str, default=None):
        if key == "api.anthropic_settings":
            return "conf/vendor/anthropic.json"
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    paths = get_config_paths()
    expected = paths.project_root / "conf/vendor/anthropic.json"
    assert paths.get_anthropic_settings_path() == expected


def test_anthropic_settings_path_keeps_absolute_path(monkeypatch: pytest.MonkeyPatch):
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting
    import omni.foundation.config.settings as settings_module

    absolute_path = Path("/tmp/anthropic/settings.json")

    def _fake_get_setting(key: str, default=None):
        if key == "api.anthropic_settings":
            return str(absolute_path)
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    assert get_config_paths().get_anthropic_settings_path() == absolute_path


def test_mcp_config_path_defaults_when_setting_missing(monkeypatch: pytest.MonkeyPatch):
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting
    import omni.foundation.config.settings as settings_module

    def _fake_get_setting(key: str, default=None):
        if key == "mcp.config_file":
            return None
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    paths = get_config_paths()
    assert paths.get_mcp_config_path() == paths.project_root / ".mcp.json"


def test_api_base_url_prefers_settings_then_env(monkeypatch: pytest.MonkeyPatch):
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting
    import omni.foundation.config.settings as settings_module

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example")

    def _fake_get_setting(key: str, default=None):
        if key == "inference.base_url":
            return "https://settings.example"
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_api_base_url() == "https://settings.example"


def test_api_base_url_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting
    import omni.foundation.config.settings as settings_module

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example")

    def _fake_get_setting(key: str, default=None):
        if key == "inference.base_url":
            return None
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_api_base_url() == "https://env.example"
