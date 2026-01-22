"""
test_omni_rag.py - RAG Integration Tests for OmniLoop

Tests the Cognitive Loop with knowledge retrieval augmentation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from omni.agent.core.omni import OmniLoop, OmniLoopConfig
from omni.core.knowledge.librarian import KnowledgeEntry, SearchResult


class TestOmniLoopKnowledgeDetection:
    """Tests for the knowledge intent detection."""

    def test_detects_how_to_queries(self):
        """Should detect 'how to' as knowledge-intensive."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("how to commit changes") is True
        assert loop._needs_knowledge("How do I install the package") is True

    def test_detects_what_is_queries(self):
        """Should detect 'what is' as knowledge-intensive."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("what is the architecture") is True
        assert loop._needs_knowledge("What is OmniLoop") is True

    def test_detects_explain_queries(self):
        """Should detect 'explain' as knowledge-intensive."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("explain the RAG system") is True
        assert loop._needs_knowledge("please explain") is True

    def test_detects_documentation_keywords(self):
        """Should detect docs-related keywords."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("read the documentation") is True
        assert loop._needs_knowledge("best practice for commits") is True
        assert loop._needs_knowledge("give me an example") is True

    def test_detects_question_patterns(self):
        """Should detect question-starting queries."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("Why is this failing") is True
        assert loop._needs_knowledge("Where is the config") is True
        assert loop._needs_knowledge("Which file should I edit") is True

    def test_detects_file_extensions(self):
        """Should detect file extension references."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("check the README.md file") is True
        assert loop._needs_knowledge("see docs/guide.rst") is True

    def test_ignores_simple_commands(self):
        """Should not flag simple commands as knowledge-intensive."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        assert loop._needs_knowledge("commit my changes") is False
        assert loop._needs_knowledge("status") is False
        assert loop._needs_knowledge("run tests") is False


class TestOmniLoopRAGDisabled:
    """Tests for OmniLoop with RAG disabled."""

    def test_rag_disabled_skips_knowledge(self):
        """Should not search when RAG is disabled."""
        config = OmniLoopConfig(enable_rag=False)
        loop = OmniLoop(config)

        # Even if needs_knowledge is True, should skip augmentation
        assert loop.config.enable_rag is False
        assert loop._librarian is None


class TestOmniLoopRAGEnabled:
    """Tests for OmniLoop with RAG enabled (mocked)."""

    @pytest.fixture
    def mock_librarian(self):
        """Create a mock Librarian."""
        librarian = MagicMock()
        librarian.is_ready = True
        librarian.search = AsyncMock(return_value=[])
        return librarian

    @pytest.mark.asyncio
    async def test_augment_context_with_no_results(self, mock_librarian):
        """Should handle empty search results gracefully."""
        config = OmniLoopConfig(enable_rag=True)
        loop = OmniLoop(config)
        loop._librarian = mock_librarian
        loop._librarian_ready = True

        # No results from search
        mock_librarian.search.return_value = []

        result = await loop._augment_context("test query")

        assert result == 0
        mock_librarian.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_augment_context_injects_knowledge(self, mock_librarian):
        """Should inject knowledge entries into context."""
        config = OmniLoopConfig(enable_rag=True, knowledge_limit=3)
        loop = OmniLoop(config)
        loop._librarian = mock_librarian
        loop._librarian_ready = True

        # Mock search results
        entry = KnowledgeEntry(
            id="test_001",
            content="Test content about the system",
            source="docs/architecture.md",
            metadata={},
            score=0.9,
        )
        search_result = SearchResult(entry=entry, score=0.9)
        mock_librarian.search.return_value = [search_result]

        result = await loop._augment_context("what is the architecture")

        assert result == 1
        # Verify context was updated - system prompts should include knowledge
        assert len(loop.context.system_prompts) > 0

    @pytest.mark.asyncio
    async def test_run_calls_augment_for_knowledge_query(self, mock_librarian):
        """run() should call _augment_context for knowledge queries."""
        config = OmniLoopConfig(enable_rag=True)
        loop = OmniLoop(config)
        loop._librarian = mock_librarian
        loop._librarian_ready = True

        # Mock the engine to avoid actual API call
        with patch.object(loop._inference, "complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = {"success": True, "content": "Test response"}

            # Knowledge query
            response = await loop.run("how to use the system")

            # Verify search was called
            mock_librarian.search.assert_called()

    @pytest.mark.asyncio
    async def test_run_skips_augment_for_simple_command(self, mock_librarian):
        """run() should skip _augment_context for simple commands."""
        config = OmniLoopConfig(enable_rag=True)
        loop = OmniLoop(config)
        loop._librarian = mock_librarian
        loop._librarian_ready = True

        # Mock the engine
        with patch.object(loop._inference, "complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = {"success": True, "content": "Test response"}

            # Simple command (not knowledge-intensive)
            response = await loop.run("commit my changes")

            # Search should NOT be called
            mock_librarian.search.assert_not_called()


class TestOmniLoopConfig:
    """Tests for OmniLoopConfig RAG settings."""

    def test_default_config_enables_rag(self):
        """RAG should be enabled by default."""
        config = OmniLoopConfig()
        assert config.enable_rag is True
        assert config.knowledge_limit == 3
        assert config.knowledge_threshold == 0.5

    def test_config_can_disable_rag(self):
        """RAG can be disabled via config."""
        config = OmniLoopConfig(enable_rag=False)
        assert config.enable_rag is False

    def test_config_custom_limits(self):
        """Custom knowledge limits are respected."""
        config = OmniLoopConfig(knowledge_limit=5, knowledge_threshold=0.7)
        assert config.knowledge_limit == 5
        assert config.knowledge_threshold == 0.7


class TestOmniLoopIntegration:
    """Integration-style tests for OmniLoop with mocked dependencies."""

    @pytest.fixture
    def setup_loop_with_mocks(self, tmp_path: Path):
        """Create OmniLoop with all dependencies mocked."""
        config = OmniLoopConfig(enable_rag=True)
        loop = OmniLoop(config)

        # Mock the librarian
        mock_librarian = MagicMock()
        mock_librarian.is_ready = True
        mock_librarian.search = AsyncMock(return_value=[])
        loop._librarian = mock_librarian
        loop._librarian_ready = True

        # Mock the engine
        loop._inference.complete = AsyncMock(
            return_value={"success": True, "content": "Test response"}
        )

        return loop

    @pytest.mark.asyncio
    async def test_full_rag_flow_knowledge_query(self, setup_loop_with_mocks):
        """Test complete RAG flow: detect -> retrieve -> augment -> respond."""
        loop = setup_loop_with_mocks

        # Setup mock to return knowledge
        entry = KnowledgeEntry(
            id="doc_001",
            content="The system uses a Trinity Architecture with Foundation, Core, and Agent layers.",
            source="docs/architecture.md",
            metadata={},
            score=0.95,
        )
        search_result = SearchResult(entry=entry, score=0.95)
        loop._librarian.search.return_value = [search_result]

        # Execute knowledge query
        response = await loop.run("explain the architecture")

        # Verify response was generated
        assert response == "Test response"
        # Verify knowledge was searched
        loop._librarian.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_simple_command_skips_rag(self, setup_loop_with_mocks):
        """Simple commands should skip the RAG flow."""
        loop = setup_loop_with_mocks

        # Execute simple command
        response = await loop.run("run tests")

        # Verify RAG was NOT triggered
        loop._librarian.search.assert_not_called()
        # But engine was still called
        loop._inference.complete.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
