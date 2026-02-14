"""Bridge configuration: boost constants, KnowledgeGraph Lance path resolution.

KnowledgeGraph is stored as Arrow tables (kg_entities, kg_relations) inside
the knowledge.lance directory — the same Lance ecosystem as knowledge chunks.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("omni.rag.dual_core")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Score boost for recall results whose source docs are ZK-linked
ZK_LINK_PROXIMITY_BOOST = 0.12

# Score boost for recall results in same ZK tag group
ZK_TAG_PROXIMITY_BOOST = 0.08

# Score boost for router tools connected via ZK entity graph
ZK_ENTITY_GRAPH_BOOST = 0.10

# Maximum ZK link hops to consider for proximity
MAX_ZK_LINK_HOPS = 2

# Score boost per unit of KG relevance (tool relevance from multi-hop graph walk)
KG_QUERY_RERANK_SCALE = 0.08

# Max results to consider from KG relevance query
KG_QUERY_LIMIT = 15


# ---------------------------------------------------------------------------
# Lance path resolver
# ---------------------------------------------------------------------------


def _resolve_lance_dir(lance_dir: str | Path | None = None) -> Path:
    """Resolve the Lance directory for KnowledgeGraph tables.

    Points to knowledge.lance which contains ``kg_entities`` and ``kg_relations``
    Arrow tables alongside knowledge chunks.
    """
    if lance_dir is not None:
        return Path(lance_dir)
    from omni.foundation.config.database import get_knowledge_graph_lance_dir

    return get_knowledge_graph_lance_dir()


# ---------------------------------------------------------------------------
# KG load / save (Lance only)
# ---------------------------------------------------------------------------


def _load_kg(
    *,
    lance_dir: str | Path | None = None,
) -> "PyKnowledgeGraph | None":
    """Load KnowledgeGraph from Lance tables.

    Returns:
        Loaded PyKnowledgeGraph, or None if tables don't exist yet.
    """
    try:
        from omni_core_rs import PyKnowledgeGraph
    except ImportError:
        return None

    lance_path = _resolve_lance_dir(lance_dir)
    entity_table = lance_path / "kg_entities"
    if not entity_table.exists():
        return None

    kg = PyKnowledgeGraph()
    kg.load_from_lance(str(lance_path))
    logger.debug("KG loaded from Lance: %s", lance_path)
    return kg


def _save_kg(
    kg: "PyKnowledgeGraph",
    *,
    lance_dir: str | Path | None = None,
) -> None:
    """Save KnowledgeGraph to Lance tables."""
    lance_path = _resolve_lance_dir(lance_dir)
    lance_path.mkdir(parents=True, exist_ok=True)
    kg.save_to_lance(str(lance_path))
    logger.debug("KG saved to Lance: %s", lance_path)
