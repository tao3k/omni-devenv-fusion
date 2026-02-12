"""Architecture guardrails for modular tracer invoker package."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


TRACER_DIR = Path(__file__).resolve().parents[3] / "src" / "omni" / "tracer"
pytestmark = pytest.mark.architecture


def _parse(module_name: str) -> ast.Module:
    path = TRACER_DIR / module_name
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.Module) -> list[str]:
    modules: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
    return modules


def test_node_factory_does_not_depend_on_concrete_invokers() -> None:
    """node_factory defines protocols/core node behavior only."""
    imported = _imported_modules(_parse("node_factory.py"))
    forbidden = {"mcp_invoker", "retrieval_invoker", "composite_invoker", "invoker_stack"}
    for module in imported:
        assert not any(name in module for name in forbidden), (
            "node_factory.py must not import concrete invoker modules"
        )


def test_mcp_invoker_depends_only_on_node_factory_contract() -> None:
    """mcp_invoker should use ToolInvoker protocol and stay isolated."""
    imported = _imported_modules(_parse("mcp_invoker.py"))
    assert any("node_factory" in module for module in imported)
    forbidden = {"retrieval_invoker", "composite_invoker", "invoker_stack", "pipeline"}
    for module in imported:
        assert not any(name in module for name in forbidden), (
            "mcp_invoker.py must not import other invoker stack or pipeline modules"
        )


def test_retrieval_invoker_depends_only_on_contract_and_retrieval_backend() -> None:
    """retrieval_invoker should not couple to mcp/composite/stack/pipeline."""
    imported = _imported_modules(_parse("retrieval_invoker.py"))
    assert any("node_factory" in module for module in imported)
    assert any("omni.rag.retrieval" in module for module in imported)
    forbidden = {"mcp_invoker", "composite_invoker", "invoker_stack", "pipeline"}
    for module in imported:
        assert not any(name in module for name in forbidden), (
            "retrieval_invoker.py must not import mcp/composite/stack/pipeline modules"
        )


def test_composite_invoker_depends_only_on_tool_contract_layer() -> None:
    """composite_invoker should compose ToolInvoker, not know concrete invokers."""
    imported = _imported_modules(_parse("composite_invoker.py"))
    assert any("node_factory" in module for module in imported)
    forbidden = {"mcp_invoker", "retrieval_invoker", "invoker_stack", "pipeline"}
    for module in imported:
        assert not any(name in module for name in forbidden), (
            "composite_invoker.py must not import concrete invokers or pipeline modules"
        )


def test_invoker_stack_is_only_composition_layer() -> None:
    """invoker_stack is allowed to compose concrete invokers and factory contracts."""
    imported = _imported_modules(_parse("invoker_stack.py"))

    required = {"composite_invoker", "mcp_invoker", "retrieval_invoker", "node_factory"}
    for name in required:
        assert any(name in module for module in imported), f"invoker_stack.py must import {name}"

    forbidden = {"pipeline_builder", "pipeline_runtime", "pipeline_schema"}
    for module in imported:
        assert not any(name in module for name in forbidden), (
            "invoker_stack.py must not import pipeline modules"
        )
