"""
zk_enhancer.py - Secondary Enhancement Layer for ZK Query Results.

Takes raw ZK query results and enriches them using Rust-accelerated omni-knowledge:
1. Extract entity references from wikilinks ([[Entity#type]])
2. Parse YAML frontmatter for structured metadata
3. Build Entity/Relation entries in KnowledgeGraph
4. Return enriched results with entity context and relationship data

Architecture:
    ZK CLI (primary engine) → raw notes
        ↓
    ZkEnhancer (this module) → Rust omni-knowledge bindings
        ↓
    Enriched results with entities, relations, frontmatter metadata

Usage:
    from omni.rag.zk_enhancer import ZkEnhancer

    enhancer = ZkEnhancer()
    enriched = enhancer.enhance_notes(zk_notes)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .zk_client import ZkNote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rust binding imports (graceful fallback)
# ---------------------------------------------------------------------------

_RUST_AVAILABLE = False
_RUST_ENHANCER_AVAILABLE = False
try:
    from omni_core_rs import (
        PyEntity,
        PyKnowledgeGraph,
        PyRelation,
        zk_extract_entity_refs,
        zk_get_ref_stats,
    )

    _RUST_AVAILABLE = True
except ImportError:
    logger.debug("omni_core_rs not available; ZkEnhancer will use Python fallback")

try:
    from omni_core_rs import (
        zk_enhance_note as _rust_enhance_note,
        zk_enhance_notes_batch as _rust_enhance_notes_batch,
        zk_parse_frontmatter as _rust_parse_frontmatter,
    )

    _RUST_ENHANCER_AVAILABLE = True
except ImportError:
    logger.debug("Rust enhancer bindings not available; using Python fallback")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FrontmatterData:
    """Parsed YAML frontmatter from a markdown note."""

    title: str | None = None
    description: str | None = None
    name: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    routing_keywords: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityRef:
    """An entity reference extracted from note content."""

    name: str
    entity_type: str | None = None
    original: str = ""


@dataclass
class EnrichedNote:
    """A ZK note enriched with secondary analysis."""

    note: ZkNote
    frontmatter: FrontmatterData
    entity_refs: list[EntityRef]
    ref_stats: dict[str, Any]
    # Relationships inferred from this note
    relations: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Frontmatter parser (Python fallback for omni-scanner)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(content: str) -> FrontmatterData:
    """Extract and parse YAML frontmatter from markdown content."""
    if not content:
        return FrontmatterData()

    m = _FM_RE.match(content)
    if not m:
        return FrontmatterData()

    yaml_text = m.group(1)
    try:
        import yaml

        data = yaml.safe_load(yaml_text) or {}
    except Exception:
        return FrontmatterData()

    if not isinstance(data, dict):
        return FrontmatterData()

    metadata = data.get("metadata", {}) or {}

    return FrontmatterData(
        title=data.get("title"),
        description=data.get("description"),
        name=data.get("name"),
        category=data.get("category"),
        tags=data.get("tags") or metadata.get("tags") or [],
        routing_keywords=metadata.get("routing_keywords", []),
        intents=metadata.get("intents", []),
        raw=data,
    )


# ---------------------------------------------------------------------------
# Python fallback for entity extraction
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]#|]+)(?:#([^\]#|]+))?(?:\|[^\]]+)?\]\]")


def _extract_entity_refs_py(content: str) -> list[EntityRef]:
    """Pure-Python fallback for extracting entity references from wikilinks."""
    seen: set[str] = set()
    refs: list[EntityRef] = []
    for m in _WIKILINK_RE.finditer(content):
        name = m.group(1).strip()
        etype = m.group(2).strip() if m.group(2) else None
        if name not in seen:
            seen.add(name)
            refs.append(EntityRef(name=name, entity_type=etype, original=m.group(0)))
    return refs


# ---------------------------------------------------------------------------
# ZkEnhancer
# ---------------------------------------------------------------------------


class ZkEnhancer:
    """Secondary enhancement layer for ZK query results.

    Uses Rust-accelerated omni-knowledge when available, otherwise falls back
    to pure-Python implementations.

    Responsibilities (things ZK CLI cannot do natively):
    - Extract typed entity references from [[wikilinks]]
    - Parse YAML frontmatter into structured metadata
    - Build Entity/Relation graph from note relationships
    - Compute reference statistics for ranking/scoring
    """

    def __init__(self, graph: Any | None = None) -> None:
        """Initialize enhancer.

        Args:
            graph: Optional PyKnowledgeGraph instance. Created automatically
                   if omni_core_rs is available and none provided.
        """
        self._graph = graph
        if self._graph is None and _RUST_AVAILABLE:
            self._graph = PyKnowledgeGraph()

    @property
    def rust_available(self) -> bool:
        """Whether Rust bindings are available."""
        return _RUST_AVAILABLE

    @property
    def graph(self) -> Any | None:
        """The underlying KnowledgeGraph instance."""
        return self._graph

    # ------------------------------------------------------------------
    # Core: enhance a batch of ZK notes
    # ------------------------------------------------------------------

    def enhance_notes(self, notes: list[ZkNote]) -> list[EnrichedNote]:
        """Enhance a batch of ZK notes with secondary analysis.

        Delegates to Rust `zk_enhance_notes_batch` when available (Rayon-parallelized).
        Falls back to Python-only path otherwise.

        Args:
            notes: Raw ZK notes from ZkClient queries.

        Returns:
            List of EnrichedNote with frontmatter, entities, and relations.
        """
        if _RUST_ENHANCER_AVAILABLE and len(notes) > 0:
            try:
                return self._enhance_notes_rust(notes)
            except Exception as e:
                logger.warning("Rust batch enhance failed, falling back to Python: %s", e)

        return [self._enhance_note_python(note) for note in notes]

    def enhance_note(self, note: ZkNote) -> EnrichedNote:
        """Enhance a single ZK note.

        Delegates to Rust when available, Python fallback otherwise.

        Args:
            note: Raw ZK note.

        Returns:
            EnrichedNote with full secondary analysis.
        """
        if _RUST_ENHANCER_AVAILABLE:
            try:
                return self._enhance_note_rust(note)
            except Exception as e:
                logger.warning("Rust enhance failed, falling back to Python: %s", e)

        return self._enhance_note_python(note)

    # ------------------------------------------------------------------
    # Rust-accelerated path
    # ------------------------------------------------------------------

    def _enhance_note_rust(self, note: ZkNote) -> EnrichedNote:
        """Enhance via Rust omni-knowledge (single note)."""
        content = note.raw_content or ""
        result = _rust_enhance_note(note.path, note.title, content)
        return self._convert_rust_result(note, result)

    def _enhance_notes_rust(self, notes: list[ZkNote]) -> list[EnrichedNote]:
        """Enhance via Rust omni-knowledge (batch, Rayon-parallelized)."""
        inputs = [(n.path, n.title, n.raw_content or "") for n in notes]
        rust_results = _rust_enhance_notes_batch(inputs)

        enriched: list[EnrichedNote] = []
        for note, result in zip(notes, rust_results):
            enriched.append(self._convert_rust_result(note, result))
        return enriched

    def _convert_rust_result(self, note: ZkNote, result: Any) -> EnrichedNote:
        """Convert a Rust PyEnhancedNote to Python EnrichedNote."""
        fm_rust = result.frontmatter
        fm = FrontmatterData(
            title=fm_rust.title,
            description=fm_rust.description,
            name=fm_rust.name,
            category=fm_rust.category,
            tags=fm_rust.tags,
            routing_keywords=fm_rust.routing_keywords,
            intents=fm_rust.intents,
        )

        entity_refs = [
            EntityRef(name=name, entity_type=etype) for name, etype in result.entity_refs
        ]

        ref_stats = {
            "total_refs": result.total_refs,
            "unique_entities": result.unique_entities,
            "by_type": [],
        }

        relations = [
            {
                "source": r.source,
                "target": r.target,
                "relation_type": r.relation_type,
                "description": r.description,
            }
            for r in result.relations
        ]

        # Register in graph
        if self._graph is not None:
            self._register_in_graph(note, fm, entity_refs, relations)

        return EnrichedNote(
            note=note,
            frontmatter=fm,
            entity_refs=entity_refs,
            ref_stats=ref_stats,
            relations=relations,
        )

    # ------------------------------------------------------------------
    # Python fallback path
    # ------------------------------------------------------------------

    def _enhance_note_python(self, note: ZkNote) -> EnrichedNote:
        """Enhance using pure-Python implementation (fallback)."""
        content = note.raw_content or ""

        fm = _parse_frontmatter(content)
        entity_refs = self._extract_entities(content)
        ref_stats = self._get_ref_stats(content)
        relations = self._infer_relations(note, fm, entity_refs)

        if self._graph is not None:
            self._register_in_graph(note, fm, entity_refs, relations)

        return EnrichedNote(
            note=note,
            frontmatter=fm,
            entity_refs=entity_refs,
            ref_stats=ref_stats,
            relations=relations,
        )

    # ------------------------------------------------------------------
    # Entity extraction (Rust or Python)
    # ------------------------------------------------------------------

    def _extract_entities(self, content: str) -> list[EntityRef]:
        """Extract entity references using Rust or Python fallback."""
        if _RUST_AVAILABLE:
            try:
                rust_refs = zk_extract_entity_refs(content)
                return [
                    EntityRef(
                        name=r.name,
                        entity_type=r.entity_type,
                        original=r.original,
                    )
                    for r in rust_refs
                ]
            except Exception as e:
                logger.warning("Rust entity extraction failed, using fallback: %s", e)

        return _extract_entity_refs_py(content)

    def _get_ref_stats(self, content: str) -> dict[str, Any]:
        """Get reference statistics using Rust or Python fallback."""
        if _RUST_AVAILABLE:
            try:
                stats = zk_get_ref_stats(content)
                return {
                    "total_refs": stats.total_refs,
                    "unique_entities": stats.unique_entities,
                    "by_type": stats.by_type,
                }
            except Exception as e:
                logger.warning("Rust ref stats failed, using fallback: %s", e)

        refs = _extract_entity_refs_py(content)
        type_counts: dict[str, int] = {}
        for r in refs:
            t = r.entity_type or "none"
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_refs": len(refs),
            "unique_entities": len(refs),
            "by_type": list(type_counts.items()),
        }

    # ------------------------------------------------------------------
    # Relation inference
    # ------------------------------------------------------------------

    def _infer_relations(
        self,
        note: ZkNote,
        fm: FrontmatterData,
        entity_refs: list[EntityRef],
    ) -> list[dict[str, str]]:
        """Infer relations from note structure.

        Relations inferred:
        - DOCUMENTED_IN: Entity refs → this document
        - CONTAINS: Skill SKILL.md → its tools (from frontmatter)
        - RELATED_TO: Notes sharing tags
        - USES: From routing_keywords and intents
        """
        relations: list[dict[str, str]] = []
        doc_name = note.title or note.filename_stem or note.path

        # Entity refs → DOCUMENTED_IN
        for ref in entity_refs:
            relations.append(
                {
                    "source": ref.name,
                    "target": doc_name,
                    "relation_type": "DOCUMENTED_IN",
                    "description": f"{ref.name} documented in {doc_name}",
                }
            )

        # Skill frontmatter → CONTAINS
        if fm.name and "SKILL" in (note.filename_stem or "").upper():
            relations.append(
                {
                    "source": fm.name,
                    "target": doc_name,
                    "relation_type": "CONTAINS",
                    "description": f"Skill {fm.name} defined in {doc_name}",
                }
            )

        # Tags → potential RELATED_TO (stored for later graph use)
        for tag in fm.tags:
            relations.append(
                {
                    "source": doc_name,
                    "target": f"tag:{tag}",
                    "relation_type": "RELATED_TO",
                    "description": f"{doc_name} tagged with {tag}",
                }
            )

        return relations

    # ------------------------------------------------------------------
    # Graph registration
    # ------------------------------------------------------------------

    def _register_in_graph(
        self,
        note: ZkNote,
        fm: FrontmatterData,
        entity_refs: list[EntityRef],
        relations: list[dict[str, str]],
    ) -> None:
        """Register note data in the KnowledgeGraph.

        Creates Entity nodes for the document and referenced entities,
        then creates Relation edges between them.
        """
        if not _RUST_AVAILABLE or self._graph is None:
            return

        doc_name = note.title or note.filename_stem or note.path

        # Register document as entity
        try:
            entity_type = "DOCUMENT"
            if fm.name and "SKILL" in (note.filename_stem or "").upper():
                entity_type = "SKILL"
            elif fm.category == "pattern":
                entity_type = "PATTERN"

            doc_entity = PyEntity(
                name=doc_name,
                entity_type=entity_type,
                description=fm.description or f"Note: {doc_name}",
            )
            self._graph.add_entity(doc_entity)
        except Exception as e:
            logger.debug("Failed to register document entity %s: %s", doc_name, e)

        # Register referenced entities
        for ref in entity_refs:
            try:
                etype = ref.entity_type.upper() if ref.entity_type else "CONCEPT"
                ref_entity = PyEntity(
                    name=ref.name,
                    entity_type=etype,
                    description=f"Referenced in {doc_name}",
                )
                self._graph.add_entity(ref_entity)
            except Exception as e:
                logger.debug("Failed to register entity %s: %s", ref.name, e)

        # Register tag entities
        for tag in fm.tags:
            try:
                tag_entity = PyEntity(
                    name=f"tag:{tag}",
                    entity_type="CONCEPT",
                    description=f"Tag: {tag}",
                )
                self._graph.add_entity(tag_entity)
            except Exception as e:
                logger.debug("Failed to register tag entity %s: %s", tag, e)

        # Register relations
        for rel in relations:
            try:
                py_rel = PyRelation(
                    source=rel["source"],
                    target=rel["target"],
                    relation_type=rel["relation_type"],
                    description=rel["description"],
                )
                self._graph.add_relation(py_rel)
            except Exception as e:
                logger.debug(
                    "Failed to register relation %s->%s: %s",
                    rel["source"],
                    rel["target"],
                    e,
                )

    # ------------------------------------------------------------------
    # Graph persistence
    # ------------------------------------------------------------------

    def save_graph(self, path: str | Path) -> None:
        """Persist the KnowledgeGraph to Lance tables."""
        if self._graph is None:
            return
        try:
            from omni.rag.dual_core._config import _save_kg

            _save_kg(self._graph)
            logger.info("Knowledge graph saved to Lance")
        except ImportError:
            logger.debug("dual_core not available, skipping graph save")

    def load_graph(self, path: str | Path) -> None:
        """Load the KnowledgeGraph from Lance tables."""
        if self._graph is None:
            return
        try:
            from omni.rag.dual_core._config import _load_kg

            loaded = _load_kg()
            if loaded is not None:
                self._graph = loaded
                logger.info("Knowledge graph loaded from Lance")
                return
        except ImportError:
            pass
        logger.debug("No KnowledgeGraph found in Lance")

    def get_graph_stats(self) -> dict[str, Any]:
        """Get KnowledgeGraph statistics."""
        if self._graph is None:
            return {"error": "No graph available"}
        import json

        return json.loads(self._graph.get_stats())

    # ------------------------------------------------------------------
    # Query helpers (leverage graph for enhanced retrieval)
    # ------------------------------------------------------------------

    def find_related_entities(self, entity_name: str, max_hops: int = 2) -> list[dict[str, Any]]:
        """Find entities related to the given name via multi-hop traversal.

        This is the key enhancement ZK CLI cannot do: typed entity graph
        traversal with configurable hop depth.

        Args:
            entity_name: Starting entity name.
            max_hops: Maximum graph hops.

        Returns:
            List of related entities with type and description.
        """
        if not _RUST_AVAILABLE or self._graph is None:
            return []

        import json

        try:
            entities = self._graph.multi_hop_search(entity_name, max_hops)
            return [json.loads(e.to_dict()) for e in entities]
        except Exception as e:
            logger.warning("Multi-hop search failed: %s", e)
            return []

    def search_entities(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search entities in the graph by name or description."""
        if not _RUST_AVAILABLE or self._graph is None:
            return []

        import json

        try:
            entities = self._graph.search_entities(query, limit)
            return [json.loads(e.to_dict()) for e in entities]
        except Exception as e:
            logger.warning("Entity search failed: %s", e)
            return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_zk_enhancer(graph: Any | None = None) -> ZkEnhancer:
    """Create a ZkEnhancer instance.

    Args:
        graph: Optional PyKnowledgeGraph instance.

    Returns:
        ZkEnhancer instance.
    """
    return ZkEnhancer(graph)


__all__ = [
    "EntityRef",
    "EnrichedNote",
    "FrontmatterData",
    "ZkEnhancer",
    "get_zk_enhancer",
]
