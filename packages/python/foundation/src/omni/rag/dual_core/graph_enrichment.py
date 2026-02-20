"""Bridge 3: LinkGraph Entity Graph → Router Skill Relationships.

Enriches the router's skill relationship graph with LinkGraph entity connections.
Also includes Bridge 4: Shared Entity Registry (omni sync hook).
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from ._config import LINK_GRAPH_ENTITY_BOOST, _load_kg, _save_kg, logger

if TYPE_CHECKING:
    from pathlib import Path


def enrich_skill_graph_from_link_graph(
    skill_graph: dict[str, list[tuple[str, float]]],
    *,
    lance_dir: str | Path | None = None,
    entity_boost: float = LINK_GRAPH_ENTITY_BOOST,
) -> dict[str, list[tuple[str, float]]]:
    """Enrich the router's skill relationship graph with LinkGraph entity connections.

    Loads the persisted KnowledgeGraph and finds additional connections between
    tools based on shared entities (DOCUMENTED_IN, USES, etc.).

    If tool A and tool B both have entity connections via search_entities,
    they are considered related and an edge is added.

    Args:
        skill_graph: Router's existing {tool_id: [(related_tool, weight)]}.
        lance_dir: Path to knowledge.lance directory.
        entity_boost: Weight for new graph-derived connections.

    Returns:
        The enriched skill_graph (mutated in place and returned).
    """
    kg = _load_kg(lance_dir=lance_dir)
    if kg is None:
        logger.debug("KnowledgeGraph not loaded, skipping enrichment")
        return skill_graph

    try:
        # Build tool_name -> set of entity names
        tool_entities: dict[str, set[str]] = {}
        for tool_name in skill_graph:
            parts = tool_name.replace(".", " ").replace("_", " ").split()
            entities_found: set[str] = set()
            for part in parts:
                results = kg.search_entities(part, 5)
                for entity in results:
                    # entity may be a PyEntity or dict
                    if hasattr(entity, "to_dict"):
                        import json as _json

                        try:
                            info = _json.loads(entity.to_dict())
                            name = info.get("name", "")
                        except Exception:
                            name = str(entity)
                    elif isinstance(entity, dict):
                        name = entity.get("name", "")
                    else:
                        name = str(entity)
                    if name:
                        entities_found.add(name)
            tool_entities[tool_name] = entities_found

        # Find shared-entity connections
        tool_names = list(skill_graph.keys())
        for i, t1 in enumerate(tool_names):
            for j, t2 in enumerate(tool_names):
                if i >= j:
                    continue
                shared = tool_entities.get(t1, set()) & tool_entities.get(t2, set())
                if shared:
                    existing_t1 = dict(skill_graph.get(t1, []))
                    existing_t2 = dict(skill_graph.get(t2, []))

                    if t2 not in existing_t1:
                        skill_graph.setdefault(t1, []).append((t2, entity_boost))
                    if t1 not in existing_t2:
                        skill_graph.setdefault(t2, []).append((t1, entity_boost))

        # Persist graph after enrichment.
        with suppress(Exception):
            _save_kg(kg, lance_dir=lance_dir)

    except Exception as e:
        logger.debug("LinkGraph enrichment failed: %s", e)

    logger.info(
        "LinkGraph entity graph enrichment complete: %d tools in skill_graph",
        len(skill_graph),
    )
    return skill_graph


# ---------------------------------------------------------------------------
# Bridge 4: Shared Entity Registry
# ---------------------------------------------------------------------------


def _normalize_docs_for_rust(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize skill docs into a flat list suitable for Rust JSON ingestion."""
    import json as _json

    normalized: list[dict[str, Any]] = []
    for doc in docs:
        meta = doc.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = _json.loads(meta)
            except Exception:
                continue

        normalized.append(
            {
                "id": doc.get("id", ""),
                "type": meta.get("type", ""),
                "skill_name": meta.get("skill_name", ""),
                "tool_name": meta.get("tool_name", "") or doc.get("id", ""),
                "content": doc.get("content", ""),
                "routing_keywords": meta.get("routing_keywords", []) or [],
            }
        )
    return normalized


def register_skill_entities(
    docs: list[dict[str, Any]],
    *,
    lance_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Register indexed skill docs as entities in the KnowledgeGraph.

    Called during ``omni sync`` / ``omni reindex``. Prefers Rust-native batch path.
    Persists to Lance tables in knowledge.lance.

    Args:
        docs: Indexed skill documents from SkillIndexer.
        lance_dir: Where to persist Lance tables.

    Returns:
        Stats dict with entities_added, relations_added.
    """
    import json as _json

    try:
        from omni_core_rs import PyKnowledgeGraph
    except ImportError:
        logger.debug("omni_core_rs unavailable, skipping entity registration")
        return {"entities_added": 0, "relations_added": 0, "status": "skipped"}

    # Load existing graph or create fresh
    kg = _load_kg(lance_dir=lance_dir)
    if kg is None:
        kg = PyKnowledgeGraph()

    normalized = _normalize_docs_for_rust(docs)

    try:
        result_json = kg.register_skill_entities_json(_json.dumps(normalized))
        result = _json.loads(result_json)
    except (AttributeError, TypeError):
        logger.debug("register_skill_entities_json not available, falling back to Python loop")
        result = _register_skill_entities_python(kg, normalized)

    # Save to Lance
    try:
        _save_kg(kg, lance_dir=lance_dir)
        logger.info(
            "KnowledgeGraph updated: +%d entities, +%d relations",
            result.get("entities_added", 0),
            result.get("relations_added", 0),
        )
    except Exception as e:
        logger.warning("Failed to save KnowledgeGraph: %s", e)

    return result


def _register_skill_entities_python(kg: Any, normalized: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure-Python fallback for register_skill_entities."""
    from omni_core_rs import PyEntity, PyRelation

    entities_added = 0
    relations_added = 0
    skills: dict[str, list[str]] = {}
    tool_keywords: dict[str, set[str]] = {}

    for doc in normalized:
        doc_type = doc.get("type", "")
        skill_name = doc.get("skill_name", "")
        tool_name = doc.get("tool_name", "")

        if doc_type == "skill" and skill_name:
            try:
                content = doc.get("content", f"Skill: {skill_name}")
                kg.add_entity(
                    PyEntity(
                        name=skill_name,
                        entity_type="SKILL",
                        description=str(content)[:200],
                    )
                )
                entities_added += 1
                skills.setdefault(skill_name, [])
            except Exception:
                pass

        elif doc_type == "command" and tool_name:
            try:
                kg.add_entity(
                    PyEntity(
                        name=tool_name,
                        entity_type="TOOL",
                        description=str(doc.get("content", ""))[:200],
                    )
                )
                entities_added += 1
            except Exception:
                pass
            if skill_name:
                skills.setdefault(skill_name, []).append(tool_name)
            kw = doc.get("routing_keywords", [])
            if isinstance(kw, list):
                tool_keywords[tool_name] = {str(k).lower() for k in kw if k}

    for skill_name, tool_ids in skills.items():
        for tool_id in tool_ids:
            try:
                kg.add_relation(
                    PyRelation(
                        source=skill_name,
                        target=tool_id,
                        relation_type="CONTAINS",
                        description=f"{skill_name} contains {tool_id}",
                    )
                )
                relations_added += 1
            except Exception:
                pass

    all_keywords: set[str] = set()
    for kw_set in tool_keywords.values():
        all_keywords |= kw_set

    for kw in all_keywords:
        try:
            kg.add_entity(
                PyEntity(
                    name=f"keyword:{kw}",
                    entity_type="CONCEPT",
                    description=f"Routing keyword: {kw}",
                )
            )
            entities_added += 1
        except Exception:
            pass

    for tool_id, kw_set in tool_keywords.items():
        for kw in kw_set:
            try:
                kg.add_relation(
                    PyRelation(
                        source=tool_id,
                        target=f"keyword:{kw}",
                        relation_type="RELATED_TO",
                        description=f"{tool_id} has keyword {kw}",
                    )
                )
                relations_added += 1
            except Exception:
                pass

    return {
        "entities_added": entities_added,
        "relations_added": relations_added,
        "status": "success",
    }
