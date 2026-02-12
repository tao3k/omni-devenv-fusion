"""Tests for file fixtures in omni.test_kit."""

from __future__ import annotations

from pathlib import Path

from omni.test_kit.fixtures.files import temp_yaml_file as _temp_yaml_fixture


def test_temp_yaml_file_factory_creates_file(tmp_path: Path) -> None:
    factory = _temp_yaml_fixture.__wrapped__(tmp_path)  # type: ignore[attr-defined]
    target = factory("sample.yaml", "pipeline: []")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "pipeline: []"
