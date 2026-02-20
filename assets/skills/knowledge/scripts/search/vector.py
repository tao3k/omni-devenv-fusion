"""Vector (semantic/recall) search over knowledge store."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import get_logger

logger = get_logger("skill.knowledge.search.vector")

if TYPE_CHECKING:
    from omni.foundation.config.paths import ConfigPaths


def _parse_recall_output(out: object) -> dict[str, Any]:
    if isinstance(out, str):
        try:
            payload = json.loads(out)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {"raw": out}
        return {"raw": out}

    if isinstance(out, dict):
        content = out.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                try:
                    payload = json.loads(first["text"])
                    if isinstance(payload, dict):
                        return payload
                except json.JSONDecodeError:
                    return {"raw": out}
        return out

    return {"raw": out}


async def run_vector_search(
    query: str,
    limit: int = 10,
    collection: str = "knowledge_chunks",
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Run vector/semantic search via recall; returns success, query, and recall payload."""
    try:
        from recall import recall
    except ImportError:
        from omni.skills.knowledge.scripts.recall import recall
    out = await recall(query, limit=limit, collection=collection)
    data = _parse_recall_output(out)
    return {"success": True, "query": query, **data}


__all__ = ["run_vector_search"]
