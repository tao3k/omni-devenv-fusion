"""Bridge 1: ZK Link Proximity → Knowledge Recall.

Boosts LanceDB recall results when source docs share ZK bidirectional links.
Supports dynamic fusion weights from the intent extractor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._config import (
    MAX_ZK_LINK_HOPS,
    ZK_LINK_PROXIMITY_BOOST,
    ZK_TAG_PROXIMITY_BOOST,
    logger,
)


async def zk_link_proximity_boost(
    results: list[dict[str, Any]],
    query: str,
    *,
    zk_root: str | Path | None = None,
    link_boost: float = ZK_LINK_PROXIMITY_BOOST,
    tag_boost: float = ZK_TAG_PROXIMITY_BOOST,
    max_hops: int = MAX_ZK_LINK_HOPS,
    fusion_scale: float | None = None,
) -> list[dict[str, Any]]:
    """Boost recall results when source docs share ZK bidirectional links.

    Scans each result's source path, checks ZK for link relationships
    between sources, and boosts scores accordingly.

    Args:
        results: Recall results (list of dicts with 'score', 'source' keys).
        query: The user's query (used for ZK search context).
        zk_root: Root directory for .zk/ (defaults to cwd).
        link_boost: Base score boost when two results share a ZK link.
        tag_boost: Base score boost when two results share a ZK tag.
        max_hops: Maximum link hops for proximity.
        fusion_scale: Dynamic multiplier from ``compute_fusion_weights``.
            When provided, effective boosts = base * fusion_scale.

    Returns:
        Results with boosted scores, re-sorted.
    """
    if not results or len(results) < 2:
        return results

    # Apply dynamic fusion weight
    effective_link_boost = link_boost
    effective_tag_boost = tag_boost
    if fusion_scale is not None:
        effective_link_boost = link_boost * fusion_scale
        effective_tag_boost = tag_boost * fusion_scale

    try:
        from omni.rag.zk_integration import ZkClient
    except ImportError:
        return results

    try:
        root = Path(zk_root) if zk_root else Path.cwd()
        zk = ZkClient(notebook_dir=str(root))
    except Exception:
        return results

    # Build stem → set of linked stems via list_notes
    stems = [Path(r.get("source", "")).stem for r in results if r.get("source")]

    stem_links: dict[str, set[str]] = {}
    stem_tags: dict[str, set[str]] = {}

    for stem in stems:
        if not stem:
            continue
        stem_links[stem] = set()
        stem_tags[stem] = set()

        try:
            linked_notes = await zk.list_notes(linked_by=[stem])
            for note in linked_notes or []:
                stem_links[stem].add(getattr(note, "filename_stem", ""))

            back_notes = await zk.list_notes(link_to=[stem])
            for note in back_notes or []:
                stem_links[stem].add(getattr(note, "filename_stem", ""))

            # Collect tags from the note itself
            note_results = await zk.list_notes(match=[stem])
            for note in note_results or []:
                stem_tags[stem].update(getattr(note, "tags", []) or [])
        except Exception:
            continue

    # Apply proximity boosts between pairs of results
    boosted = 0
    for i, r1 in enumerate(results):
        stem1 = Path(r1.get("source", "")).stem
        if not stem1 or stem1 not in stem_links:
            continue

        for j, r2 in enumerate(results):
            if i >= j:
                continue
            stem2 = Path(r2.get("source", "")).stem
            if not stem2 or stem2 not in stem_links:
                continue

            reasons: list[str] = []

            # Check bidirectional link
            if stem2 in stem_links.get(stem1, set()) or stem1 in stem_links.get(stem2, set()):
                r1["score"] = float(r1.get("score", 0)) + effective_link_boost
                r2["score"] = float(r2.get("score", 0)) + effective_link_boost
                reasons.append("zk_link")

            # Check shared tags
            shared_tags = stem_tags.get(stem1, set()) & stem_tags.get(stem2, set())
            if shared_tags:
                r1["score"] = float(r1.get("score", 0)) + effective_tag_boost
                r2["score"] = float(r2.get("score", 0)) + effective_tag_boost
                reasons.append(f"shared_tags({len(shared_tags)})")

            if reasons:
                boosted += 1
                logger.debug(
                    "ZK proximity boost: %s <-> %s (%s, scale=%.2f)",
                    r1.get("source", "?"),
                    r2.get("source", "?"),
                    ", ".join(reasons),
                    fusion_scale or 1.0,
                )

    # Re-sort by score
    results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return results
