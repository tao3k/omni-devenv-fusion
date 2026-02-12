"""
entities.py - Entity and Relation Types

Provides dataclasses for knowledge graph entities and relations.
These types bridge Python extraction with Rust storage.

Entity Types:
- Entity: Named entities extracted from text (PERSON, ORGANIZATION, etc.)
- Relation: Relationships between entities

Usage:
    from omni.rag.entities import Entity, Relation

    entity = Entity(
        name="Claude Code",
        entity_type="TOOL",
        description="AI coding assistant",
        source="docs/tools.md",
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """Represents a named entity extracted from text.

    Attributes:
        name: The entity name/identifier.
        entity_type: Type of entity (PERSON, ORGANIZATION, CONCEPT, etc.)
        description: Brief description of the entity.
        source: Source document or URL where entity was found.
        aliases: Alternative names or aliases for this entity.
        confidence: Confidence score (0.0-1.0) from extraction.
        metadata: Additional metadata (properties, attributes, etc.)
    """

    name: str
    entity_type: str
    description: str
    source: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Hash based on entity name for set/dict usage."""
        return hash(self.name)

    def __eq__(self, other):
        """Entities are equal if they have the same name."""
        if not isinstance(other, Entity):
            return False
        return self.name == other.name

    @property
    def id(self) -> str:
        """Generate a unique ID for the entity."""
        return f"{self.entity_type}:{self.name}".lower().replace(" ", "_")

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "source": self.source,
            "aliases": self.aliases,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entity:
        """Create Entity from dictionary."""
        return cls(
            name=data["name"],
            entity_type=data["entity_type"],
            description=data.get("description", ""),
            source=data.get("source", ""),
            aliases=data.get("aliases", []),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Relation:
    """Represents a relationship between two entities.

    Attributes:
        source: Source entity name.
        target: Target entity name.
        relation_type: Type of relationship (WORKS_FOR, PART_OF, USES, etc.)
        description: Brief description of the relationship.
        source_doc: Document where relation was extracted.
        confidence: Confidence score (0.0-1.0).
        metadata: Additional metadata (strength, evidence, etc.)
    """

    source: str
    target: str
    relation_type: str
    description: str = ""
    source_doc: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Hash based on source, target, and relation type."""
        return hash(f"{self.source}|{self.target}|{self.relation_type}")

    def __eq__(self, other):
        """Relations are equal if they connect the same entities with same type."""
        if not isinstance(other, Relation):
            return False
        return (
            self.source == other.source
            and self.target == other.target
            and self.relation_type == other.relation_type
        )

    @property
    def id(self) -> str:
        """Generate a unique ID for the relation."""
        return f"{self.source}|{self.relation_type}|{self.target}".lower().replace(" ", "_")

    def to_dict(self) -> dict[str, Any]:
        """Convert relation to dictionary."""
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "description": self.description,
            "source_doc": self.source_doc,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relation:
        """Create Relation from dictionary."""
        return cls(
            source=data["source"],
            target=data["target"],
            relation_type=data["relation_type"],
            description=data.get("description", ""),
            source_doc=data.get("source_doc", ""),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EntityMention:
    """Represents where an entity appears in text.

    Attributes:
        entity_id: ID of the entity.
        text: The actual text span that was matched.
        start_char: Starting character position.
        end_char: Ending character position.
        context: Surrounding text context.
    """

    entity_id: str
    text: str
    start_char: int
    end_char: int
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert mention to dictionary."""
        return {
            "entity_id": self.entity_id,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "context": self.context,
        }


@dataclass
class ExtractedChunk:
    """Represents a chunk of extracted content with its entities and relations.

    Attributes:
        chunk_id: Unique identifier for this chunk.
        text: Original text content.
        entities: Entities extracted from this chunk.
        relations: Relations extracted from this chunk.
        source: Source document/path.
        chunk_index: Position in document chunk sequence.
    """

    chunk_id: str
    text: str
    entities: list[Entity]
    relations: list[Relation]
    source: str
    chunk_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "source": self.source,
            "chunk_index": self.chunk_index,
        }

    @property
    def entity_count(self) -> int:
        """Number of entities in this chunk."""
        return len(self.entities)

    @property
    def relation_count(self) -> int:
        """Number of relations in this chunk."""
        return len(self.relations)


# Standard entity types
class EntityType:
    """Standard entity type constants."""

    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    CONCEPT = "CONCEPT"
    PROJECT = "PROJECT"
    TOOL = "TOOL"
    SKILL = "SKILL"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    DOCUMENT = "DOCUMENT"
    CODE = "CODE"
    API = "API"
    ERROR = "ERROR"
    PATTERN = "PATTERN"


# Standard relation types
class RelationType:
    """Standard relation type constants."""

    WORKS_FOR = "WORKS_FOR"
    PART_OF = "PART_OF"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    SIMILAR_TO = "SIMILAR_TO"
    LOCATED_IN = "LOCATED_IN"
    CREATED_BY = "CREATED_BY"
    DOCUMENTED_IN = "DOCUMENTED_IN"
    RELATED_TO = "RELATED_TO"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CONTAINS = "CONTAINS"


__all__ = [
    "Entity",
    "Relation",
    "EntityMention",
    "ExtractedChunk",
    "EntityType",
    "RelationType",
]
