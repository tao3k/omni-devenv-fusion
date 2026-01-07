"""
src/agent/tests/test_phase16_neural_bridge.py
Phase 16: Neural Bridge Tests - Active RAG for Agents

Tests the Active RAG feature where agents retrieve relevant project knowledge
from VectorStore before execution.

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_phase16_neural_bridge.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent
from agent.core.vector_store import SearchResult


class TestActiveRAG:
    """Test Phase 16 Active RAG (Neural Bridge)."""

    @pytest.mark.asyncio
    async def test_coder_rag_injects_knowledge(self):
        """Verify Coder retrieves and injects relevant knowledge."""
        agent = CoderAgent()

        # Mock search results with high similarity (low distance)
        mock_results = [
            SearchResult(
                content="Security Standard: Always hash passwords with bcrypt before logging.",
                metadata={"source_file": "standards/security.md", "domain": "standards"},
                distance=0.15,  # High similarity
                id="sec-001",
            ),
            SearchResult(
                content="Python Standard: Use Pydantic for type validation.",
                metadata={"source_file": "lang-python.md", "domain": "standards"},
                distance=0.2,  # High similarity
                id="py-001",
            ),
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Fix SQL injection vulnerability in login")

            # Verify knowledge was injected
            assert "RELEVANT PROJECT KNOWLEDGE" in ctx.system_prompt
            assert "bcrypt" in ctx.system_prompt
            assert "Pydantic" in ctx.system_prompt
            assert "standards/security.md" in ctx.system_prompt

    @pytest.mark.asyncio
    async def test_coder_rag_no_results(self):
        """Verify Coder works when no knowledge is found."""
        agent = CoderAgent()

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=[])

            ctx = await agent.prepare_context("Some random task")

            # Should not have knowledge section when empty
            assert "RELEVANT PROJECT KNOWLEDGE" not in ctx.system_prompt
            assert ctx.knowledge_context == ""

    @pytest.mark.asyncio
    async def test_coder_rag_filters_low_similarity(self):
        """Verify RAG filters out low-similarity results."""
        agent = CoderAgent()

        # Mock with low similarity (high distance)
        mock_results = [
            SearchResult(
                content="Unrelated document about something else...",
                metadata={"source_file": "unrelated.md"},
                distance=0.8,  # Low similarity - should be filtered
                id="unrelated",
            )
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Fix bug")

            # Should not include low-similarity result
            assert "RELEVANT PROJECT KNOWLEDGE" not in ctx.system_prompt
            assert ctx.knowledge_context == ""

    @pytest.mark.asyncio
    async def test_reviewer_skips_rag(self):
        """Verify Reviewer doesn't use RAG (disabled explicitly)."""
        agent = ReviewerAgent()

        # Mock that search is NOT called
        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock()

            ctx = await agent.prepare_context("Review this PR")

            # Knowledge section should not appear for Reviewer
            assert "RELEVANT PROJECT KNOWLEDGE" not in ctx.system_prompt
            # Verify search was NOT called
            mock_vm.return_value.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_context_includes_knowledge(self):
        """Verify AgentContext has knowledge_context field."""
        agent = CoderAgent()

        mock_results = [
            SearchResult(
                content="Test knowledge.",
                metadata={"source_file": "test.md"},
                distance=0.1,
                id="test-001",
            )
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Test task")

            # Verify knowledge_context field is populated
            assert hasattr(ctx, "knowledge_context")
            assert ctx.knowledge_context != ""
            assert "Test knowledge" in ctx.knowledge_context

    @pytest.mark.asyncio
    async def test_rag_respects_max_results(self):
        """Verify RAG respects n_results parameter."""
        agent = CoderAgent()

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=[])

            await agent._retrieve_relevant_knowledge("test query", n_results=5)

            # Verify search was called with correct n_results
            mock_vm.return_value.search.assert_called_once_with("test query", n_results=5)

    @pytest.mark.asyncio
    async def test_rag_content_truncation(self):
        """Verify RAG truncates long content."""
        agent = CoderAgent()

        # Create content longer than 800 chars
        long_content = "A" * 1000

        mock_results = [
            SearchResult(
                content=long_content,
                metadata={"source_file": "long.md"},
                distance=0.1,
                id="long-001",
            )
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Test task")

            # Content should be truncated (800 chars + "...")
            assert len(ctx.knowledge_context) < 1200  # Allow for formatting overhead


class TestKnowledgeContextFormat:
    """Test the format of injected knowledge context."""

    @pytest.mark.asyncio
    async def test_knowledge_section_format(self):
        """Verify knowledge is formatted correctly with header."""
        agent = CoderAgent()

        mock_results = [
            SearchResult(
                content="Test content.",
                metadata={"source_file": "test.md"},
                distance=0.1,
                id="test-001",
            )
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Test")

            # Verify section header format
            assert "## 🧠 RELEVANT PROJECT KNOWLEDGE" in ctx.system_prompt
            assert "- **test.md**:" in ctx.system_prompt

    @pytest.mark.asyncio
    async def test_knowledge_source_file_in_metadata(self):
        """Verify source_file is used for display."""
        agent = CoderAgent()

        mock_results = [
            SearchResult(
                content="Content.",
                metadata={"source_file": "path/to/my_file.md", "title": "My Title"},
                distance=0.1,
                id="test-001",
            )
        ]

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            mock_vm.return_value.search = AsyncMock(return_value=mock_results)

            ctx = await agent.prepare_context("Test")

            # Should use source_file, not title
            assert "path/to/my_file.md" in ctx.system_prompt


class TestRAGErrorHandling:
    """Test RAG error handling."""

    @pytest.mark.asyncio
    async def test_rag_failure_does_not_crash(self):
        """Verify RAG failure doesn't block agent execution."""
        agent = CoderAgent()

        with patch("agent.core.agents.base.get_vector_memory") as mock_vm:
            # Simulate VectorStore failure
            mock_vm.return_value.search = AsyncMock(side_effect=Exception("Connection failed"))

            # Should not raise, should continue with empty knowledge
            ctx = await agent.prepare_context("Test task")

            assert ctx.system_prompt != ""  # Should still have a prompt
            assert "RELEVANT PROJECT KNOWLEDGE" not in ctx.system_prompt
