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


def test_config_module_exposes_link_graph_api_only() -> None:
    import omni.foundation.config as cfg

    assert hasattr(cfg, "get_link_graph_default_config_relative_path")
    assert hasattr(cfg, "get_link_graph_notebook_dir")
    assert hasattr(cfg, "get_link_graph_config_path")
    assert hasattr(cfg, "get_link_graph_harvested_dir")
    assert not hasattr(cfg, "LinkGraphCliRuntimeConfig")
    assert not hasattr(cfg, "get_link_graph_cli_runtime_config")
    assert not hasattr(cfg, "get_zk_notebook_dir")
    assert not hasattr(cfg, "get_zk_config_path")
