"""Bridge 1b: KG Entity Boost → Knowledge Recall.

Enriches LanceDB recall results using KnowledgeGraph entity search.
When a query mentions entities that exist in the graph, recall results
whose source docs are connected to those entities get a score boost.

This complements the ZK link proximity boost (Bridge 1) by adding
graph-level semantic connections on top of structural link connections.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._config import _load_kg, logger


# Base boost per KG entity match in a recall result's source
KG_RECALL_ENTITY_BOOST = 0.06


def apply_kg_recall_boost(
    results: list[dict[str, Any]],
    query: str,
    *,
    lance_dir: str | Path | None = None,
    boost: float = KG_RECALL_ENTITY_BOOST,
    fusion_scale: float | None = None,
) -> list[dict[str, Any]]:
    """Boost recall results connected to query entities in KnowledgeGraph.

    Algorithm:
    1. Extract keywords from query via Rust intent extractor.
    2. For each keyword, search KnowledgeGraph for matching entities.
    3. Walk entity relations to find DOCUMENT / source connections.
    4. Boost recall results whose source paths match connected entities.

    Args:
        results: Recall results (list of dicts with 'score', 'source').
        query: The user's query.
        lance_dir: Path to knowledge.lance directory.
        boost: Base score boost per entity connection.
        fusion_scale: Dynamic multiplier from fusion weights.

    Returns:
        Results with boosted scores, re-sorted.
    """
    if not results or not query or not query.strip():
        return results

    effective_boost = boost
    if fusion_scale is not None:
        effective_boost = boost * fusion_scale

    try:
        from omni_core_rs import extract_query_intent

        kg = _load_kg(lance_dir=lance_dir)
        if kg is None:
            return results

        # Extract keywords from query
        intent = extract_query_intent(query)
        keywords = intent.keywords
        if not keywords:
            return results

        # Search KG for entities matching keywords, collect their names
        entity_names: set[str] = set()
        for kw in keywords[:8]:  # limit to prevent excessive search
            matched = kg.search_entities(kw, 5)
            for entity in matched:
                entity_names.add(entity.name.lower())
                # Also add aliases
                for alias in entity.aliases:
                    entity_names.add(alias.lower())

        if not entity_names:
            return results

        # Match entity names against result source paths and content
        boosted = 0
        for r in results:
            source = r.get("source", "").lower()
            content = r.get("content", "").lower()
            title = r.get("title", "").lower()

            # Check if any entity name appears in source, content, or title
            matches = 0
            for ename in entity_names:
                if ename in source or ename in title:
                    matches += 2  # Strong: entity in source/title
                elif len(ename) >= 3 and ename in content:
                    matches += 1  # Weak: entity in content body

            if matches > 0:
                # Scale boost by match count (diminishing returns)
                score_add = effective_boost * min(matches, 4)
                r["score"] = float(r.get("score", 0)) + score_add
                boosted += 1

        if boosted > 0:
            results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
            logger.debug(
                "KG recall entity boost: %d/%d results boosted (entities=%d, keywords=%s)",
                boosted,
                len(results),
                len(entity_names),
                keywords[:5],
            )

    except ImportError:
        pass
    except Exception as e:
        logger.debug("KG recall entity boost skipped: %s", e)

    return results
