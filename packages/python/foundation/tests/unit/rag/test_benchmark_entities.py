"""
Benchmark tests for omni.rag.entities module.

These tests measure the performance of entity dataclass operations.
"""

import pytest
import time
from typing import Any


class TestEntityDataclassPerformance:
    """Performance tests for Entity dataclass."""

    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for benchmarking."""
        from omni.rag.entities import Entity

        return [
            Entity(
                name=f"Entity_{i}",
                entity_type=["PERSON", "ORG", "CONCEPT", "TOOL"][i % 4],
                description=f"Description for entity {i}",
                source=f"doc_{i % 10}.md",
                confidence=0.8 + (i % 20) / 100.0,
                aliases=[f"alias_{i}", f"alt_{i}"],
                metadata={"key": f"value_{i}"},
            )
            for i in range(100)
        ]

    def test_entity_creation_performance(self):
        """Test entity creation performance."""
        from omni.rag.entities import Entity

        start = time.perf_counter()
        for i in range(1000):
            entity = Entity(
                name=f"Entity_{i}",
                entity_type="PERSON",
                description=f"Description {i}",
                source="test.md",
            )
        elapsed = time.perf_counter() - start

        # Should create 1000 entities in under 50ms
        assert elapsed < 0.05, f"Entity creation took {elapsed:.3f}s"

        print(f"Entity creation: 1000 entities in {elapsed * 1000:.2f}ms")

    def test_entity_hash_performance(self, sample_entities):
        """Test entity hashing performance."""
        from omni.rag.entities import Entity

        start = time.perf_counter()
        for _ in range(100):
            hashes = [hash(entity) for entity in sample_entities]
        elapsed = time.perf_counter() - start

        # Should hash 100 entities 100 times in under 50ms
        assert elapsed < 0.05, f"Entity hashing took {elapsed:.3f}s"

        print(f"Entity hashing: 100x100 in {elapsed * 1000:.2f}ms")

    def test_entity_equality_performance(self, sample_entities):
        """Test entity equality performance."""
        from omni.rag.entities import Entity

        entities_copy = [
            Entity(
                name=f"Entity_{i}",
                entity_type=["PERSON", "ORG", "CONCEPT", "TOOL"][i % 4],
                description=f"Description for entity {i}",
                source=f"doc_{i % 10}.md",
                confidence=0.8 + (i % 20) / 100.0,
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            for i in range(len(sample_entities)):
                _ = sample_entities[i] == entities_copy[i]
        elapsed = time.perf_counter() - start

        # Should compare 100 entities 100 times in under 50ms
        assert elapsed < 0.05, f"Entity equality took {elapsed:.3f}s"

        print(f"Entity equality: 100x100 comparisons in {elapsed * 1000:.2f}ms")

    def test_entity_to_dict_performance(self, sample_entities):
        """Test entity to_dict performance."""
        from omni.rag.entities import Entity

        start = time.perf_counter()
        for _ in range(100):
            dicts = [entity.to_dict() for entity in sample_entities]
        elapsed = time.perf_counter() - start

        # Should convert 100 entities 100 times in under 100ms
        assert elapsed < 0.1, f"Entity to_dict took {elapsed:.3f}s"

        print(f"Entity to_dict: 100x100 in {elapsed * 1000:.2f}ms")

    def test_entity_from_dict_performance(self, sample_entities):
        """Test entity from_dict performance."""
        from omni.rag.entities import Entity

        dicts = [entity.to_dict() for entity in sample_entities]

        start = time.perf_counter()
        for _ in range(100):
            entities = [Entity.from_dict(d) for d in dicts]
        elapsed = time.perf_counter() - start

        # Should create 100 entities from dicts 100 times in under 100ms
        assert elapsed < 0.1, f"Entity from_dict took {elapsed:.3f}s"

        print(f"Entity from_dict: 100x100 in {elapsed * 1000:.2f}ms")

    def test_entity_id_performance(self, sample_entities):
        """Test entity ID generation performance."""
        from omni.rag.entities import Entity

        start = time.perf_counter()
        for _ in range(100):
            ids = [entity.id for entity in sample_entities]
        elapsed = time.perf_counter() - start

        # Should generate 100 IDs 100 times in under 50ms
        assert elapsed < 0.05, f"Entity ID generation took {elapsed:.3f}s"

        print(f"Entity ID: 100x100 in {elapsed * 1000:.2f}ms")


class TestEntitySetOperationsPerformance:
    """Performance tests for entity set operations."""

    @pytest.fixture
    def entity_set(self):
        """Create a set of entities for testing."""
        from omni.rag.entities import Entity

        return {
            Entity(
                name=f"Entity_{i}", entity_type="PERSON", description=f"Desc {i}", source="test.md"
            )
            for i in range(100)
        }

    def test_entity_set_lookup_performance(self, entity_set):
        """Test entity lookup in set performance."""
        from omni.rag.entities import Entity

        lookup_entities = [
            Entity(
                name=f"Entity_{i}", entity_type="PERSON", description=f"Desc {i}", source="test.md"
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            for entity in lookup_entities:
                _ = entity in entity_set
        elapsed = time.perf_counter() - start

        # Should do 10000 lookups in under 50ms
        assert elapsed < 0.05, f"Entity set lookup took {elapsed:.3f}s"

        print(f"Entity set lookup: 10000 in {elapsed * 1000:.2f}ms")

    def test_entity_set_add_performance(self):
        """Test entity add to set performance."""
        from omni.rag.entities import Entity

        start = time.perf_counter()
        entity_set = set()
        for i in range(1000):
            entity_set.add(
                Entity(
                    name=f"Entity_{i}",
                    entity_type="PERSON",
                    description=f"Desc {i}",
                    source="test.md",
                )
            )
        elapsed = time.perf_counter() - start

        # Should add 1000 entities in under 50ms
        assert elapsed < 0.05, f"Entity set add took {elapsed:.3f}s"

        print(f"Entity set add: 1000 in {elapsed * 1000:.2f}ms")


class TestRelationDataclassPerformance:
    """Performance tests for Relation dataclass."""

    def test_relation_creation_performance(self):
        """Test relation creation performance."""
        from omni.rag.entities import Relation, Entity

        entity_a = Entity(
            name="Python", entity_type="LANGUAGE", description="Lang", source="test.md"
        )
        entity_b = Entity(
            name="Guido van Rossum", entity_type="PERSON", description="Creator", source="test.md"
        )

        start = time.perf_counter()
        for i in range(1000):
            relation = Relation(
                source=entity_a,
                target=entity_b,
                relation_type="CREATED_BY",
                description=f"Relation {i}",
            )
        elapsed = time.perf_counter() - start

        # Should create 1000 relations in under 50ms
        assert elapsed < 0.05, f"Relation creation took {elapsed:.3f}s"

        print(f"Relation creation: 1000 in {elapsed * 1000:.2f}ms")

    def test_relation_to_dict_performance(self):
        """Test relation to_dict performance."""
        from omni.rag.entities import Relation, Entity

        entity_a = Entity(
            name="Python", entity_type="LANGUAGE", description="Lang", source="test.md"
        )
        entity_b = Entity(
            name="Guido van Rossum", entity_type="PERSON", description="Creator", source="test.md"
        )

        relations = [
            Relation(
                source=entity_a,
                target=entity_b,
                relation_type="CREATED_BY",
                description=f"Relation {i}",
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        for _ in range(100):
            dicts = [r.to_dict() for r in relations]
        elapsed = time.perf_counter() - start

        # Should convert 100 relations 100 times in under 100ms
        assert elapsed < 0.1, f"Relation to_dict took {elapsed:.3f}s"

        print(f"Relation to_dict: 100x100 in {elapsed * 1000:.2f}ms")
