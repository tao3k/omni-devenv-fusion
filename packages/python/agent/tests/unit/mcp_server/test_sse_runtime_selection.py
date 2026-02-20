"""Tests for SSE uvicorn runtime selection."""

from __future__ import annotations

from omni.agent.mcp_server.sse import _missing_fast_runtime_modules, _select_uvicorn_runtime


def test_select_uvicorn_runtime_prefers_fast_modules(monkeypatch) -> None:
    """When uvloop/httptools are available, select them."""

    def _find_spec(name: str):
        if name in {"uvloop", "httptools"}:
            return object()
        return None

    monkeypatch.setattr("importlib.util.find_spec", _find_spec)
    assert _select_uvicorn_runtime() == ("uvloop", "httptools")


def test_select_uvicorn_runtime_falls_back_to_asyncio_h11(monkeypatch) -> None:
    """When optional modules are unavailable, use asyncio+h11."""

    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    assert _select_uvicorn_runtime() == ("asyncio", "h11")


def test_missing_fast_runtime_modules_detects_both(monkeypatch) -> None:
    """Return both modules when neither optional runtime dependency is present."""

    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    assert _missing_fast_runtime_modules() == ("uvloop", "httptools")


def test_missing_fast_runtime_modules_empty_when_all_present(monkeypatch) -> None:
    """Return empty tuple when both optional runtime dependencies are available."""

    monkeypatch.setattr("importlib.util.find_spec", lambda _name: object())
    assert _missing_fast_runtime_modules() == ()
