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
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    def _fake_get_setting(key: str, default=None):
        if key == "api.anthropic_settings":
            return "conf/vendor/anthropic.json"
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    paths = get_config_paths()
    expected = paths.project_root / "conf/vendor/anthropic.json"
    assert paths.get_anthropic_settings_path() == expected


def test_anthropic_settings_path_keeps_absolute_path(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    absolute_path = Path("/tmp/anthropic/settings.json")

    def _fake_get_setting(key: str, default=None):
        if key == "api.anthropic_settings":
            return str(absolute_path)
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    assert get_config_paths().get_anthropic_settings_path() == absolute_path


def test_mcp_config_path_defaults_when_setting_missing(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    def _fake_get_setting(key: str, default=None):
        if key == "mcp.config_file":
            return None
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)

    paths = get_config_paths()
    assert paths.get_mcp_config_path() == paths.project_root / ".mcp.json"


def test_api_base_url_prefers_settings_then_env(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example")

    def _fake_get_setting(key: str, default=None):
        if key == "inference.base_url":
            return "https://settings.example"
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_api_base_url() == "https://settings.example"


def test_api_base_url_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example")

    def _fake_get_setting(key: str, default=None):
        if key == "inference.base_url":
            return None
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_api_base_url() == "https://env.example"


def test_get_mcp_idle_timeout_from_settings(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    def _fake_get_setting(key: str, default=None):
        if key == "mcp.idle_timeout":
            return 120
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_mcp_idle_timeout(None) == 120


def test_get_mcp_idle_timeout_zero_when_unset(monkeypatch: pytest.MonkeyPatch):
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    def _fake_get_setting(key: str, default=None):
        if key == "mcp.idle_timeout":
            return 0
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    assert get_config_paths().get_mcp_idle_timeout(None) == 0


def test_get_mcp_idle_timeout_clamped_when_exceeds_timeout(monkeypatch: pytest.MonkeyPatch):
    """When idle_timeout > timeout, config loader clamps to timeout (spec invariant)."""
    import omni.foundation.config.settings as settings_module
    from omni.foundation.config.paths import get_config_paths
    from omni.foundation.config.settings import get_setting as original_get_setting

    def _fake_get_setting(key: str, default=None):
        if key == "mcp.idle_timeout":
            return 300
        if key == "mcp.timeout":
            return 180
        return original_get_setting(key, default)

    monkeypatch.setattr(settings_module, "get_setting", _fake_get_setting)
    with pytest.warns(UserWarning, match="clamping"):
        result = get_config_paths().get_mcp_idle_timeout(None)
    assert result == 180


def test_wendao_settings_file_uses_prj_config_home(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from omni.foundation.config.dirs import PRJ_DIRS
    from omni.foundation.config.paths import get_config_paths

    config_home = tmp_path / ".config"
    monkeypatch.setenv("PRJ_CONFIG_HOME", str(config_home))
    PRJ_DIRS.clear_cache()

    paths = get_config_paths()
    assert paths.settings_file == config_home / "omni-dev-fusion" / "settings.yaml"
    assert paths.wendao_settings_file == config_home / "omni-dev-fusion" / "wendao.yaml"
    PRJ_DIRS.clear_cache()


def test_list_config_files_includes_wendao_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from omni.foundation.config.dirs import PRJ_DIRS
    from omni.foundation.config.paths import get_config_paths

    config_home = tmp_path / ".config"
    app_config = config_home / "omni-dev-fusion"
    app_config.mkdir(parents=True)
    (app_config / "settings.yaml").write_text("core:\n  mode: test\n", encoding="utf-8")
    (app_config / "wendao.yaml").write_text("link_graph:\n  backend: wendao\n", encoding="utf-8")

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(config_home))
    PRJ_DIRS.clear_cache()

    files = get_config_paths().list_config_files()
    by_name = {item["name"]: item for item in files}

    assert "settings.yaml" in by_name
    assert "wendao.yaml" in by_name
    assert by_name["settings.yaml"]["exists"] is True
    assert by_name["wendao.yaml"]["exists"] is True
    PRJ_DIRS.clear_cache()
