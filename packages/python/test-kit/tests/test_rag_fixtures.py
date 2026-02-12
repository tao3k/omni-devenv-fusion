"""Test RAG fixtures integration with omni.test_kit.

This file demonstrates how to use RAG fixtures for testing.
"""

import pytest

pytest_plugins = ["omni.test_kit.fixtures.rag"]

# Import RagTestHelper directly since it's a class, not a fixture
from omni.test_kit.fixtures.rag import RagTestHelper


class TestRAGFixturesDemo:
    """Demonstrate RAG fixtures usage."""

    def test_rag_config_fixture(self, rag_config_fixture):
        """Use rag_config_fixture to get default RAG configuration."""
        assert rag_config_fixture.enabled is True
        assert rag_config_fixture.knowledge_graph.enabled is True
        assert rag_config_fixture.document_parsing.enabled is True

    def test_knowledge_graph_disabled(self, rag_knowledge_graph_disabled):
        """Test with knowledge graph disabled."""
        assert rag_knowledge_graph_disabled.knowledge_graph.enabled is False

    def test_knowledge_graph_enabled(self, rag_knowledge_graph_enabled):
        """Test with custom knowledge graph configuration."""
        config = rag_knowledge_graph_enabled
        assert config.knowledge_graph.enabled is True
        assert "PERSON" in config.knowledge_graph.entity_types
        assert "ORGANIZATION" in config.knowledge_graph.entity_types

    def test_mock_llm_response(self, mock_llm_for_extraction):
        """Test mock LLM returns expected response."""
        response = mock_llm_for_extraction("test prompt")
        # Response returns a coroutine-like object that yields the response
        import asyncio

        if asyncio.iscoroutine(response):
            response = asyncio.run(response)
        assert "entities" in response
        assert "relations" in response

    @pytest.mark.asyncio
    async def test_mock_llm_awaitable(self, mock_llm_for_extraction):
        """Test mock LLM can be awaited."""
        response = await mock_llm_for_extraction("test prompt")
        assert "Test Entity" in response

    @pytest.mark.asyncio
    async def test_sentence_chunker(self, rag_sentence_chunker, sample_text_for_chunking):
        """Test sentence chunking with fixture (async method)."""
        chunks = await rag_sentence_chunker.chunk(sample_text_for_chunking)
        # Sentence chunker returns chunks with sentence metadata
        assert len(chunks) >= 1
        assert chunks[0].chunk_type == "sentence"
        assert "sentences" in chunks[0].metadata

    @pytest.mark.asyncio
    async def test_paragraph_chunker(self, rag_paragraph_chunker, sample_text_for_chunking):
        """Test paragraph chunking with fixture (async method)."""
        chunks = await rag_paragraph_chunker.chunk(sample_text_for_chunking)
        # Paragraph chunker splits by paragraphs
        assert len(chunks) >= 1
        assert chunks[0].chunk_type == "paragraph"

    @pytest.mark.asyncio
    async def test_sliding_window_chunker(self, rag_sliding_window_chunker):
        """Test sliding window chunking with fixture (async method)."""
        # Use longer text for sliding window
        long_text = "word " * 200
        chunks = await rag_sliding_window_chunker.chunk(long_text)
        assert len(chunks) >= 1

    def test_rag_test_helper(self, rag_test_helper):
        """Test RagTestHelper is available."""
        assert rag_test_helper is not None

    def test_entity_extraction_with_fixtures(
        self, rag_graph_extractor, sample_text_for_entity_extraction
    ):
        """Test entity extraction using fixtures."""
        import asyncio

        extractor = rag_graph_extractor
        # Note: This would need async test in real scenario
        # For now just verify extractor is configured
        assert extractor is not None
        assert len(extractor.entity_types) == 4


class TestRAGAssertions:
    """Test RagTestHelper assertions."""

    def test_assert_entities_equal(self):
        """Test entity assertion helper."""
        from omni.rag.entities import Entity

        # Create test entities
        entities = [
            Entity(name="Test1", entity_type="CONCEPT", description="Test", source="test.md"),
            Entity(name="Test2", entity_type="TOOL", description="Test", source="test.md"),
        ]

        # Use helper to verify
        RagTestHelper.assert_entities_equal(
            entities,
            expected_names=["Test1", "Test2"],
            expected_types=["CONCEPT", "TOOL"],
        )

    def test_assert_chunks_valid(self):
        """Test chunk validation assertion."""
        from omni.rag.chunking import Chunk

        chunks = [
            Chunk(text="This is a test sentence." * 5, index=0),
            Chunk(text="Another test sentence." * 5, index=1),
        ]

        RagTestHelper.assert_chunks_valid(
            chunks,
            min_chunk_length=10,
            max_chunk_length=1000,
        )

    def test_assert_no_overlap(self):
        """Test chunk overlap assertion."""
        from omni.rag.chunking import Chunk

        chunks = [
            Chunk(text="First chunk of text." * 10, index=0),
            Chunk(text="Second chunk of text." * 10, index=1),
        ]

        RagTestHelper.assert_no_overlap_between_chunks(chunks)


class TestRAGIntegrationWithExistingFixtures:
    """Test RAG fixtures work with existing test-kit fixtures."""

    def test_rag_with_core_fixtures(self, rag_config_fixture, project_root, skills_root):
        """RAG fixtures work with core fixtures."""
        assert rag_config_fixture is not None
        assert project_root is not None
        assert skills_root is not None

    def test_rag_with_mock_llm_and_chunker(self, mock_llm_for_extraction, rag_sentence_chunker):
        """Mock LLM and chunker work together."""
        assert mock_llm_for_extraction is not None
        assert rag_sentence_chunker is not None
