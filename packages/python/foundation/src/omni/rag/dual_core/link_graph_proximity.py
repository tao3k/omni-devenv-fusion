"""Bridge adapter: dual_core entrypoint routed to common LinkGraph engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omni.rag.link_graph import apply_link_graph_proximity_boost

from ._config import (
    LINK_GRAPH_LINK_PROXIMITY_BOOST,
    LINK_GRAPH_TAG_PROXIMITY_BOOST,
    MAX_LINK_GRAPH_HOPS,
)

if TYPE_CHECKING:
    from pathlib import Path


async def link_graph_proximity_boost(
    results: list[dict[str, Any]],
    query: str,
    *,
    graph_root: str | Path | None = None,
    link_boost: float = LINK_GRAPH_LINK_PROXIMITY_BOOST,
    tag_boost: float = LINK_GRAPH_TAG_PROXIMITY_BOOST,
    max_hops: int = MAX_LINK_GRAPH_HOPS,
    fusion_scale: float | None = None,
) -> list[dict[str, Any]]:
    """Thin wrapper around ``omni.rag.link_graph.proximity``."""
    return await apply_link_graph_proximity_boost(
        results,
        query,
        notebook_dir=graph_root,
        link_boost=link_boost,
        tag_boost=tag_boost,
        max_hops=max_hops,
        fusion_scale=fusion_scale,
    )


__all__ = ["link_graph_proximity_boost"]
