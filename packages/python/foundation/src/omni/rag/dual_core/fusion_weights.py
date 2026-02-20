"""Dynamic fusion weight selection based on Rust-native query intent.

Determines how much emphasis to place on LinkGraph (graph/proximity) vs
LanceDB (vector/keyword) signals depending on query characteristics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("omni.rag.dual_core.fusion")


@dataclass(frozen=True)
class FusionWeights:
    """Per-query weights controlling LinkGraph vs LanceDB emphasis.

    Attributes:
        link_graph_proximity_scale: Multiplier for LinkGraph proximity boost (Bridge 1).
        link_graph_entity_scale: Multiplier for graph entity enrichment (Bridge 3).
        kg_rerank_scale: Multiplier for KG query-time rerank (Bridge 5).
        vector_weight: Emphasis on LanceDB vector similarity.
        keyword_weight: Emphasis on LanceDB BM25 keyword match.
        intent_action: Canonical action from intent extractor (informational).
        intent_target: Canonical target from intent extractor (informational).
    """

    link_graph_proximity_scale: float = 1.0
    link_graph_entity_scale: float = 1.0
    kg_rerank_scale: float = 1.0
    vector_weight: float = 1.0
    keyword_weight: float = 1.0
    intent_action: str | None = None
    intent_target: str | None = None
    intent_keywords: list[str] = field(default_factory=list)


# Default balanced weights
_BALANCED = FusionWeights()

# Target → LinkGraph emphasis profile
_GRAPH_HEAVY_TARGETS = {"knowledge", "docs"}
# Target → LanceDB emphasis profile
_VECTOR_HEAVY_TARGETS = {"code", "database", "skill", "test"}
# Actions that benefit from graph context
_GRAPH_ACTIONS = {"search", "research"}
# Actions that need precise tool routing (LanceDB)
_TOOL_ACTIONS = {"commit", "push", "pull", "merge", "rebase", "run", "test", "lint", "format"}


def compute_fusion_weights(query: str) -> FusionWeights:
    """Compute dynamic fusion weights from a user query.

    Uses the Rust-native intent extractor (``extract_query_intent``) for
    action/target/context decomposition. Falls back to balanced defaults
    if the Rust module is unavailable or the query is empty.

    Args:
        query: Raw user query string.

    Returns:
        FusionWeights with per-signal scaling.
    """
    if not query or not query.strip():
        return _BALANCED

    try:
        from omni_core_rs import extract_query_intent

        intent = extract_query_intent(query)
    except ImportError:
        logger.debug("omni_core_rs not available; using balanced weights")
        return _BALANCED
    except Exception as e:
        logger.debug("Intent extraction failed: %s", e)
        return _BALANCED

    action = intent.action
    target = intent.target
    keywords = intent.keywords

    # Start from balanced
    graph_prox = 1.0
    graph_ent = 1.0
    kg_rerank = 1.0
    vec_w = 1.0
    kw_w = 1.0

    # --- Target-based adjustments ---
    if target in _GRAPH_HEAVY_TARGETS:
        # Knowledge / docs queries: graph context is more valuable.
        graph_prox = 1.5
        graph_ent = 1.4
        kg_rerank = 1.3
        vec_w = 0.9
    elif target in _VECTOR_HEAVY_TARGETS:
        # Code / tool queries: LanceDB precision matters more
        graph_prox = 0.7
        graph_ent = 0.8
        kg_rerank = 0.9
        vec_w = 1.2
        kw_w = 1.3

    # --- Action-based refinements ---
    # Only apply action adjustments if no specific target was detected,
    # or if the target is in a compatible group. Target provides stronger
    # domain signal than action alone.
    has_specific_target = target is not None
    if action in _GRAPH_ACTIONS and target not in _VECTOR_HEAVY_TARGETS:
        # Search / research benefits from broader graph context
        graph_prox = max(graph_prox, 1.3)
        kg_rerank = max(kg_rerank, 1.2)
    elif action in _TOOL_ACTIONS:
        # Precise tool routing — favor LanceDB exact match
        vec_w = max(vec_w, 1.1)
        kw_w = max(kw_w, 1.4)
        if not has_specific_target or target not in _GRAPH_HEAVY_TARGETS:
            graph_prox = min(graph_prox, 0.8)

    # --- Keyword density heuristic ---
    # Many keywords → broader query → graph context helps disambiguate.
    if len(keywords) >= 4:
        kg_rerank *= 1.1
        graph_ent *= 1.1

    weights = FusionWeights(
        link_graph_proximity_scale=round(graph_prox, 2),
        link_graph_entity_scale=round(graph_ent, 2),
        kg_rerank_scale=round(kg_rerank, 2),
        vector_weight=round(vec_w, 2),
        keyword_weight=round(kw_w, 2),
        intent_action=action,
        intent_target=target,
        intent_keywords=keywords,
    )

    logger.debug(
        "Fusion weights computed: action=%s target=%s → graph_prox=%.2f kg_rerank=%.2f vec=%.2f kw=%.2f",
        action,
        target,
        weights.link_graph_proximity_scale,
        weights.kg_rerank_scale,
        weights.vector_weight,
        weights.keyword_weight,
    )

    return weights
