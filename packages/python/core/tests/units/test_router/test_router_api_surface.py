"""Public API surface tests for omni.core.router exports."""

from __future__ import annotations


def test_router_exports_explicit_command_router_only() -> None:
    import omni.core.router as router

    assert hasattr(router, "ExplicitCommandRouter")
    assert not hasattr(router, "FallbackRouter")
