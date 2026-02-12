"""
composite_invoker.py - Chain multiple ToolInvoker implementations.

Allows ordered fallback such as:
MCP -> Retrieval -> Mapping -> NoOp
"""

from __future__ import annotations

from typing import Any

from .node_factory import NoOpToolInvoker, ToolInvoker


class CompositeToolInvoker(ToolInvoker):
    """Invoke tools through a prioritized list of ToolInvokers."""

    def __init__(
        self,
        invokers: list[ToolInvoker] | tuple[ToolInvoker, ...],
        default_invoker: ToolInvoker | None = None,
    ):
        self._invokers = list(invokers)
        self._default = default_invoker or NoOpToolInvoker()

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any] | Any:
        errors: list[str] = []

        for invoker in self._invokers:
            try:
                result = await invoker.invoke(
                    server=server, tool=tool, payload=payload, state=state
                )
            except Exception as exc:  # pragma: no cover - exercised in tests
                errors.append(f"{type(exc).__name__}: {exc}")
                continue

            if isinstance(result, dict) and result.get("status") == "not_implemented":
                continue
            return result

        fallback = await self._default.invoke(
            server=server, tool=tool, payload=payload, state=state
        )
        if isinstance(fallback, dict) and errors:
            fallback = dict(fallback)
            fallback["errors"] = errors
        return fallback


__all__ = [
    "CompositeToolInvoker",
]
