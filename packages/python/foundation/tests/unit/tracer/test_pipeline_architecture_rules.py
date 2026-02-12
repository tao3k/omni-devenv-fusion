"""Architecture guardrails for modular tracer pipeline package."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


TRACER_DIR = Path(__file__).resolve().parents[3] / "src" / "omni" / "tracer"


def _parse(module_name: str) -> ast.Module:
    path = TRACER_DIR / module_name
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


pytestmark = pytest.mark.architecture


def test_pipeline_facade_is_removed() -> None:
    """No compatibility facade: pipeline.py should not exist."""
    assert not (TRACER_DIR / "pipeline.py").exists()


def test_schema_module_does_not_import_builder_or_runtime() -> None:
    """Schema layer must not depend on higher layers."""
    tree = _parse("pipeline_schema.py")

    forbidden = {"pipeline_builder", "pipeline_runtime"}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        assert not any(part in module for part in forbidden) and module != ".pipeline", (
            "pipeline_schema.py cannot import builder/runtime/facade modules"
        )


def test_builder_module_does_not_import_runtime() -> None:
    """Builder layer must not depend on runtime layer."""
    tree = _parse("pipeline_builder.py")

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        assert "pipeline_runtime" not in module, (
            "pipeline_builder.py cannot import pipeline_runtime.py"
        )


def test_runtime_module_imports_modular_layers_only() -> None:
    """Runtime should use schema/builder modules directly."""
    tree = _parse("pipeline_runtime.py")

    imported = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    assert any("pipeline_builder" in mod for mod in imported)
    assert any("pipeline_schema" in mod for mod in imported)
    assert all(".pipeline" != mod for mod in imported)
