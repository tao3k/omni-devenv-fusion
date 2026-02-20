"""Integration tests for Wendao config priority (wendao.yaml first)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from omni.rag.link_graph.wendao_backend import WendaoLinkGraphBackend

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _reset_settings_singleton() -> None:
    from omni.foundation.config.settings import Settings

    Settings._instance = None
    Settings._loaded = False


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_wendao_backend_prefers_wendao_yaml_over_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_dir = tmp_path / "packages" / "conf"
    _write_yaml(conf_dir / "settings.yaml", "core:\n  mode: default\n")
    _write_yaml(
        conf_dir / "wendao.yaml",
        (
            "link_graph:\n"
            "  include_dirs_auto: false\n"
            "  cache:\n"
            '    valkey_url: "redis://127.0.0.1:6396/0"\n'
        ),
    )

    user_conf = tmp_path / ".config"
    user_conf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(user_conf))
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6391/0")
    monkeypatch.setattr("omni.foundation.runtime.gitops.get_project_root", lambda: tmp_path)
    _reset_settings_singleton()

    notebook = tmp_path / "notes"
    notebook.mkdir(parents=True, exist_ok=True)
    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert os.environ["VALKEY_URL"] == "redis://127.0.0.1:6396/0"


def test_wendao_backend_falls_back_to_env_when_wendao_yaml_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf_dir = tmp_path / "packages" / "conf"
    _write_yaml(conf_dir / "settings.yaml", "core:\n  mode: default\n")

    user_conf = tmp_path / ".config"
    user_conf.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(user_conf))
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6391/0")
    monkeypatch.setattr("omni.foundation.runtime.gitops.get_project_root", lambda: tmp_path)
    _reset_settings_singleton()

    notebook = tmp_path / "notes"
    notebook.mkdir(parents=True, exist_ok=True)
    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert os.environ["VALKEY_URL"] == "redis://127.0.0.1:6391/0"
