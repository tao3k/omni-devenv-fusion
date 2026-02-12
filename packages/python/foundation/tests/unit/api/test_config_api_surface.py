"""Public API surface tests for omni.foundation.config."""

from __future__ import annotations


def test_config_module_does_not_export_legacy_wrapper_helpers() -> None:
    import omni.foundation.config as cfg

    assert not hasattr(cfg, "get_conf_directory")
    assert not hasattr(cfg, "set_configuration_directory")
    assert not hasattr(cfg, "get_config_path")
    assert not hasattr(cfg, "list_setting_sections")


def test_config_module_exposes_primary_settings_api() -> None:
    import omni.foundation.config as cfg

    assert hasattr(cfg, "Settings")
    assert hasattr(cfg, "get_settings")
    assert hasattr(cfg, "get_setting")
