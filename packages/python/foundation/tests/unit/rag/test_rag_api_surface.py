"""API surface checks for `omni.rag` namespace."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import omni.rag as rag


def test_legacy_link_graph_cli_exports_removed() -> None:
    """Legacy CLI-oriented LinkGraph exports are intentionally removed."""
    legacy = {
        "LinkGraphClient",
        "LinkGraphListConfig",
        "LinkGraphNote",
        "get_link_graph_client",
    }
    assert legacy.isdisjoint(set(rag.__all__))
    for name in legacy:
        assert not hasattr(rag, name)


def test_legacy_link_graph_client_module_removed() -> None:
    """Legacy `omni.rag.link_graph_client` module should not be importable."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("omni.rag.link_graph_client")


def test_importing_legacy_symbol_from_namespace_fails() -> None:
    """`from omni.rag import LinkGraphClient` must fail after API cleanup."""
    with pytest.raises(ImportError):
        exec("from omni.rag import LinkGraphClient", {})


def test_legacy_module_not_discoverable_via_pkgutil() -> None:
    """Legacy module should not appear in package discovery output."""
    module_names = {module.name for module in pkgutil.iter_modules(rag.__path__)}
    assert "link_graph_client" not in module_names
