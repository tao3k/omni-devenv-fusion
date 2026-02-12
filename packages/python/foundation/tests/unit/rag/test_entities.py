"""
Tests for omni.rag.entities module.
"""

import pytest


class TestEntity:
    """Test Entity dataclass."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        from omni.rag.entities import Entity

        entity = Entity(
            name="Claude Code",
            entity_type="TOOL",
            description="AI coding assistant",
            source="docs/tools.md",
        )

        assert entity.name == "Claude Code"
        assert entity.entity_type == "TOOL"
        assert entity.description == "AI coding assistant"
        assert entity.source == "docs/tools.md"
        assert entity.confidence == 1.0
        assert entity.aliases == []

    def test_entity_with_aliases(self):
        """Test entity with aliases."""
        from omni.rag.entities import Entity

        entity = Entity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
            source="docs/lang.md",
            aliases=["py", "python3"],
        )

        assert len(entity.aliases) == 2
        assert "py" in entity.aliases

    def test_entity_id_generation(self):
        """Test entity ID generation."""
        from omni.rag.entities import Entity

        entity = Entity(
            name="Claude Code",
            entity_type="TOOL",
            description="AI coding assistant",
            source="docs.md",
        )

        assert entity.id == "tool:claude_code"

    def test_entity_hash(self):
        """Test entity hashing."""
        from omni.rag.entities import Entity

        entity1 = Entity(
            name="Test Entity",
            entity_type="CONCEPT",
            description="A test",
            source="test.md",
        )
        entity2 = Entity(
            name="Test Entity",
            entity_type="CONCEPT",
            description="A different description",
            source="other.md",
        )

        # Same name = same hash
        assert hash(entity1) == hash(entity2)

    def test_entity_equality(self):
        """Test entity equality."""
        from omni.rag.entities import Entity

        entity1 = Entity(
            name="Test Entity",
            entity_type="CONCEPT",
            description="A test",
            source="test.md",
        )
        entity2 = Entity(
            name="Test Entity",
            entity_type="CONCEPT",
            description="Different description",
            source="different.md",
        )

        assert entity1 == entity2  # Same name

        entity3 = Entity(
            name="Different Entity",
            entity_type="CONCEPT",
            description="A test",
            source="test.md",
        )

        assert entity1 != entity3  # Different name

    def test_entity_to_dict(self):
        """Test entity serialization to dict."""
        from omni.rag.entities import Entity

        entity = Entity(
            name="Claude Code",
            entity_type="TOOL",
            description="AI coding assistant",
            source="docs.md",
            aliases=["claude"],
            confidence=0.95,
            metadata={"version": "1.0"},
        )

        data = entity.to_dict()

        assert data["name"] == "Claude Code"
        assert data["entity_type"] == "TOOL"
        assert data["confidence"] == 0.95
        assert "claude" in data["aliases"]

    def test_entity_from_dict(self):
        """Test entity deserialization from dict."""
        from omni.rag.entities import Entity

        data = {
            "name": "Test Entity",
            "entity_type": "CONCEPT",
            "description": "A test entity",
            "source": "test.md",
            "aliases": ["test"],
            "confidence": 0.8,
        }

        entity = Entity.from_dict(data)

        assert entity.name == "Test Entity"
        assert entity.entity_type == "CONCEPT"
        assert entity.confidence == 0.8


class TestRelation:
    """Test Relation dataclass."""

    def test_relation_creation(self):
        """Test basic relation creation."""
        from omni.rag.entities import Relation

        relation = Relation(
            source="John Doe",
            target="Acme Corp",
            relation_type="WORKS_FOR",
            description="Employee of Acme",
            source_doc="docs/team.md",
        )

        assert relation.source == "John Doe"
        assert relation.target == "Acme Corp"
        assert relation.relation_type == "WORKS_FOR"
        assert relation.confidence == 1.0

    def test_relation_id_generation(self):
        """Test relation ID generation."""
        from omni.rag.entities import Relation

        relation = Relation(
            source="John Doe",
            target="Acme Corp",
            relation_type="WORKS_FOR",
            description="Works at",
        )

        assert "john_doe" in relation.id
        assert "works_for" in relation.id
        assert "acme_corp" in relation.id

    def test_relation_equality(self):
        """Test relation equality."""
        from omni.rag.entities import Relation

        rel1 = Relation(
            source="A",
            target="B",
            relation_type="USES",
            description="A uses B",
        )
        rel2 = Relation(
            source="A",
            target="B",
            relation_type="USES",
            description="Different description",
        )

        assert rel1 == rel2

        rel3 = Relation(
            source="A",
            target="C",
            relation_type="USES",
            description="A uses C",
        )

        assert rel1 != rel3

    def test_relation_to_dict(self):
        """Test relation serialization."""
        from omni.rag.entities import Relation

        relation = Relation(
            source="Python",
            target="AI Development",
            relation_type="USES",
            description="Used for AI development",
            confidence=0.9,
        )

        data = relation.to_dict()

        assert data["source"] == "Python"
        assert data["target"] == "AI Development"
        assert data["relation_type"] == "USES"
        assert data["confidence"] == 0.9


class TestEntityConstants:
    """Test entity and relation type constants."""

    def test_entity_types(self):
        """Test entity type constants."""
        from omni.rag.entities import EntityType

        assert EntityType.PERSON == "PERSON"
        assert EntityType.ORGANIZATION == "ORGANIZATION"
        assert EntityType.CONCEPT == "CONCEPT"
        assert EntityType.PROJECT == "PROJECT"
        assert EntityType.TOOL == "TOOL"
        assert EntityType.SKILL == "SKILL"

    def test_relation_types(self):
        """Test relation type constants."""
        from omni.rag.entities import RelationType

        assert RelationType.WORKS_FOR == "WORKS_FOR"
        assert RelationType.PART_OF == "PART_OF"
        assert RelationType.USES == "USES"
        assert RelationType.DEPENDS_ON == "DEPENDS_ON"
        assert RelationType.RELATED_TO == "RELATED_TO"


class TestExtractedChunk:
    """Test ExtractedChunk dataclass."""

    def test_extracted_chunk_creation(self):
        """Test extracted chunk creation."""
        from omni.rag.entities import Entity, Relation, ExtractedChunk

        entities = [
            Entity(
                name="Test Entity",
                entity_type="CONCEPT",
                description="A test",
                source="test.md",
            )
        ]
        relations = [
            Relation(
                source="A",
                target="B",
                relation_type="USES",
                description="Uses",
            )
        ]

        chunk = ExtractedChunk(
            chunk_id="chunk-0",
            text="This is test content.",
            entities=entities,
            relations=relations,
            source="test.md",
            chunk_index=0,
        )

        assert chunk.chunk_id == "chunk-0"
        assert chunk.entity_count == 1
        assert chunk.relation_count == 1

    def test_extracted_chunk_to_dict(self):
        """Test chunk serialization."""
        from omni.rag.entities import ExtractedChunk

        chunk = ExtractedChunk(
            chunk_id="chunk-0",
            text="Test",
            entities=[],
            relations=[],
            source="test.md",
        )

        data = chunk.to_dict()

        assert data["chunk_id"] == "chunk-0"
        assert "entities" in data
        assert "relations" in data
