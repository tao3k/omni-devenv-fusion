"""
Skill relationship graph for associative (neural-style) routing.

Builds a relationship graph from skill/tool data so retrieval can use
connections between tools, not just single-query similarity. Supports:
- Keyword-overlap similarity (routing_keywords Jaccard) as relationship strength
- Same-skill edges (tools under the same skill)
- Shared-reference edges (tools that reference the same references/*.md)
- Persist/load graph next to the router index
- Relationship-based rerank in hybrid search (boost tools related to top results)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.skill_relationships")

# Max related tools per node; keep graph sparse for fast lookup
DEFAULT_RELATED_TOP_K = 5
# Min overlap (Jaccard) to consider two tools related
MIN_OVERLAP = 0.1
# Weight for same-skill sibling edge (Skill → tools hierarchy)
SAME_SKILL_WEIGHT = 0.35
# Weight for shared-reference edge (tools → references hierarchy)
SHARED_REF_WEIGHT = 0.25
# Score boost when a result is related to a top-ranked result (rerank)
RELATIONSHIP_RERANK_BOOST = 0.06
# How many top results seed the relationship boost (only boost related to these)
RELATIONSHIP_TOP_N = 3


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets (0..1)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _normalize_refs(refs: Any) -> set[str]:
    """Normalize skill_tools_refers to a set of non-empty strings."""
    if not refs:
        return set()
    if isinstance(refs, list):
        return {str(r).strip() for r in refs if r}
    return set()


def build_relationship_graph(
    docs: list[dict[str, Any]],
    *,
    top_k: int = DEFAULT_RELATED_TOP_K,
    min_overlap: float = MIN_OVERLAP,
) -> dict[str, list[tuple[str, float]]]:
    """Build tool_id -> [(related_id, weight), ...] from indexed docs.

    Uses three relationship dimensions when metadata is present:
    1. Keyword overlap (routing_keywords Jaccard) — similar intents.
    2. Same skill (metadata.skill_name) — tools under the same skill.
    3. Shared references (metadata.skill_tools_refers) — tools that reference
       the same references/*.md (for_tools).

    Args:
        docs: List of {id, metadata}. Metadata may include routing_keywords,
            skill_name, skill_tools_refers (from Rust index).
        top_k: Max related tools per node.
        min_overlap: Minimum Jaccard to add a keyword-overlap edge.

    Returns:
        Graph: tool_id -> [(related_id, weight), ...] sorted by weight descending.
    """
    # Collect command entries: id, keywords, skill_name, refs
    id_to_kw: dict[str, set[str]] = {}
    id_to_skill: dict[str, str] = {}
    id_to_refs: dict[str, set[str]] = {}
    for d in docs:
        meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
        mid = d.get("id") or meta.get("tool_name") or meta.get("id")
        if not mid:
            continue
        kw = meta.get("routing_keywords") or []
        id_to_kw[mid] = {str(k).lower().strip() for k in kw if k} if isinstance(kw, list) else set()
        skill = (meta.get("skill_name") or "").strip()
        if skill:
            id_to_skill[mid] = skill
        id_to_refs[mid] = _normalize_refs(meta.get("skill_tools_refers"))

    if not id_to_kw:
        return {}

    ids = list(id_to_kw.keys())
    # Merge edges from keyword overlap, same-skill, shared-refs; keep max weight per target
    graph_weights: dict[str, dict[str, float]] = {aid: {} for aid in ids}
    for i, aid in enumerate(ids):
        for j, bid in enumerate(ids):
            if i == j:
                continue
            w = 0.0
            # Keyword overlap
            sim = _jaccard(id_to_kw[aid], id_to_kw[bid])
            if sim >= min_overlap:
                w = max(w, round(sim, 4))
            # Same skill (Skill → tools)
            if id_to_skill.get(aid) and id_to_skill.get(aid) == id_to_skill.get(bid):
                w = max(w, SAME_SKILL_WEIGHT)
            # Shared references (tools → references)
            refs_a, refs_b = id_to_refs.get(aid, set()), id_to_refs.get(bid, set())
            if refs_a and refs_b and (refs_a & refs_b):
                w = max(w, SHARED_REF_WEIGHT)
            if w > 0:
                graph_weights[aid][bid] = max(graph_weights[aid].get(bid, 0), w)

    graph: dict[str, list[tuple[str, float]]] = {}
    for aid in ids:
        neighbors = sorted(
            graph_weights[aid].items(),
            key=lambda x: -x[1],
        )[:top_k]
        graph[aid] = [(bid, w) for bid, w in neighbors]

    logger.debug("Relationship graph built: %d nodes", len(graph))
    return graph


def save_relationship_graph(graph: dict[str, list[tuple[str, float]]], path: Path) -> None:
    """Persist graph to JSON. path is the file path (e.g. .../skill_relationships.json)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON serializable: list of [id, weight] for each key
    out = {k: [[rid, w] for rid, w in v] for k, v in graph.items()}
    path.write_text(json.dumps(out, indent=0), encoding="utf-8")
    logger.debug("Relationship graph saved to %s", path)


def load_relationship_graph(path: Path) -> dict[str, list[tuple[str, float]]] | None:
    """Load graph from JSON. Returns None if file missing or invalid."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: [tuple(x) for x in v] for k, v in raw.items()}
    except Exception as e:
        logger.warning("Failed to load relationship graph from %s: %s", path, e)
        return None


def get_relationship_graph_path(storage_path: str | None) -> Path | None:
    """Resolve path to skill_relationships.json next to the router/skills store."""
    if not storage_path or storage_path == ":memory:":
        return None
    p = Path(storage_path)
    if p.suffix == ".lance":
        base = p.parent
    else:
        base = p
    return base / "skill_relationships.json"


def build_graph_from_docs(docs: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    """Build relationship graph from indexer docs (id + metadata with routing_keywords)."""
    # Normalize to {id, metadata} for command entries only
    entries: list[dict[str, Any]] = []
    for d in docs:
        meta = d.get("metadata")
        if isinstance(meta, str):
            continue
        if not isinstance(meta, dict):
            meta = {}
        if meta.get("type") != "command":
            continue
        entries.append(
            {"id": d.get("id") or meta.get("tool_name") or meta.get("id"), "metadata": meta}
        )
    return build_relationship_graph(entries)


def build_graph_from_entries(entries: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    """Build relationship graph from raw table rows (e.g. from store.list_all).

    Each entry is a dict with id and metadata fields (type, skill_name,
    routing_keywords, skill_tools_refers). Use after reindex to get same-skill
    and shared-reference edges from the index.
    """
    if not entries:
        return {}
    docs = [
        {"id": r.get("id"), "metadata": r}
        for r in entries
        if r.get("type") == "command" and r.get("id")
    ]
    return build_graph_from_docs(docs)


def build_graph_from_store(
    store: Any,
    table_name: str = "skills",
) -> dict[str, list[tuple[str, float]]]:
    """Build relationship graph from the vector store (e.g. after Rust reindex).

    Reads all rows via store.list_all(table_name); each row should have
    type, skill_name, routing_keywords, and optionally skill_tools_refers.
    Caller must run list_all in async context; for sync reindex use
    build_graph_from_entries(entries) with the result of list_all.

    After building the base graph from skill metadata, enriches it with
    ZK entity connections (Core 1 → Core 2 bridge).
    """
    try:
        entries = store.list_all(table_name)
    except Exception as e:
        logger.debug("list_all failed for relationship graph: %s", e)
        return {}
    graph = build_graph_from_entries(entries)
    return _enrich_with_zk_graph(graph)


def _enrich_with_zk_graph(
    graph: dict[str, list[tuple[str, float]]],
) -> dict[str, list[tuple[str, float]]]:
    """Enrich skill relationship graph with ZK entity connections.

    This is Bridge 3: ZK Entity Graph → Router. Non-blocking: if ZK graph
    is unavailable, returns the original graph unchanged.
    """
    try:
        from omni.rag.dual_core import enrich_skill_graph_from_zk

        return enrich_skill_graph_from_zk(graph)
    except Exception as e:
        logger.debug("ZK enrichment skipped: %s", e)
        return graph


def apply_relationship_rerank(
    results: list[dict[str, Any]],
    graph: dict[str, list[tuple[str, float]]] | None,
    *,
    top_n: int = RELATIONSHIP_TOP_N,
    boost: float = RELATIONSHIP_RERANK_BOOST,
) -> list[dict[str, Any]]:
    """Boost score of results that are related to top-ranked results (associative rerank).

    If graph says A is related to B, and A is in the top-N results, then B gets
    a small score boost so that relationship-connected tools rank higher.

    Args:
        results: List of result dicts with 'id', 'score', 'final_score'.
        graph: tool_id -> [(related_id, weight), ...] from load_relationship_graph.
        top_n: Only top-N results seed the boost.
        boost: Score increment for each related result (scaled by edge weight).

    Returns:
        Same list, scores updated, re-sorted by score descending.
    """
    if not graph or not results:
        return results
    top_ids = {
        results[i].get("id") for i in range(min(top_n, len(results))) if results[i].get("id")
    }
    related_to_top: dict[str, float] = {}
    for tid in top_ids:
        for rid, weight in graph.get(tid, []):
            related_to_top[rid] = max(related_to_top.get(rid, 0), weight)
    for r in results:
        rid = r.get("id")
        if rid in related_to_top:
            w = related_to_top[rid]
            s = float(r.get("score") or 0)
            f = float(r.get("final_score") or s)
            r["score"] = s + boost * w
            r["final_score"] = f + boost * w
    results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return results
