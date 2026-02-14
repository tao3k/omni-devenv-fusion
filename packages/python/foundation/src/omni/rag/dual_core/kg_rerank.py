"""Bridge 5: Query-Time KG Rerank (KnowledgeGraph → Router at search time).

Dynamically reranks router results using multi-hop graph traversal.
Uses the Rust-native intent extractor for precise keyword extraction,
and applies dynamic fusion weights for context-aware boosting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._config import KG_QUERY_LIMIT, KG_QUERY_RERANK_SCALE, _load_kg, logger


def _extract_query_terms(query: str) -> list[str]:
    """Extract meaningful search terms using Rust intent extractor.

    Tries the Rust-native ``extract_query_intent`` first (fast, precise
    stop-word removal + tokenization). Falls back to Python ad-hoc extraction.

    Args:
        query: Raw user query.

    Returns:
        List of significant keywords for KG search.
    """
    try:
        from omni_core_rs import extract_query_intent

        intent = extract_query_intent(query)
        terms = intent.keywords
        if terms:
            return terms
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: simple Python tokenization
    raw_terms = [t.lower() for t in query.split() if len(t) >= 2]
    _stop = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "to",
        "for",
        "in",
        "on",
        "of",
        "help",
        "me",
        "my",
        "please",
        "want",
        "need",
        "with",
        "and",
        "or",
    }
    return [t for t in raw_terms if t not in _stop]


def apply_kg_rerank(
    results: list[dict[str, Any]],
    query: str,
    *,
    lance_dir: str | Path | None = None,
    scale: float = KG_QUERY_RERANK_SCALE,
    fusion_scale: float | None = None,
) -> list[dict[str, Any]]:
    """Rerank router results using KnowledgeGraph at query time.

    Extracts meaningful terms from the query (via Rust intent extractor),
    walks the KnowledgeGraph (Rust-native multi-hop traversal), and boosts
    tools that are connected to query-relevant entities.

    Args:
        results: Router search results (list of dicts with 'id', 'score').
        query: The user's search query.
        lance_dir: Path to knowledge.lance directory.
        scale: Base boost multiplier per KG relevance unit.
        fusion_scale: Optional multiplier from dynamic fusion weights.
            When provided, effective scale = scale * fusion_scale.

    Returns:
        Results with scores adjusted, re-sorted.
    """
    if not results or not query or not query.strip():
        return results

    # Apply dynamic fusion weight if provided
    effective_scale = scale
    if fusion_scale is not None:
        effective_scale = scale * fusion_scale

    try:
        import json as _json

        kg = _load_kg(lance_dir=lance_dir)
        if kg is None:
            return results

        terms = _extract_query_terms(query)
        if not terms:
            return results

        relevance_json = kg.query_tool_relevance(terms, 2, KG_QUERY_LIMIT)
        relevance_pairs: list[list] = _json.loads(relevance_json)

        if not relevance_pairs:
            return results

        kg_scores: dict[str, float] = {}
        for pair in relevance_pairs:
            if len(pair) >= 2:
                kg_scores[str(pair[0])] = float(pair[1])

        if not kg_scores:
            return results

        boosted = 0
        for r in results:
            tool_id = r.get("id", "")
            rel_score = kg_scores.get(tool_id, 0.0)
            if rel_score > 0:
                boost = rel_score * effective_scale
                r["score"] = float(r.get("score", 0)) + boost
                r["final_score"] = float(r.get("final_score", r.get("score", 0))) + boost
                boosted += 1

        if boosted > 0:
            results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
            logger.debug(
                "KG query-time rerank: boosted %d/%d results (terms=%s, scale=%.3f)",
                boosted,
                len(results),
                terms[:5],
                effective_scale,
            )

    except ImportError:
        pass
    except Exception as e:
        logger.debug("KG query-time rerank skipped: %s", e)

    return results
