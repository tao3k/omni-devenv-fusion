"""Tests for LinkGraph configuration helpers."""

from __future__ import annotations

from pathlib import Path

import omni.foundation.services.reference as reference_module
from omni.foundation.config.link_graph import (
    get_link_graph_config_path,
    get_link_graph_harvested_dir,
    get_link_graph_notebook_dir,
)


def test_get_link_graph_notebook_dir_reads_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        reference_module,
        "ref",
        lambda key: Path("assets/knowledge") if key == "link_graph.notebook" else Path(),
    )
    assert get_link_graph_notebook_dir() == Path("assets/knowledge")


def test_get_link_graph_config_path_uses_notebook_and_default_relative_path(monkeypatch) -> None:
    def _ref(key: str):
        if key == "link_graph.notebook":
            return Path("assets/knowledge")
        return Path()

    monkeypatch.setattr(reference_module, "ref", _ref)
    assert get_link_graph_config_path() == Path("assets/knowledge/.wendao/config.toml")


def test_get_link_graph_config_path_uses_runtime_default_relative_path(monkeypatch) -> None:
    def _ref(key: str):
        if key == "link_graph.notebook":
            return Path("assets/knowledge")
        return Path()

    monkeypatch.setattr(reference_module, "ref", _ref)
    monkeypatch.setattr(
        "omni.foundation.config.link_graph.get_link_graph_default_config_relative_path",
        lambda: Path(".link_graph/config.toml"),
    )
    assert get_link_graph_config_path() == Path("assets/knowledge/.link_graph/config.toml")


def test_get_link_graph_harvested_dir_reads_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        reference_module,
        "ref",
        lambda key: Path(".data/harvested") if key == "link_graph.harvested" else Path(),
    )
    assert get_link_graph_harvested_dir() == Path(".data/harvested")


def test_get_link_graph_config_path_supports_absolute_runtime_path(monkeypatch) -> None:
    def _ref(key: str):
        if key == "link_graph.notebook":
            return Path("assets/knowledge")
        return Path()

    monkeypatch.setattr(reference_module, "ref", _ref)
    monkeypatch.setattr(
        "omni.foundation.config.link_graph.get_link_graph_default_config_relative_path",
        lambda: Path("/etc/wendao/link-graph.toml"),
    )
    assert get_link_graph_config_path() == Path("/etc/wendao/link-graph.toml")
