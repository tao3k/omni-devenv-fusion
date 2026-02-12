"""Tests for reference library path resolution via PRJ config directories."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def _reset_reference_singleton() -> None:
    from omni.foundation.services.reference import ReferenceLibrary

    ReferenceLibrary._instance = None


def test_reference_library_reads_from_prj_config_home(tmp_path, monkeypatch):
    """ReferenceLibrary should read `<PRJ_CONFIG_HOME>/omni-dev-fusion/references.yaml`."""
    conf_dir = tmp_path / "conf"
    app_dir = conf_dir / "omni-dev-fusion"
    app_dir.mkdir(parents=True)
    (app_dir / "references.yaml").write_text(
        yaml.safe_dump({"specs": {"dir": "assets/specs"}}), encoding="utf-8"
    )

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(conf_dir))
    from omni.foundation.config.dirs import PRJ_DIRS

    PRJ_DIRS.clear_cache()
    _reset_reference_singleton()

    from omni.foundation.services.reference import ReferenceLibrary

    ref = ReferenceLibrary()
    assert ref.get("specs.dir") == "assets/specs"


def test_reference_set_conf_dir_routes_through_directory_api(tmp_path, monkeypatch):
    """`set_conf_dir()` should update PRJ config root used by ReferenceLibrary."""
    original = os.environ.get("PRJ_CONFIG_HOME")

    conf_dir = tmp_path / "custom_conf"
    app_dir = conf_dir / "omni-dev-fusion"
    app_dir.mkdir(parents=True)
    (app_dir / "references.yaml").write_text(
        yaml.safe_dump({"cli": {"files": ["app.py"]}}), encoding="utf-8"
    )

    from omni.foundation.config.dirs import PRJ_DIRS
    from omni.foundation.services.reference import ReferenceLibrary, get_conf_dir, set_conf_dir

    try:
        set_conf_dir(str(conf_dir))
        PRJ_DIRS.clear_cache()

        assert get_conf_dir() == str(app_dir)
        ref = ReferenceLibrary()
        assert ref.get("cli.files") == ["app.py"]
    finally:
        if original is None:
            os.environ.pop("PRJ_CONFIG_HOME", None)
        else:
            os.environ["PRJ_CONFIG_HOME"] = original
        PRJ_DIRS.clear_cache()
        _reset_reference_singleton()


def test_get_reference_path_missing_returns_empty_string(tmp_path, monkeypatch):
    """Missing key without fallback should return empty string (not '.')."""
    conf_dir = tmp_path / "conf_missing"
    app_dir = conf_dir / "omni-dev-fusion"
    app_dir.mkdir(parents=True)
    (app_dir / "references.yaml").write_text(
        yaml.safe_dump({"specs": {"dir": "assets/specs"}}), encoding="utf-8"
    )

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(conf_dir))
    from omni.foundation.config.dirs import PRJ_DIRS

    PRJ_DIRS.clear_cache()
    _reset_reference_singleton()

    from omni.foundation.services.reference import get_reference_path

    assert get_reference_path("does.not.exist") == ""
