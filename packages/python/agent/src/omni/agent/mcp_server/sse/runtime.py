"""Runtime selection helpers for MCP SSE transport."""

from __future__ import annotations

import importlib.util


def _module_available(module_name: str) -> bool:
    """Return True when an optional runtime module is importable."""
    return importlib.util.find_spec(module_name) is not None


def _missing_fast_runtime_modules() -> tuple[str, ...]:
    """Return missing optional modules for fast uvicorn runtime."""
    missing: list[str] = []
    if not _module_available("uvloop"):
        missing.append("uvloop")
    if not _module_available("httptools"):
        missing.append("httptools")
    return tuple(missing)


def _select_uvicorn_runtime() -> tuple[str, str]:
    """Select fastest available uvicorn loop/http implementations."""
    missing = _missing_fast_runtime_modules()
    loop_impl = "asyncio" if "uvloop" in missing else "uvloop"
    http_impl = "h11" if "httptools" in missing else "httptools"
    return loop_impl, http_impl
