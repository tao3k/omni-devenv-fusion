"""Tests for knowledge ingest_document URL support (download to project data)."""

from pathlib import Path

import pytest


# Import helpers from skill script (scripts dir on path via conftest or parent)
def _import_graph_module():
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    import sys

    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import graph as graph_mod

    return graph_mod


def test_is_url():
    """_is_url identifies http(s) URLs."""
    graph = _import_graph_module()
    assert graph._is_url("https://arxiv.org/pdf/2601.03192") is True
    assert graph._is_url("http://example.com/doc.pdf") is True
    assert graph._is_url("  https://a.b/c  ") is True
    assert graph._is_url("/local/path/doc.pdf") is False
    assert graph._is_url("docs/guide.pdf") is False
    assert graph._is_url("") is False
    assert graph._is_url(None) is False


def test_filename_from_url_arxiv():
    """_filename_from_url derives arxiv ID as filename."""
    graph = _import_graph_module()
    assert graph._filename_from_url("https://arxiv.org/pdf/2601.03192") == "2601.03192.pdf"
    assert graph._filename_from_url("https://arxiv.org/pdf/2510.12323.pdf") == "2510.12323.pdf"


def test_filename_from_url_generic():
    """_filename_from_url uses path basename or document.pdf."""
    graph = _import_graph_module()
    assert graph._filename_from_url("https://example.com/papers/report.pdf") == "report.pdf"
    assert graph._filename_from_url("https://example.com/papers/report") == "report.pdf"
    assert graph._filename_from_url("https://example.com/") == "document.pdf"
