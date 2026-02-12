import pytest
import sys
import json
from pathlib import Path

# Add skill scripts to path to import search_graph
skill_scripts = Path(__file__).parents[1] / "scripts"
sys.path.append(str(skill_scripts))

# Now import the skill command
from graph import search_graph

# Import fixtures - conftest.py in test directory provides these
# mock_knowledge_graph_store is provided by omni.test_kit.fixtures.rag via conftest.py


@pytest.mark.asyncio
async def test_search_graph_entities(mock_knowledge_graph_store):
    """Test searching for entities using the skill command."""
    # Setup mock data
    mock_knowledge_graph_store.add_entity(
        {"name": "Python", "entity_type": "SKILL", "description": "Programming language"}
    )

    # Call skill command
    result_json = await search_graph(query="Python", mode="entities")
    result = json.loads(result_json)

    # Verify
    assert "entity" in result
    assert result["entity"]["name"] == "Python"
    assert result["entity"]["entity_type"] == "SKILL"


@pytest.mark.asyncio
async def test_search_graph_relations(mock_knowledge_graph_store):
    """Test searching for relations."""
    mock_knowledge_graph_store.add_relation(
        {
            "source": "Developer",
            "target": "Python",
            "relation_type": "USES",
            "description": "Dev uses Python",
        }
    )

    # Call skill command
    result_json = await search_graph(query="Developer", mode="relations")
    result = json.loads(result_json)

    # Verify
    assert "relations" in result
    assert len(result["relations"]) == 1
    assert result["relations"][0]["target"] == "Python"


@pytest.mark.asyncio
async def test_search_graph_hybrid(mock_knowledge_graph_store):
    """Test hybrid search (entity + neighbors)."""
    # Setup graph: Dev -> USES -> Python
    mock_knowledge_graph_store.add_entity({"name": "Developer", "entity_type": "PERSON"})
    mock_knowledge_graph_store.add_entity({"name": "Python", "entity_type": "SKILL"})
    mock_knowledge_graph_store.add_relation(
        {"source": "Developer", "target": "Python", "relation_type": "USES"}
    )

    # Call skill command
    result_json = await search_graph(query="Developer", mode="hybrid")
    result = json.loads(result_json)

    # Verify entity found
    assert result.get("entity", {}).get("name") == "Developer"

    # Verify related entities (multi-hop mock)
    # Note: MockPyKnowledgeGraph.multi_hop_search needs to find "Python"
    # The simple mock implementation looks for direct relations.
    related = result.get("related_entities", [])
    assert len(related) > 0
    assert any(e["name"] == "Python" for e in related)


@pytest.mark.asyncio
async def test_search_graph_backend_missing(monkeypatch):
    """Test error handling when backend is missing."""
    # Force backend to None
    from omni.rag.graph import KnowledgeGraphStore

    def mock_init_none(self):
        self._backend = None

    monkeypatch.setattr(KnowledgeGraphStore, "__init__", mock_init_none)

    result_json = await search_graph(query="Python")

    # It might return an error string directly, not JSON
    if result_json.startswith("{"):
        result = json.loads(result_json)
        assert result.get("error") or result.get("status") == "error"
    else:
        assert "not available" in result_json or "failed" in result_json.lower()
