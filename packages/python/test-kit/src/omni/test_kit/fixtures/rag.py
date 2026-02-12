"""RAG fixtures for testing knowledge graph and chunking functionality.

Provides pytest fixtures for:
- Mock LLM for entity extraction
- RagConfig fixture for configuration testing
- GraphExtractor fixture for knowledge graph tests
- Chunkers for testing different chunking strategies
- Mock Knowledge Graph Store for testing graph operations
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Any

from omni.rag.config import RAGConfig, KnowledgeGraphConfig, DocumentParsingConfig


@pytest.fixture
def rag_config_fixture() -> RAGConfig:
    """Provide a default RAG configuration for tests."""
    return RAGConfig()


@pytest.fixture
def rag_knowledge_graph_disabled() -> RAGConfig:
    """Provide RAG config with knowledge graph disabled."""
    config = RAGConfig()
    config.knowledge_graph.enabled = False
    return config


@pytest.fixture
def rag_knowledge_graph_enabled() -> RAGConfig:
    """Provide RAG config with knowledge graph enabled."""
    config = RAGConfig()
    config.knowledge_graph.enabled = True
    config.knowledge_graph.entity_types = ["PERSON", "ORGANIZATION", "CONCEPT"]
    config.knowledge_graph.relation_types = ["WORKS_FOR", "PART_OF", "USES"]
    return config


@pytest.fixture
def mock_llm_for_extraction() -> MagicMock:
    """Provide a mock LLM function for entity extraction tests."""
    mock = MagicMock()
    default_response = """{
        "entities": [
            {
                "name": "Test Entity",
                "entity_type": "CONCEPT",
                "description": "A test entity",
                "aliases": ["test"],
                "confidence": 0.9
            }
        ],
        "relations": [
            {
                "source": "Test Entity",
                "target": "Another Entity",
                "relation_type": "RELATED_TO",
                "description": "Related entities",
                "confidence": 0.8
            }
        ]
    }"""
    async_mock = AsyncMock(return_value=default_response)
    mock.side_effect = lambda x: async_mock()
    return mock


@pytest.fixture
def mock_llm_empty_response() -> MagicMock:
    """Provide a mock LLM that returns empty results."""
    mock = MagicMock()
    async_mock = AsyncMock(return_value='{"entities": [], "relations": []}')
    mock.side_effect = lambda x: async_mock()
    return mock


@pytest.fixture
def mock_llm_invalid_json() -> MagicMock:
    """Provide a mock LLM that returns invalid JSON."""
    mock = MagicMock()
    async_mock = AsyncMock(return_value="This is not valid JSON")
    mock.side_effect = lambda x: async_mock()
    return mock


# --- Mock Knowledge Graph Backend ---


class MockPyEntity:
    """Mock PyEntity object."""

    def __init__(self, data: dict):
        self.name = data.get("name", "")
        self.entity_type = data.get("entity_type", "CONCEPT")
        self.description = data.get("description", "")
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class MockPyKnowledgeGraph:
    """Mock implementation of Rust PyKnowledgeGraph for testing."""

    def __init__(self):
        self.entities = {}
        self.relations = []

    def add_entity(self, entity: Any) -> None:
        """Add entity to in-memory store."""
        if hasattr(entity, "to_dict"):
            data = entity.to_dict()
        else:
            data = entity
        # Simple ID generation using name
        entity_id = data.get("name")
        self.entities[entity_id] = data

    def add_relation(self, relation: Any) -> None:
        """Add relation to in-memory store."""
        if hasattr(relation, "to_dict"):
            data = relation.to_dict()
        else:
            data = relation
        self.relations.append(data)

    def search_entities(self, query: str, limit: int = 10) -> list[Any]:
        """Search entities by name."""
        results = []
        for name, data in self.entities.items():
            if query.lower() in name.lower():
                results.append(MockPyEntity(data))
        return results[:limit]

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def get_relations(
        self, entity_name: str | None = None, relation_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get relations filtered by entity or type."""
        results = []
        for r in self.relations:
            match_entity = True
            if entity_name:
                match_entity = r["source"] == entity_name or r["target"] == entity_name

            match_type = True
            if relation_type:
                match_type = r["relation_type"] == relation_type

            if match_entity and match_type:
                results.append(r)
        return results

    def multi_hop_search(
        self,
        start_entities: list[str],
        relation_types: list[str] | None = None,
        max_hops: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Mock multi-hop search (returns direct neighbors)."""
        results = []
        for start in start_entities:
            rels = self.get_relations(entity_name=start)
            for r in rels:
                target = r["target"] if r["source"] == start else r["source"]
                if target in self.entities:
                    results.append(self.entities[target])
        return results[:limit]


@pytest.fixture
def mock_knowledge_graph_store(monkeypatch) -> MockPyKnowledgeGraph:
    """Provide a mock KnowledgeGraphStore with in-memory backend."""
    mock_backend = MockPyKnowledgeGraph()

    # Patch the KnowledgeGraphStore class to use our mock backend
    def mock_init(self):
        self._backend = mock_backend

    monkeypatch.setattr("omni.rag.graph.KnowledgeGraphStore.__init__", mock_init)

    return mock_backend


@pytest.fixture
def rag_graph_extractor(mock_llm_for_extraction) -> Any:
    """Provide a KnowledgeGraphExtractor with mocked LLM."""
    from omni.rag.graph import KnowledgeGraphExtractor

    return KnowledgeGraphExtractor(
        llm_complete_func=mock_llm_for_extraction,
        entity_types=["PERSON", "ORGANIZATION", "CONCEPT", "TOOL"],
        relation_types=["WORKS_FOR", "PART_OF", "USES", "DEPENDS_ON"],
    )


@pytest.fixture
def rag_sentence_chunker() -> Any:
    """Provide a SentenceChunker for testing."""
    from omni.rag.chunking import SentenceChunker

    return SentenceChunker()


@pytest.fixture
def rag_paragraph_chunker() -> Any:
    """Provide a ParagraphChunker for testing."""
    from omni.rag.chunking import ParagraphChunker

    return ParagraphChunker()


@pytest.fixture
def rag_sliding_window_chunker() -> Any:
    """Provide a SlidingWindowChunker for testing."""
    from omni.rag.chunking import SlidingWindowChunker

    return SlidingWindowChunker(window_size=100, step_size=50)


@pytest.fixture
def rag_semantic_chunker(mock_llm_for_extraction) -> Any:
    """Provide a SemanticChunker with mocked LLM."""
    from omni.rag.chunking import SemanticChunker

    return SemanticChunker(llm_complete_func=mock_llm_for_extraction, chunk_size=500)


@pytest.fixture
def sample_text_for_chunking() -> str:
    """Provide sample text for chunking tests."""
    return """This is the first sentence. Here is the second sentence.

    This is a new paragraph with multiple sentences. Sentence three in this paragraph.
    Sentence four continues the thought. Final sentence in this paragraph.

    Another paragraph begins here. Yet another sentence follows.
    """


@pytest.fixture
def sample_text_for_entity_extraction() -> str:
    """Provide sample text containing entities for extraction tests."""
    return """John Doe is a software engineer at Acme Corporation. He works on the
    Omni-Dev-Fusion project using Python and Rust. Jane Smith, a data scientist,
    also contributes to the project. The project is part of the Tao3k organization.

    Python is a programming language developed by the Python Software Foundation.
    Rust is a systems programming language developed by Mozilla.
    """


class RagTestHelper:
    """Helper class for RAG testing."""

    def __init__(self, extractor: Any = None, chunker: Any = None):
        self.extractor = extractor
        self.chunker = chunker

    @staticmethod
    def assert_entities_equal(
        actual: list[Any], expected_names: list[str], expected_types: list[str] | None = None
    ) -> None:
        assert len(actual) == len(expected_names), (
            f"Expected {len(expected_names)} entities, got {len(actual)}"
        )
        for i, (entity, expected_name) in enumerate(zip(actual, expected_names)):
            assert entity.name == expected_name, (
                f"Entity {i}: expected name '{expected_name}', got '{entity.name}'"
            )
        if expected_types:
            for i, (entity, expected_type) in enumerate(zip(actual, expected_types)):
                assert entity.entity_type == expected_type, (
                    f"Entity {i}: expected type '{expected_type}', got '{entity.entity_type}'"
                )

    @staticmethod
    def assert_chunks_valid(
        chunks: list[Any], min_chunk_length: int = 10, max_chunk_length: int = 1000
    ) -> None:
        assert len(chunks) > 0, "Expected at least one chunk"
        for i, chunk in enumerate(chunks):
            assert len(chunk.text) >= min_chunk_length, (
                f"Chunk {i}: text too short ({len(chunk.text)} chars)"
            )
            assert len(chunk.text) <= max_chunk_length, (
                f"Chunk {i}: text too long ({len(chunk.text)} chars)"
            )
            assert hasattr(chunk, "index") and chunk.index is not None, f"Chunk {i}: missing index"

    @staticmethod
    def assert_no_overlap_between_chunks(chunks: list[Any]) -> None:
        if len(chunks) <= 1:
            return
        for i in range(len(chunks) - 1):
            current_end = len(chunks[i].text)
            next_start = chunks[i + 1].text.find(chunks[i + 1].text[:20])
            assert next_start < 10 or next_start > current_end - 10, (
                f"Chunks {i} and {i + 1} appear to overlap significantly"
            )


@pytest.fixture
def rag_test_helper() -> RagTestHelper:
    """Provide a RAG test helper instance."""
    return RagTestHelper()


__all__ = [
    "rag_config_fixture",
    "rag_knowledge_graph_disabled",
    "rag_knowledge_graph_enabled",
    "mock_llm_for_extraction",
    "mock_llm_empty_response",
    "mock_llm_invalid_json",
    "mock_knowledge_graph_store",
    "MockPyKnowledgeGraph",
    "MockPyEntity",
    "rag_graph_extractor",
    "rag_sentence_chunker",
    "rag_paragraph_chunker",
    "rag_sliding_window_chunker",
    "rag_semantic_chunker",
    "sample_text_for_chunking",
    "sample_text_for_entity_extraction",
    "rag_test_helper",
    "RagTestHelper",
]
