"""
Benchmark tests for omni.rag.graph module.

These tests measure the performance of knowledge graph operations.
"""

import pytest
import time


class TestExtractedChunkPerformance:
    """Performance tests for ExtractedChunk."""

    def test_chunk_creation_performance(self):
        """Test ExtractedChunk creation performance."""
        from omni.rag.entities import ExtractedChunk, Entity

        start = time.perf_counter()
        for i in range(1000):
            chunk = ExtractedChunk(
                chunk_id=f"chunk_{i}",
                text=f"Test content {i}",
                entities=[
                    Entity(
                        name=f"Entity_{i}",
                        entity_type="PERSON",
                        description="A test entity",
                        source="test.md",
                    )
                ],
                relations=[],
                source=f"source_{i % 10}",
                chunk_index=i,
            )
        elapsed = time.perf_counter() - start

        # Should create 1000 chunks in under 50ms
        assert elapsed < 0.05, f"Chunk creation took {elapsed:.3f}s"

        print(f"ExtractedChunk creation: 1000 in {elapsed * 1000:.2f}ms")

    def test_chunk_serialization_performance(self):
        """Test ExtractedChunk serialization performance."""
        from omni.rag.entities import ExtractedChunk, Entity

        chunks = [
            ExtractedChunk(
                chunk_id=f"chunk_{i}",
                text=f"content {i}",
                entities=[
                    Entity(
                        name=f"e_{i}",
                        entity_type="PERSON",
                        description="test",
                        source="test.md",
                    )
                ],
                relations=[],
                source=f"source_{i}",
                chunk_index=i,
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            serialized = [c.to_dict() for c in chunks]
        elapsed = time.perf_counter() - start

        # Should serialize 100 chunks 100 times in under 100ms
        assert elapsed < 0.1, f"Chunk serialization took {elapsed:.3f}s"

        print(f"Chunk serialization: 100x100 in {elapsed * 1000:.2f}ms")


class TestEntitySerializationPerformance:
    """Performance tests for entity serialization."""

    def test_entity_to_dict_performance(self):
        """Test entity to_dict performance."""
        from omni.rag.entities import Entity

        entities = [
            Entity(
                name=f"Entity_{i}",
                entity_type=["PERSON", "ORG", "CONCEPT"][i % 3],
                description=f"Description for entity {i}",
                source=f"doc_{i % 10}.md",
                aliases=[f"alias_{i}"],
                confidence=0.8 + (i % 20) / 100.0,
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            dicts = [e.to_dict() for e in entities]
        elapsed = time.perf_counter() - start

        # Should convert 100 entities 100 times in under 100ms
        assert elapsed < 0.1, f"Entity to_dict took {elapsed:.3f}s"

        print(f"Entity to_dict: 100x100 in {elapsed * 1000:.2f}ms")

    def test_entity_from_dict_performance(self):
        """Test entity from_dict performance."""
        from omni.rag.entities import Entity

        dicts = [
            {
                "name": f"Entity_{i}",
                "entity_type": "PERSON",
                "description": f"Desc {i}",
                "source": "test.md",
                "aliases": [],
                "confidence": 0.9,
                "metadata": {},
            }
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            entities = [Entity.from_dict(d) for d in dicts]
        elapsed = time.perf_counter() - start

        # Should create 100 entities 100 times in under 100ms
        assert elapsed < 0.1, f"Entity from_dict took {elapsed:.3f}s"

        print(f"Entity from_dict: 100x100 in {elapsed * 1000:.2f}ms")


class TestRelationSerializationPerformance:
    """Performance tests for relation serialization."""

    def test_relation_to_dict_performance(self):
        """Test relation to_dict performance."""
        from omni.rag.entities import Entity, Relation

        entities = [
            Entity(
                name=f"Entity_{i}", entity_type="PERSON", description=f"Desc {i}", source="test.md"
            )
            for i in range(100)
        ]

        relations = [
            Relation(
                source=entities[i],
                target=entities[(i + 1) % 100],
                relation_type="RELATED_TO",
                description=f"Relation {i}",
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            _dicts = [r.to_dict() for r in relations]
        elapsed = time.perf_counter() - start

        # Should serialize 100 relations 100 times in under 100ms
        assert elapsed < 0.1, f"Relation to_dict took {elapsed:.3f}s"

        print(f"Relation to_dict: 100x100 in {elapsed * 1000:.2f}ms")


class TestPromptConstructionPerformance:
    """Performance tests for prompt construction."""

    def test_prompt_templates_exist(self):
        """Test that prompt templates are properly defined."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT_EN

        # Verify prompts exist and are reasonable length
        assert len(EXTRACT_ENTITIES_PROMPT_EN) > 100

        print(f"Prompt template length: {len(EXTRACT_ENTITIES_PROMPT_EN)} chars")

    def test_json_serialization_performance(self):
        """Test JSON serialization for graph data."""
        import json

        # Create test data
        data = {
            "entities": [
                {"name": f"Entity_{i}", "entity_type": "PERSON", "description": f"Desc {i}"}
                for i in range(50)
            ],
            "relations": [
                {"source": f"Entity_{i}", "target": f"Entity_{(i + 1) % 50}", "type": "RELATED_TO"}
                for i in range(50)
            ],
        }

        start = time.perf_counter()
        for _ in range(100):
            _json_str = json.dumps(data)
            _parsed = json.loads(_json_str)
        elapsed = time.perf_counter() - start

        # Should serialize/deserialize 100 times in under 100ms
        assert elapsed < 0.1, f"JSON serialization took {elapsed:.3f}s"

        print(f"JSON serialization: 100 in {elapsed * 1000:.2f}ms")


# Run performance benchmarks
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
