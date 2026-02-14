import json

import pytest

from graph import search_graph  # noqa: E402  (skill scripts on sys.path via conftest)


def _unwrap(result):
    """Unwrap MCP tool result envelope to get the inner payload dict."""
    if isinstance(result, dict) and "content" in result:
        text = result["content"][0].get("text", "")
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (ValueError, TypeError):
            return result
    return result


@pytest.mark.asyncio
async def test_search_graph_entities(mock_knowledge_graph_store):
    """Test searching for entities using the skill command."""
    mock_knowledge_graph_store.add_entity(
        {"name": "Python", "entity_type": "SKILL", "description": "Programming language"}
    )

    raw = await search_graph(query="Python", mode="entities")
    result = _unwrap(raw)

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

    raw = await search_graph(query="Developer", mode="relations")
    result = _unwrap(raw)

    assert "relations" in result
    assert len(result["relations"]) == 1
    assert result["relations"][0]["target"] == "Python"


@pytest.mark.asyncio
async def test_search_graph_hybrid(mock_knowledge_graph_store):
    """Test hybrid search (entity + neighbors)."""
    mock_knowledge_graph_store.add_entity({"name": "Developer", "entity_type": "PERSON"})
    mock_knowledge_graph_store.add_entity({"name": "Python", "entity_type": "SKILL"})
    mock_knowledge_graph_store.add_relation(
        {"source": "Developer", "target": "Python", "relation_type": "USES"}
    )

    raw = await search_graph(query="Developer", mode="hybrid")
    result = _unwrap(raw)

    assert result.get("entity", {}).get("name") == "Developer"

    related = result.get("related_entities", [])
    assert len(related) > 0
    assert any(e["name"] == "Python" for e in related)


@pytest.mark.asyncio
async def test_search_graph_backend_missing(monkeypatch):
    """Test error handling when backend is missing."""
    from omni.rag.graph import KnowledgeGraphStore

    def mock_init_none(self):
        self._backend = None

    monkeypatch.setattr(KnowledgeGraphStore, "__init__", mock_init_none)

    raw = await search_graph(query="Python")
    result = _unwrap(raw)

    if isinstance(result, dict):
        assert result.get("error") or result.get("status") == "error"
    else:
        assert "not available" in result or "failed" in result.lower()
