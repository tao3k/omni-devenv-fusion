"""Tests that ensure graph write order: entities before relations.

Rust PyKnowledgeGraph requires source/target entities to exist before add_relation.
These tests would have caught 'Invalid relation' when entities and relations
were written in parallel.
"""

import pytest


@pytest.mark.asyncio
async def test_write_entities_then_relations_order():
    """write_entities_then_relations must call add_entity for all entities before any add_relation."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    from graph import write_entities_then_relations

    call_order = []

    class RecordingStore:
        def add_entity(self, entity):
            call_order.append(("entity", entity))

        def add_relation(self, relation):
            call_order.append(("relation", relation))

    store = RecordingStore()
    entities = [{"name": "A", "entity_type": "CONCEPT"}, {"name": "B", "entity_type": "CONCEPT"}]
    relations = [{"source": "A", "target": "B", "relation_type": "RELATED_TO"}]

    await write_entities_then_relations(store, entities, relations)

    assert len(call_order) == 3
    assert call_order[0][0] == "entity"
    assert call_order[1][0] == "entity"
    assert call_order[2][0] == "relation"
    entity_calls = [c for c in call_order if c[0] == "entity"]
    relation_calls = [c for c in call_order if c[0] == "relation"]
    assert len(entity_calls) == 2
    assert len(relation_calls) == 1
    # All entity calls must occur before any relation call
    last_entity_idx = max(i for i, (kind, _) in enumerate(call_order) if kind == "entity")
    first_relation_idx = min(i for i, (kind, _) in enumerate(call_order) if kind == "relation")
    assert last_entity_idx < first_relation_idx
