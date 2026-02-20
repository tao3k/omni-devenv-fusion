"""Architecture guardrails for LinkGraph search API contracts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

pytestmark = pytest.mark.architecture

if TYPE_CHECKING:
    from pathlib import Path


def _read(project_root: Path, relative_path: str) -> str:
    return (project_root / relative_path).read_text(encoding="utf-8")


def test_link_graph_python_backend_contract_is_planned_only(project_root: Path) -> None:
    """Python backend protocol must keep planned-search as the only search entrypoint."""
    source = _read(project_root, "packages/python/foundation/src/omni/rag/link_graph/backend.py")
    assert "async def search_planned(" in source
    assert "async def search(" not in source


def test_link_graph_rust_py_binding_contract_is_planned_only(project_root: Path) -> None:
    """Rust PyO3 binding must expose planned-search only (no legacy search methods)."""
    source = _read(project_root, "packages/rust/crates/xiuxian-wendao/src/link_graph_py.rs")
    assert "fn search_planned(" in source
    assert re.search(r"(?m)^\s*fn\s+search\s*\(", source) is None
    assert re.search(r"(?m)^\s*fn\s+search_with_options\s*\(", source) is None
    assert re.search(r"(?m)^\s*fn\s+run_search\s*\(", source) is None


def test_link_graph_rust_index_contract_is_planned_only(project_root: Path) -> None:
    """Rust index public API must not reintroduce legacy search methods."""
    source = _read(project_root, "packages/rust/crates/xiuxian-wendao/src/link_graph/index.rs")
    assert "pub fn search_planned(" in source
    assert re.search(r"(?m)^\s*pub\s+fn\s+search\s*\(", source) is None
    assert re.search(r"(?m)^\s*pub\s+fn\s+search_with_query\s*\(", source) is None
    assert re.search(r"(?m)^\s*pub\s+fn\s+search_with_options\s*\(", source) is None
