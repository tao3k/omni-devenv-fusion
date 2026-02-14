"""
Dual-Core Knowledge Fusion Engine.

Bridges Core 1 (ZK graph) and Core 2 (LanceDB vector) into unified search.

Sub-modules by bridge:
- zk_proximity: Bridge 1 — ZK link proximity boost for recall
- vector_bridge: Bridge 2 — LanceDB vector search for ZK + factory
- graph_enrichment: Bridge 3 — ZK entity enrichment of router graph
                    Bridge 4 — Shared entity registry (sync hook)
- kg_recall: Bridge 1b — KG entity boost for recall results
- kg_rerank: Bridge 5 — Query-time KG rerank of router results
- fusion_weights: Dynamic weight selection based on Rust intent analysis
"""

from ._config import (
    KG_QUERY_LIMIT,
    KG_QUERY_RERANK_SCALE,
    MAX_ZK_LINK_HOPS,
    ZK_ENTITY_GRAPH_BOOST,
    ZK_LINK_PROXIMITY_BOOST,
    ZK_TAG_PROXIMITY_BOOST,
)
from .fusion_weights import FusionWeights, compute_fusion_weights
from .graph_enrichment import enrich_skill_graph_from_zk, register_skill_entities
from .kg_recall import apply_kg_recall_boost
from .kg_rerank import apply_kg_rerank
from .vector_bridge import build_vector_search_for_zk, get_dual_core_searcher
from .zk_proximity import zk_link_proximity_boost

__all__ = [
    "FusionWeights",
    "KG_QUERY_LIMIT",
    "KG_QUERY_RERANK_SCALE",
    "MAX_ZK_LINK_HOPS",
    "ZK_ENTITY_GRAPH_BOOST",
    "ZK_LINK_PROXIMITY_BOOST",
    "ZK_TAG_PROXIMITY_BOOST",
    "apply_kg_recall_boost",
    "apply_kg_rerank",
    "build_vector_search_for_zk",
    "compute_fusion_weights",
    "enrich_skill_graph_from_zk",
    "get_dual_core_searcher",
    "register_skill_entities",
    "zk_link_proximity_boost",
]
