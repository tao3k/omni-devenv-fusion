"""Bridge configuration: boost constants, KnowledgeGraph Lance path resolution.

KnowledgeGraph is stored as Arrow tables (kg_entities, kg_relations) inside
the knowledge.lance directory — the same Lance ecosystem as knowledge chunks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("omni.rag.dual_core")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Score boost for recall results whose source docs are link-graph linked.
LINK_GRAPH_LINK_PROXIMITY_BOOST = 0.12

# Score boost for recall results sharing link-graph metadata tags.
LINK_GRAPH_TAG_PROXIMITY_BOOST = 0.08

# Score boost for router tools connected via graph entity relations.
LINK_GRAPH_ENTITY_BOOST = 0.10

# Maximum link-graph hops to consider for proximity.
MAX_LINK_GRAPH_HOPS = 2

# Timeout (seconds) for link-graph neighbor/tag fetch.
LINK_GRAPH_PROXIMITY_TIMEOUT = 5

# Max stems to fetch link-graph context for (top by result order).
LINK_GRAPH_MAX_STEMS = 8

# TTL (seconds) for in-memory link-graph stem cache; 0 = disabled.
LINK_GRAPH_STEM_CACHE_TTL_SEC = 60

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
) -> Any | None:
    """Load KnowledgeGraph from Lance tables.

    Uses Rust-side cache (load_kg_from_lance_cached) to avoid repeated disk
    reads during recall. Cache is invalidated on save_to_lance.

    Returns:
        Loaded PyKnowledgeGraph, or None if tables don't exist or import fails.
    """
    try:
        from omni_core_rs import load_kg_from_lance_cached
    except ImportError:
        return None

    lance_path = _resolve_lance_dir(lance_dir)
    result = load_kg_from_lance_cached(str(lance_path))
    if result is None:
        return None
    logger.debug("KG loaded from Lance (cached): %s", lance_path)
    return result


def _save_kg(
    kg: Any,
    *,
    lance_dir: str | Path | None = None,
) -> None:
    """Save KnowledgeGraph to Lance tables.

    Rust save_to_lance invalidates the KG cache for this path automatically.
    """
    lance_path = _resolve_lance_dir(lance_dir)
    lance_path.mkdir(parents=True, exist_ok=True)
    kg.save_to_lance(str(lance_path))
    logger.debug("KG saved to Lance: %s", lance_path)
