"""
Dual-Core Knowledge Fusion Engine.

Bridges Core 1 (LinkGraph) and Core 2 (LanceDB vector) into unified search.

Sub-modules by bridge:
- link_graph_proximity: Bridge 1 — LinkGraph proximity boost for recall
- graph_enrichment: Bridge 3 — entity enrichment of router graph
                    Bridge 4 — Shared entity registry (sync hook)
- kg_recall: Bridge 1b — KG entity boost for recall results
- kg_rerank: Bridge 5 — Query-time KG rerank of router results
- fusion_weights: Dynamic weight selection based on Rust intent analysis
"""

from ._config import (
    KG_QUERY_LIMIT,
    KG_QUERY_RERANK_SCALE,
    LINK_GRAPH_ENTITY_BOOST,
    LINK_GRAPH_LINK_PROXIMITY_BOOST,
    LINK_GRAPH_TAG_PROXIMITY_BOOST,
    MAX_LINK_GRAPH_HOPS,
)
from .fusion_weights import FusionWeights, compute_fusion_weights
from .graph_enrichment import enrich_skill_graph_from_link_graph, register_skill_entities
from .kg_recall import apply_kg_recall_boost
from .kg_rerank import apply_kg_rerank
from .link_graph_proximity import link_graph_proximity_boost

__all__ = [
    "KG_QUERY_LIMIT",
    "KG_QUERY_RERANK_SCALE",
    "LINK_GRAPH_ENTITY_BOOST",
    "LINK_GRAPH_LINK_PROXIMITY_BOOST",
    "LINK_GRAPH_TAG_PROXIMITY_BOOST",
    "MAX_LINK_GRAPH_HOPS",
    "FusionWeights",
    "apply_kg_recall_boost",
    "apply_kg_rerank",
    "compute_fusion_weights",
    "enrich_skill_graph_from_link_graph",
    "link_graph_proximity_boost",
    "register_skill_entities",
]
