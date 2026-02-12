"""
retrieval_invoker.py - Retrieval-backed ToolInvoker adapters.

Provides ToolInvoker implementations that expose retrieval backends as
pipeline tools (e.g., retriever.search / retriever.hybrid_search).
"""

from __future__ import annotations

from typing import Any

from omni.rag.retrieval import (
    RetrievalConfig,
    RetrievalBackend,
    LanceRetrievalBackend,
    HybridRetrievalBackend,
)

from .node_factory import ToolInvoker


class RetrievalToolInvoker(ToolInvoker):
    """Expose retrieval operations as pipeline-invokable tools."""

    def __init__(
        self,
        vector_backend: RetrievalBackend | None = None,
        hybrid_backend: RetrievalBackend | None = None,
        default_backend: str = "lance",
    ):
        self.vector_backend = vector_backend or LanceRetrievalBackend()
        self.hybrid_backend = hybrid_backend or HybridRetrievalBackend(self.vector_backend)
        normalized_default = default_backend.strip().lower()
        if normalized_default not in {"lance", "hybrid"}:
            raise ValueError(
                "Unsupported retrieval default backend: "
                f"{default_backend}. Supported: lance, hybrid."
            )
        self.default_backend = normalized_default

    def _resolve_backend(self, tool: str, payload: dict[str, Any]) -> RetrievalBackend:
        requested = str(payload.get("backend", "")).strip().lower()
        selected = requested or self.default_backend
        if selected == "hybrid":
            return self.hybrid_backend
        if selected not in {"lance", ""}:
            raise ValueError(f"Unsupported retrieval backend selection: {selected}")
        # Tool-level default behavior
        if tool == "hybrid_search":
            return self.hybrid_backend
        return self.vector_backend

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if server != "retriever":
            return {"status": "not_implemented", "server": server, "tool": tool}

        if tool in {"search", "hybrid_search"}:
            cfg = RetrievalConfig(
                collection=str(payload.get("collection", "knowledge")),
                top_k=int(payload.get("top_k", 10)),
                score_threshold=float(payload.get("score_threshold", 0.0)),
            )
            query = str(payload.get("query", "")).strip()
            backend = self._resolve_backend(tool, payload)
            results = await backend.search(query, cfg)
            return {
                "results": [
                    {
                        "id": r.id,
                        "content": r.content,
                        "score": r.score,
                        "metadata": r.metadata,
                        "source": r.source,
                    }
                    for r in results
                ],
                "count": len(results),
            }

        if tool == "index":
            docs = payload.get("documents", [])
            if not isinstance(docs, list):
                docs = []
            collection = str(payload.get("collection", "knowledge"))
            backend = self._resolve_backend(tool, payload)
            stored = await backend.index(docs, collection)
            return {"stored": stored}

        if tool == "get_stats":
            collection = str(payload.get("collection", "knowledge"))
            backend = self._resolve_backend(tool, payload)
            stats = await backend.get_stats(collection)
            return {"stats": stats}

        return {"status": "not_implemented", "server": server, "tool": tool}


__all__ = [
    "RetrievalToolInvoker",
]
