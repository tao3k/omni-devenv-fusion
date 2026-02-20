"""Unit tests for dependency_search response payload adapters."""

from __future__ import annotations

import builtins
import json
import sys
import types

import dependency_search
import pytest


def _unwrap_skill_output(payload: object) -> dict:
    if isinstance(payload, dict) and "content" in payload:
        content = payload.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return json.loads(first["text"])
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"unexpected payload type: {type(payload)}")


@pytest.mark.asyncio
async def test_dependency_search_import_error_uses_success_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "omni_core_rs":
            raise ImportError("no module named omni_core_rs")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _mock_import)

    out = _unwrap_skill_output(await dependency_search.dependency_search(query="tokio"))
    assert out["success"] is False
    assert out["error"] == "PyDependencyIndexer not available"
    assert "hint" in out


@pytest.mark.asyncio
async def test_dependency_status_import_error_uses_status_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "omni_core_rs":
            raise ImportError("no module named omni_core_rs")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _mock_import)

    out = _unwrap_skill_output(await dependency_search.dependency_status())
    assert out == {
        "status": "error",
        "error": "PyDependencyIndexer not available",
    }


@pytest.mark.asyncio
async def test_dependency_search_runtime_error_includes_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailIndexer:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_index(self) -> None:
            pass

        def search(self, _query: str, _limit: int) -> str:
            raise RuntimeError("boom")

        def get_indexed(self) -> list[str]:
            return []

    class _FakeUnifiedSymbolIndex:
        def add_external_symbol(self, *_args, **_kwargs) -> None:
            return None

        def search_unified_json(self, _query: str, _limit: int) -> str:
            return "[]"

    fake_module = types.SimpleNamespace(
        PyDependencyIndexer=_FailIndexer,
        PyUnifiedSymbolIndex=_FakeUnifiedSymbolIndex,
    )
    monkeypatch.setattr(dependency_search, "_get_project_root", lambda: "/tmp")
    monkeypatch.setattr(dependency_search, "_get_config_path", lambda: None)
    monkeypatch.setitem(sys.modules, "omni_core_rs", fake_module)

    out = _unwrap_skill_output(await dependency_search.dependency_search(query="x"))
    assert out == {
        "success": False,
        "error": "boom",
        "query": "x",
    }
