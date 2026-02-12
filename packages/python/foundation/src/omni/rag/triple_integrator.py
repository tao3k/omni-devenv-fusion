"""
triple_integrator.py - Rust + RAG Agent + Zk Triple Integration

Unified architecture that combines:
- Rust Knowledge Graph (high-performance storage & entity management)
- RAG Agent (LLM-based extraction & reasoning)
- Zk Notebook (bidirectional links & atomic notes)

Triple-Binding Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    TripleKnowledgeSystem                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐  │
│  │   Rust Graph     │◄─┤  Sync Coordinator ├──►│   zk Notes   │  │
│  │  (持久化存储)     │  │  (双向同步引擎)    │  │  (双向链接)  │  │
│  └────────┬────────┘  └──────────────────┘  └──────┬──────┘  │
│           │                                         │          │
│           │     ┌─────────────────────┐            │          │
│           └────►│   RAG Agent Layer   │◄───────────┘          │
│                 │  (实体提取+推理)     │                       │
│                 └─────────────────────┘                       │
│                            │                                  │
│                 ┌──────────▼──────────┐                      │
│                 │  TripleQueryEngine  │                      │
│                 │  (统一查询接口)       │                      │
│                 └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘

Usage:
    from omni.rag.triple_integrator import TripleKnowledgeSystem

    tks = TripleKnowledgeSystem(notebook_dir="assets/knowledge")
    tks.extract_from_code(code_content)  # RAG Agent 提取实体
    tks.sync()  # 同步到 Rust Graph + zk
    tks.query("Python 相关的一切")  # 统一查询
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.rag.zk_integration import ZkClient, get_zk_client
from omni.rag.unified_knowledge import UnifiedKnowledgeManager

logger = logging.getLogger(__name__)


@dataclass
class TripleEntity:
    """Entity existing in all three systems."""

    # Identity
    name: str
    entity_type: str

    # Content
    description: str
    content: str = ""  # Full content (for zk)
    aliases: list[str] = field(default_factory=list)

    # Rust Graph
    rust_id: str | None = None
    rust_confidence: float = 1.0

    # zk Notebook
    zk_id: str | None = None  # Note filename stem
    zk_path: str | None = None
    zk_tags: list[str] = field(default_factory=list)
    zk_created: datetime | None = None
    zk_modified: datetime | None = None

    # RAG Extraction
    extraction_source: str | None = None
    extraction_confidence: float = 1.0
    last_extracted: datetime | None = None

    # Relations
    outgoing: list[str] = field(default_factory=list)  # Entity names
    incoming: list[str] = field(default_factory=list)

    def to_zk_content(self) -> str:
        """Generate zk note content."""
        lines = [
            f"# {self.name}",
            "",
            f"> **Type**: {self.entity_type}",
            f"> **Extracted from**: {self.extraction_source or 'Manual'}",
            "",
            self.description,
            "",
        ]

        if self.content:
            lines.append("---")
            lines.append(self.content)

        if self.aliases:
            lines.append("")
            lines.append(f"**Aliases**: {', '.join(self.aliases)}")

        if self.outgoing:
            lines.append("")
            lines.append("## Links")
            for target in self.outgoing:
                slug = target.lower().replace(" ", "-")
                lines.append(f"- [[{slug}]]")

        lines.append("")
        lines.append(f"#{self.entity_type.lower()}")
        for tag in self.zk_tags:
            lines.append(f"#{tag.lower()}")

        return "\n".join(lines)


@dataclass
class TripleRelation:
    """Relation existing in all three systems."""

    source: str
    target: str
    relation_type: str
    description: str = ""

    # Rust Graph
    rust_id: str | None = None
    rust_confidence: float = 1.0

    # zk
    zk_backlink: bool = False

    # RAG Extraction
    extraction_source: str | None = None
    extraction_confidence: float = 1.0


class TripleKnowledgeSystem:
    """Unified system combining Rust Graph, RAG Agent, and zk."""

    def __init__(
        self,
        notebook_dir: str | Path | None = None,
        rust_graph: "PyKnowledgeGraph | None" = None,
    ):
        """Initialize triple knowledge system.

        Args:
            notebook_dir: zk notebook directory.
            rust_graph: PyKnowledgeGraph instance.
        """
        self.notebook_dir = Path(notebook_dir) if notebook_dir else Path.cwd()

        # Rust Graph
        self.rust_graph = rust_graph
        if rust_graph is None:
            try:
                from omni_core_rs import PyKnowledgeGraph

                self.rust_graph = PyKnowledgeGraph()
            except ImportError:
                logger.warning("Rust knowledge graph not available")

        # zk Client
        self.zk_client = get_zk_client(str(self.notebook_dir))

        # Unified Manager (zk-based)
        self.unified = UnifiedKnowledgeManager(
            notebook_dir=str(self.notebook_dir),
            zk_client=self.zk_client,
        )

        # Triple Entity Cache
        self._entity_cache: dict[str, TripleEntity] = {}

        logger.info(f"Initialized TripleKnowledgeSystem at {self.notebook_dir}")

    # =========================================================================
    # RAG Extraction Layer
    # =========================================================================

    def extract_from_code(
        self,
        code_content: str,
        source_name: str = "code",
        extract_relations: bool = True,
    ) -> list[TripleEntity]:
        """Extract entities from code using RAG patterns.

        Args:
            code_content: Code to analyze.
            source_name: Name of the source file.
            extract_relations: Whether to extract relations.

        Returns:
            List of extracted entities.
        """
        entities = self._rag_extract_entities(code_content, source_name)

        if extract_relations:
            relations = self._rag_extract_relations(code_content, source_name, entities)
            for rel in relations:
                self._add_triple_relation(rel)

        # Cache entities
        for entity in entities:
            self._entity_cache[entity.name] = entity

        logger.info(f"Extracted {len(entities)} entities from {source_name}")
        return entities

    def extract_from_text(
        self,
        text_content: str,
        source_name: str = "text",
    ) -> list[TripleEntity]:
        """Extract entities from text using RAG patterns.

        Args:
            text_content: Text to analyze.
            source_name: Name of the source.

        Returns:
            List of extracted entities.
        """
        entities = self._rag_extract_entities(text_content, source_name)

        for entity in entities:
            self._entity_cache[entity.name] = entity

        return entities

    def _rag_extract_entities(self, content: str, source: str) -> list[TripleEntity]:
        """RAG-based entity extraction (simplified)."""
        # Use prompt-based extraction
        entities = []

        # Simple pattern-based extraction (replace with LLM in production)
        import re

        # Common patterns
        patterns = {
            "SKILL": [
                r"(?i)(python|ruby|java|typescript|rust|go|javascript|c\+\+)",
                r"(?i)(docker|kubernetes|git|npm|pip|conda)",
            ],
            "TOOL": [
                r"(?i)(claude|vs\s*code|pycharm|vim|emacs|terminal)",
            ],
            "PROJECT": [
                r"(?i)(omni[\-\s]?dev[\-\s]?fusion|react|vue|fastapi|flask)",
            ],
            "CONCEPT": [
                r"(?i)(api|cli|rpc|rest|graphql|oauth|jwt|websocket)",
            ],
        }

        for entity_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    name = match.strip()
                    if len(name) > 1 and name not in self._entity_cache:
                        entity = TripleEntity(
                            name=name,
                            entity_type=entity_type,
                            description=f"Extracted from {source}",
                            extraction_source=source,
                            extraction_confidence=0.8,
                            last_extracted=datetime.now(),
                        )
                        entities.append(entity)

        return entities

    def _rag_extract_relations(
        self,
        content: str,
        source: str,
        entities: list[TripleEntity],
    ) -> list[TripleRelation]:
        """RAG-based relation extraction."""
        relations = []

        # Simple relation patterns
        import re

        entity_names = {e.name.lower() for e in entities}

        # Pattern: X uses Y
        for e1_name in entity_names:
            for e2_name in entity_names:
                if e1_name != e2_name:
                    # Check for "uses" pattern
                    pattern = rf"(?i){re.escape(e1_name)}\s+(?:uses?|depend(?:s|ing)?\s+on)\s+{re.escape(e2_name)}"
                    if re.search(pattern, content):
                        relations.append(
                            TripleRelation(
                                source=e1_name,
                                target=e2_name,
                                relation_type="USES",
                                description=f"Extracted from {source}",
                                extraction_source=source,
                            )
                        )

        return relations

    def _add_triple_relation(self, relation: TripleRelation) -> None:
        """Add relation to entity's outgoing list."""
        if relation.source in self._entity_cache:
            source_entity = self._entity_cache[relation.source]
            if relation.target not in source_entity.outgoing:
                source_entity.outgoing.append(relation.target)

        if relation.target in self._entity_cache:
            target_entity = self._entity_cache[relation.target]
            if relation.source not in target_entity.incoming:
                target_entity.incoming.append(relation.source)

    # =========================================================================
    # Sync Layer
    # =========================================================================

    def sync(
        self,
        sync_to_rust: bool = True,
        sync_to_zk: bool = True,
    ) -> dict[str, Any]:
        """Sync all cached entities to Rust Graph and zk.

        Args:
            sync_to_rust: Whether to sync to Rust Graph.
            sync_to_zk: Whether to sync to zk.

        Returns:
            Sync statistics.
        """
        stats = {
            "synced_to_rust": 0,
            "synced_to_zk": 0,
            "failed": 0,
            "entities": len(self._entity_cache),
        }

        for name, entity in self._entity_cache.items():
            try:
                # Sync to Rust Graph
                if sync_to_rust and self.rust_graph:
                    from omni_core_rs import PyEntity

                    rust_entity = PyEntity(
                        name=entity.name,
                        entity_type=entity.entity_type,
                        description=entity.description,
                    )
                    if entity.aliases:
                        rust_entity.aliases = entity.aliases

                    self.rust_graph.add_entity(rust_entity)
                    entity.rust_id = rust_entity.id
                    stats["synced_to_rust"] += 1

                # Sync to zk with entity references
                if sync_to_zk:
                    # Build entity references from outgoing relations
                    entity_refs = [{"name": rel, "type": None} for rel in entity.outgoing]

                    # Create note with entity references
                    note = self.zk_client.create_note_with_entities(
                        title=entity.name,
                        body=entity.description,
                        tags=[entity.entity_type.lower()] + entity.zk_tags,
                        entity_refs=entity_refs,
                    )
                    if note:
                        entity.zk_id = note.filename_stem
                        entity.zk_path = note.path
                        stats["synced_to_zk"] += 1

            except Exception as e:
                logger.error(f"Sync failed for {name}: {e}")
                stats["failed"] += 1

        # Re-index zk
        if sync_to_zk:
            self.zk_client.index()

        logger.info(f"Sync complete: {stats}")
        return stats

    def sync_entity(self, name: str) -> TripleEntity | None:
        """Sync a single entity to Rust Graph and zk.

        Args:
            name: Entity name.

        Returns:
            Synced entity or None.
        """
        if name not in self._entity_cache:
            return None

        entity = self._entity_cache[name]

        # Sync to Rust
        if self.rust_graph:
            try:
                from omni_core_rs import PyEntity, PyRelation

                rust_entity = PyEntity(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                )
                self.rust_graph.add_entity(rust_entity)
                entity.rust_id = rust_entity.id

                # Sync relations
                for target_name in entity.outgoing:
                    rel = PyRelation(
                        source=entity.name,
                        target=target_name,
                        relation_type="RELATED_TO",
                        description=f"From {entity.name}",
                    )
                    self.rust_graph.add_relation(rel)
            except Exception as e:
                logger.error(f"Failed to sync {name} to Rust: {e}")

        # Sync to zk
        content = entity.to_zk_content()
        note = self.zk_client.create_note(
            title=entity.name,
            body=content,
            tags=[entity.entity_type.lower()] + entity.zk_tags,
        )
        if note:
            entity.zk_id = note.filename_stem
            entity.zk_path = note.path
            self.zk_client.index()

        return entity

    # =========================================================================
    # Query Layer
    # =========================================================================

    def query(
        self,
        query: str,
        mode: str = "auto",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Unified query across all three systems.

        Args:
            query: Query string.
            mode: Query mode - "entities", "notes", "graph", "auto".
            limit: Maximum results.

        Returns:
            Unified query results.
        """
        results = {
            "query": query,
            "mode": mode,
            "entities": [],
            "notes": [],
            "graph": {},
            "related": [],
        }

        # Query Rust Graph
        if self.rust_graph:
            try:
                entities = self.rust_graph.search_entities(query, limit)
                results["entities"] = [
                    {
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "description": e.description,
                        "aliases": list(e.aliases) if e.aliases else [],
                        "confidence": e.confidence,
                    }
                    for e in entities
                ]
            except Exception as e:
                logger.error(f"Graph query failed: {e}")

        # Query zk
        notes = self.zk_client.search_notes(query, limit=limit)
        results["notes"] = [
            {
                "title": n.title,
                "path": n.path,
                "snippet": n.lead or n.body[:200],
                "tags": n.tags,
            }
            for n in notes
        ]

        # Auto mode: get related from zk
        if mode == "auto" and notes:
            first_note = notes[0]
            related = self.zk_client.find_related(first_note.filename_stem, limit=5)
            results["related"] = [{"title": r.title, "path": r.path} for r in related]

        # Get graph if requested
        if mode == "graph":
            if results["entities"]:
                entity_name = results["entities"][0]["name"]
                results["graph"] = self.get_entity_graph(entity_name, depth=2)

        return results

    def query_entities(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Query only entities from Rust Graph."""
        return self.query(query, mode="entities", limit=limit)["entities"]

    def query_notes(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Query only notes from zk."""
        return self.query(query, mode="notes", limit=limit)["notes"]

    def query_graph(self, entity_name: str, depth: int = 2) -> dict[str, Any]:
        """Get entity graph from Rust Graph."""
        return self.get_entity_graph(entity_name, depth)

    def get_entity_graph(self, entity_name: str, depth: int = 2) -> dict[str, Any]:
        """Get entity and its relations as a graph."""
        if not self.rust_graph:
            return {"nodes": [], "links": [], "entity": entity_name}

        try:
            related = self.rust_graph.multi_hop_search(entity_name, depth)

            nodes = [{"id": entity_name, "type": "root"}]
            links = []

            for entity in related:
                nodes.append(
                    {
                        "id": entity.name,
                        "type": entity.entity_type,
                        "description": entity.description,
                    }
                )

            try:
                relations = self.rust_graph.get_relations(entity_name, None)
                for rel in relations:
                    links.append(
                        {
                            "source": rel.source,
                            "target": rel.target,
                            "type": rel.relation_type,
                        }
                    )
            except Exception:
                pass

            return {"nodes": nodes, "links": links, "entity": entity_name}
        except Exception as e:
            logger.error(f"Get entity graph failed: {e}")
            return {"nodes": [], "links": [], "entity": entity_name}

    # =========================================================================
    # Bidirectional Link Queries (zk <-> Rust Graph)
    # =========================================================================

    def query_with_entity_links(
        self,
        query: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Query with bidirectional links between zk notes and Rust entities.

        Returns:
        - entities: Code entities from Rust Graph
        - notes: zk notes matching the query
        - entity_notes: Notes that reference these entities
        - linked_notes: Notes linked from entity-referencing notes
        """
        results = {
            "query": query,
            "entities": [],
            "notes": [],
            "entity_notes": [],  # Notes that reference entities
            "linked_notes": [],  # Notes linked from entity_notes
        }

        # 1. Query Rust Graph for entities
        if self.rust_graph:
            try:
                entities = self.rust_graph.search_entities(query, limit)
                results["entities"] = [
                    {
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "description": e.description,
                        "aliases": list(e.aliases) if e.aliases else [],
                    }
                    for e in entities
                ]
            except Exception as e:
                logger.error(f"Graph query failed: {e}")

        # 2. Query zk for notes
        notes = self.zk_client.search_notes(query, limit=limit)
        results["notes"] = [
            {
                "title": n.title,
                "path": n.path,
                "snippet": n.lead or n.body[:200],
                "tags": n.tags,
                "entity_refs": self.zk_client.extract_entity_refs(n.body + " " + n.lead),
            }
            for n in notes
        ]

        # 3. Find notes that reference entities
        entity_ref_notes = set()
        for entity in results["entities"]:
            found_notes = self.zk_client.find_notes_referencing_entity(entity["name"])
            for note in found_notes:
                if note.filename_stem not in [n["note_id"] for n in results["entity_notes"]]:
                    results["entity_notes"].append(
                        {
                            "note_id": note.filename_stem,
                            "note_title": note.title,
                            "referenced_entity": entity["name"],
                            "entity_type": entity["entity_type"],
                        }
                    )
                    entity_ref_notes.add(note.filename_stem)

        # 4. Get linked notes from entity-referencing notes
        for note_id in list(entity_ref_notes)[:5]:  # Limit to 5
            linked = self.zk_client.find_related(note_id, max_distance=1, limit=5)
            for l in linked:
                if l.filename_stem not in [n["note_id"] for n in results["linked_notes"]]:
                    results["linked_notes"].append(
                        {
                            "note_id": l.filename_stem,
                            "note_title": l.title,
                            "path": l.path,
                            "linked_from": note_id,
                        }
                    )

        return results

    def get_entity_context(self, entity_name: str) -> dict[str, Any]:
        """Get rich context for an entity: entity + notes + linked notes."""
        context = {
            "entity_name": entity_name,
            "entity": None,
            "zk_note": None,
            "referencing_notes": [],
            "linked_notes": [],
        }

        # 1. Get entity from Rust Graph
        if self.rust_graph:
            try:
                entity = self.rust_graph.get_entity(entity_name)
                if entity:
                    context["entity"] = {
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "description": entity.description,
                        "aliases": list(entity.aliases) if entity.aliases else [],
                    }
            except Exception as e:
                logger.error(f"Get entity failed: {e}")

        # 2. Find zk notes referencing this entity
        notes = self.zk_client.find_notes_referencing_entity(entity_name)
        context["referencing_notes"] = [
            {
                "note_id": n.filename_stem,
                "note_title": n.title,
                "path": n.path,
                "snippet": n.lead or n.body[:300],
            }
            for n in notes
        ]

        # 3. Get linked notes from referencing notes
        for note in notes[:3]:
            linked = self.zk_client.find_related(note.filename_stem, max_distance=1, limit=3)
            for l in linked:
                context["linked_notes"].append(
                    {
                        "note_id": l.filename_stem,
                        "note_title": l.title,
                        "path": l.path,
                    }
                )

        return context

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get unified statistics."""
        rust_stats = {}
        if self.rust_graph:
            try:
                stats = self.rust_graph.get_stats()
                rust_stats = json.loads(stats)
            except Exception:
                pass

        zk_stats = self.zk_client.get_stats()

        return {
            "cached_entities": len(self._entity_cache),
            "rust_graph": rust_stats,
            "zk_notebook": zk_stats,
            "notebook_dir": str(self.notebook_dir),
        }

    def clear_cache(self) -> None:
        """Clear entity cache."""
        self._entity_cache.clear()
        logger.info("Entity cache cleared")


# Convenience function
def get_triple_system(
    notebook_dir: str | None = None,
) -> TripleKnowledgeSystem:
    """Get a triple knowledge system."""
    return TripleKnowledgeSystem(notebook_dir=notebook_dir)


__all__ = [
    "TripleEntity",
    "TripleRelation",
    "TripleKnowledgeSystem",
    "get_triple_system",
]
