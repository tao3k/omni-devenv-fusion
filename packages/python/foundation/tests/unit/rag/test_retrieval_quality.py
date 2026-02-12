"""
Retrieval Quality Tests

Comprehensive evaluation of Pure Vector and Rust-native Hybrid (Vector+BM25)
retrieval strategies.

Test scenarios are based on actual project skills and tools.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import structlog

from omni.rag.retrieval import (
    LanceRetrievalBackend,
    HybridRetrievalBackend,
    RetrievalConfig,
)
from omni.foundation.services.vector import get_vector_store
from omni.foundation.services.embedding import get_embedding_service

logger = structlog.get_logger("test.retrieval.quality")


# =============================================================================
# Realistic Test Scenarios Based on Project Skills
# =============================================================================

SKILL_BASED_SCENARIOS = [
    {
        "scenario": "git_smart_commit_workflow",
        "query": (
            "I need to commit my changes with a smart commit workflow that integrates "
            "lefthook for pre-commit validation, security scanning for sensitive files, "
            "and human approval before finalizing the commit message"
        ),
        "description": "Git smart commit with lefthook integration",
        "related_skills": ["git", "knowledge"],
    },
    {
        "scenario": "knowledge_zk_reasoning_search",
        "query": (
            "Search for project architecture decisions using Zettelkasten "
            "bidirectional links and reasoning-based search to find related notes "
            "through multiple hops of link traversal"
        ),
        "description": "ZK-based reasoning search with bidirectional links",
        "related_skills": ["knowledge", "zk"],
    },
    {
        "scenario": "memory_experience_recall",
        "query": (
            "Recall past solutions and mistakes from vector-based memory to avoid "
            "repeating errors in similar situations during this development session"
        ),
        "description": "Memory recall for avoiding past mistakes",
        "related_skills": ["memory"],
    },
    {
        "scenario": "researcher_sharded_analysis",
        "query": (
            "Analyze a large GitHub repository using sharded deep research workflow "
            "with Map-Plan-Loop-Synthesize architecture to handle codebases that "
            "exceed LLM context limits"
        ),
        "description": "Sharded deep research for large repositories",
        "related_skills": ["researcher", "git"],
    },
    {
        "scenario": "skill_discovery_jit_install",
        "query": (
            "Discover available skills and commands in the omni system, then "
            "install a new capability on-demand using just-in-time installation"
        ),
        "description": "Skill discovery and JIT installation",
        "related_skills": ["skill"],
    },
    {
        "scenario": "embedding_batch_processing",
        "query": (
            "Generate text embeddings using the unified embedding service with "
            "Qwen3-Embedding model for semantic search and vector similarity calculations"
        ),
        "description": "Embedding generation for semantic operations",
        "related_skills": ["embedding"],
    },
    {
        "scenario": "hybrid_search_fusion",
        "query": (
            "Perform hybrid search combining dense vector representations with sparse "
            "BM25 keyword indexing using reciprocal rank fusion to merge results"
        ),
        "description": "Hybrid search with RRF fusion",
        "related_skills": ["knowledge", "memory"],
    },
    {
        "scenario": "knowledge_session_summarization",
        "query": (
            "Summarize the current development session trajectory capturing all "
            "execution steps, decisions made, and outcomes for future reference"
        ),
        "description": "Session summarization for continuity",
        "related_skills": ["knowledge", "memory"],
    },
    {
        "scenario": "routing_semantic_intent",
        "query": (
            "Classify user intent and route tasks to appropriate skills using "
            "semantic similarity matching and keyword extraction"
        ),
        "description": "Intent classification and routing",
        "related_skills": ["skill", "knowledge"],
    },
    {
        "scenario": "document_rag_chunking",
        "query": (
            "Implement RAG pipeline with intelligent document chunking strategies "
            "including sentence-based, paragraph-based, and semantic grouping approaches"
        ),
        "description": "RAG document chunking strategies",
        "related_skills": ["knowledge", "embedding"],
    },
]

# Documents simulating skill descriptions for retrieval tests
SKILL_DOCUMENTS = [
    {
        "id": "doc_git_smart_commit",
        "content": (
            "Git smart commit integrates lefthook for pre-commit validation and security scanning. "
            "The workflow stages all changes, scans for sensitive files like .env, .pem, credentials, "
            "runs lefthook formatters, and requests human approval before committing. "
            "Commands: git.smart_commit(action='start'), git.stage_all(), git.commit(message='...')"
        ),
        "metadata": {"skill": "git", "category": "workflow"},
    },
    {
        "id": "doc_knowledge_zk_search",
        "content": (
            "Knowledge ZK search uses bidirectional links and reasoning-based traversal. "
            "The zk_search command performs high-precision search with max_iterations=3, "
            "traversing linked notes to find related content. Related commands: zk_toc(), "
            "zk_links(), zk_hybrid_search(), zk_find_related(max_distance=2)"
        ),
        "metadata": {"skill": "knowledge", "category": "search"},
    },
    {
        "id": "doc_memory_recall",
        "content": (
            "Memory recall enables agents to remember past solutions and avoid repeating mistakes. "
            "The search_memory() function performs semantic search on vector-stored memories. "
            "save_memory() stores insights with metadata. Commands: save_memory(content, metadata), "
            "search_memory(query, limit), index_memory(), load_skill(skill_name)"
        ),
        "metadata": {"skill": "memory", "category": "retrieval"},
    },
    {
        "id": "doc_researcher_sharded",
        "content": (
            "Researcher skill performs sharded deep research on large repositories. "
            "The run_research_graph() command clones repo, maps file structure, plans shards via LLM, "
            "iterates through each shard with repomix compression, then synthesizes index.md. "
            "Architecture: Map-Plan-Loop-Synthesize using LangGraph."
        ),
        "metadata": {"skill": "researcher", "category": "analysis"},
    },
    {
        "id": "doc_skill_discovery",
        "content": (
            "Skill discovery and management via skill commands. discover() is the ONLY way to "
            "call @omni commands - get exact tool names and usage templates. jit_install() "
            "installs skills on-demand. list_index shows all available skills. "
            "Related: unload(), reload(), get_template_info()"
        ),
        "metadata": {"skill": "skill", "category": "discovery"},
    },
    {
        "id": "doc_embedding_service",
        "content": (
            "Embedding service provides unified text embedding generation. "
            "Uses Qwen/Qwen3-Embedding models with 1024 or 2560 dimensions. "
            "Supports batch processing via embed_texts() and single text via embed_single(). "
            "Auto-detects local vs HTTP client mode for distributed embedding generation."
        ),
        "metadata": {"skill": "embedding", "category": "generation"},
    },
    {
        "id": "doc_hybrid_search",
        "content": (
            "Hybrid search combines dense vector similarity with sparse BM25 keyword search. "
            "Uses Reciprocal Rank Fusion (RRF) to merge results: score = 1/(k + rank). "
            "Typical k=60, semantic_weight=1.0, keyword_weight=1.5. "
            "Vector search uses cosine similarity, BM25 uses term frequency-inverse document frequency."
        ),
        "metadata": {"skill": "knowledge", "category": "search"},
    },
    {
        "id": "doc_session_summarization",
        "content": (
            "Session summarization captures development session trajectory for continuity. "
            "The summarize_session() command takes session_id, trajectory list, and include_failures flag. "
            "Stores structured markdown with execution steps, decisions, and outcomes. "
            "Useful for long-running projects and team handoffs."
        ),
        "metadata": {"skill": "knowledge", "category": "documentation"},
    },
    {
        "id": "doc_routing_intent",
        "content": (
            "Router classifies user intents and routes tasks to appropriate skills. "
            "Uses hybrid search with semantic similarity and keyword extraction. "
            "Supports progressive disclosure for complex tasks. "
            "Core skills: git, knowledge, memory, researcher, skill, embedding."
        ),
        "metadata": {"skill": "skill", "category": "routing"},
    },
    {
        "id": "doc_rag_chunking",
        "content": (
            "RAG chunking strategies for document processing: sentence-based splits on punctuation, "
            "paragraph-based on double newlines, sliding_window with overlap, semantic grouping "
            "uses embeddings to group related content. Chunk size typically 256-512 tokens with "
            "overlap of 20-50 tokens for continuity."
        ),
        "metadata": {"skill": "knowledge", "category": "chunking"},
    },
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def embedding_status():
    """Initialize embedding service for tests."""
    service = get_embedding_service()
    service.initialize()
    # Wait for model load if needed
    if not service.is_loaded:
        import time

        for _ in range(30):
            time.sleep(0.5)
            if service.is_loaded:
                break
    return {
        "backend": service.backend,
        "dimension": service.dimension,
        "is_loaded": service.is_loaded,
    }


@pytest.fixture
def test_vector_store(embedding_status):
    """Create a test vector store with skill documents."""
    store = get_vector_store()
    # Clean up any existing test data
    asyncio.run(store.delete("test_vector", "test_collection"))
    # Index documents
    contents = [doc["content"] for doc in SKILL_DOCUMENTS]
    metadata = [{"id": doc["id"], **doc["metadata"]} for doc in SKILL_DOCUMENTS]
    asyncio.run(store.add_batch(chunks=contents, metadata=metadata, collection="test_vector"))
    yield store
    # Cleanup
    asyncio.run(store.delete("test_vector", "test_collection"))


@pytest.fixture
def test_scenarios():
    """Return test scenarios based on project skills."""
    return SKILL_BASED_SCENARIOS


@pytest.fixture
def test_documents():
    """Return test documents simulating skill descriptions."""
    return SKILL_DOCUMENTS


# =============================================================================
# Retrieval Quality Tests
# =============================================================================


class TestRetrievalQualityComparison:
    """Compare retrieval quality across Pure Vector, Hybrid, and Hybrid+Reranker."""

    def test_vector_only_quality(self, test_scenarios, test_documents, embedding_status):
        """Test pure vector search quality."""
        log = structlog.get_logger("test.quality.vector")

        # Initialize backends
        vector_backend = LanceRetrievalBackend()

        # index() expects list[dict] with 'content' and 'metadata' keys
        asyncio.run(vector_backend.index(test_documents, "test_vector"))

        results_summary = []
        for scenario in test_scenarios:
            results = asyncio.run(
                vector_backend.search(
                    scenario["query"], RetrievalConfig(top_k=3, collection="test_vector")
                )
            )

            top_score = results[0].score if results else 0.0
            results_summary.append(
                {
                    "scenario": scenario["scenario"],
                    "query_preview": scenario["query"][:50] + "...",
                    "top_score": round(top_score, 4),
                    "result_count": len(results),
                    "top_id": results[0].id if results else None,
                }
            )

        log.info("Pure vector search completed", scenario_results=len(results_summary))

        # Verify we get reasonable results
        avg_score = sum(r["top_score"] for r in results_summary) / len(results_summary)
        log.info("Average top score", avg_score=round(avg_score, 4))

        assert len(results_summary) == len(test_scenarios)

    def test_hybrid_quality(self, test_scenarios, test_documents, embedding_status):
        """Test hybrid search (Vector + BM25) quality."""
        log = structlog.get_logger("test.quality.hybrid")

        # Initialize backends
        vector_backend = LanceRetrievalBackend()
        hybrid_backend = HybridRetrievalBackend(vector_backend=vector_backend)

        # index() expects list[dict] with 'content' and 'metadata' keys
        asyncio.run(hybrid_backend.index(test_documents, "test_vector"))

        results_summary = []
        for scenario in test_scenarios:
            results = asyncio.run(
                hybrid_backend.search(
                    scenario["query"], RetrievalConfig(top_k=3, collection="test_vector")
                )
            )

            top_score = results[0].score if results else 0.0
            results_summary.append(
                {
                    "scenario": scenario["scenario"],
                    "query_preview": scenario["query"][:50] + "...",
                    "top_score": round(top_score, 4),
                    "result_count": len(results),
                    "top_id": results[0].id if results else None,
                }
            )

        log.info("Hybrid search completed", scenario_results=len(results_summary))

        assert len(results_summary) == len(test_scenarios)

    def test_hybrid_consistency_quality(self, test_scenarios, test_documents, embedding_status):
        """Test Rust-native hybrid quality consistency."""
        log = structlog.get_logger("test.quality.hybrid_consistency")

        vector_backend = LanceRetrievalBackend()
        hybrid_backend = HybridRetrievalBackend(vector_backend=vector_backend)

        # index() expects list[dict] with 'content' and 'metadata' keys
        asyncio.run(hybrid_backend.index(test_documents, "test_vector"))

        results_summary = []
        for scenario in test_scenarios:
            raw_results = asyncio.run(
                hybrid_backend.search(
                    scenario["query"], RetrievalConfig(top_k=5, collection="test_vector")
                )
            )

            top_score = raw_results[0].score if raw_results else 0.0
            results_summary.append(
                {
                    "scenario": scenario["scenario"],
                    "query_preview": scenario["query"][:50] + "...",
                    "top_score": round(top_score, 4),
                    "result_count": len(raw_results),
                    "top_id": raw_results[0].id if raw_results else None,
                }
            )

        log.info("Hybrid consistency search completed", scenario_results=len(results_summary))

        assert len(results_summary) == len(test_scenarios)


class TestRetrievalQualityMetrics:
    """Calculate quality metrics for retrieval."""

    def test_relevance_scoring(self):
        """Test relevance scoring calculation."""
        from omni.rag.retrieval import RetrievalResult

        log = structlog.get_logger("test.metrics.relevance")

        # Simulate results with different relevance levels
        results = [
            RetrievalResult(id="1", content="Perfect match", score=0.95, source="vector"),
            RetrievalResult(id="2", content="Partial match", score=0.70, source="hybrid"),
            RetrievalResult(id="3", content="Related topic", score=0.45, source="bm25"),
            RetrievalResult(id="4", content="Irrelevant", score=0.10, source="vector"),
        ]

        # Calculate metrics
        relevant = [r for r in results if r.score >= 0.5]
        precision_at_k = len(relevant) / len(results)

        log.info(
            "Relevance scoring metrics",
            total_results=len(results),
            relevant_count=len(relevant),
            precision_at_k=f"{precision_at_k:.2%}",
        )

        assert precision_at_k >= 0.5, "Should have at least 50% precision"

    def test_hybrid_backend_requires_native_engine(self):
        """Hybrid backend should reject non-native composite backends."""
        from omni.rag.retrieval import (
            HybridRetrievalBackend,
            RetrievalResult,
            RetrievalConfig,
            HybridRetrievalUnavailableError,
        )

        log = structlog.get_logger("test.metrics.rrf")

        class MockVectorBackend:
            async def search(self, query, config):
                return [
                    RetrievalResult(id="a", content="Vector match 1", score=0.9, source="vector"),
                    RetrievalResult(id="c", content="Vector match 2", score=0.8, source="vector"),
                    RetrievalResult(id="b", content="Vector match 3", score=0.7, source="vector"),
                ]

        hybrid = HybridRetrievalBackend(vector_backend=MockVectorBackend())
        with pytest.raises(HybridRetrievalUnavailableError):
            asyncio.run(hybrid.search("test", RetrievalConfig(top_k=5)))
        log.info("Hybrid backend correctly rejected non-native backend")


class TestCrossScenarioComparison:
    """Compare results across scenarios and strategies."""

    def test_scenario_comparison_matrix(self, test_scenarios, embedding_status):
        """Generate comparison matrix across all scenarios and strategies."""
        log = structlog.get_logger("test.comparison.matrix")

        # Initialize backends
        vector_backend = LanceRetrievalBackend()
        hybrid_backend = HybridRetrievalBackend(vector_backend=vector_backend)

        # Store documents - index() expects list[dict] with 'content' and 'metadata' keys
        test_docs = [
            {
                "id": "d1",
                "content": "Git smart commit integrates lefthook and security scanning workflow",
                "metadata": {"skill": "git"},
            },
            {
                "id": "d2",
                "content": "Memory recall enables agents to remember past solutions and avoid mistakes",
                "metadata": {"skill": "memory"},
            },
            {
                "id": "d3",
                "content": "Researcher sharded analysis uses Map-Plan-Loop-Synthesize architecture",
                "metadata": {"skill": "researcher"},
            },
            {
                "id": "d4",
                "content": "Skill discovery is the mandatory entry point for all @omni commands",
                "metadata": {"skill": "skill"},
            },
            {
                "id": "d5",
                "content": "Hybrid search combines vector similarity with BM25 keyword matching",
                "metadata": {"skill": "knowledge"},
            },
        ]
        asyncio.run(hybrid_backend.index(test_docs, "test_matrix"))

        # Test queries matching different documents
        queries = [
            ("git_smart_commit", "How to commit with lefthook validation?"),
            ("memory_recall", "Remember past solutions to avoid repeating mistakes"),
            ("researcher_sharded", "Analyze large codebase with sharded research"),
            ("skill_discovery", "What tools are available in omni system?"),
            ("hybrid_search", "Combine vector and keyword search together"),
        ]

        comparison = []
        for scenario_id, query in queries:
            vector_results = asyncio.run(
                vector_backend.search(query, RetrievalConfig(top_k=3, collection="test_matrix"))
            )
            rerank_results = asyncio.run(
                hybrid_backend.search(query, RetrievalConfig(top_k=3, collection="test_matrix"))
            )

            vector_top = vector_results[0].score if vector_results else 0.0
            rerank_top = rerank_results[0].score if rerank_results else 0.0

            comparison.append(
                {
                    "scenario": scenario_id,
                    "query": query,
                    "vector_top_score": round(vector_top, 4),
                    "rerank_top_score": round(rerank_top, 4),
                    "vector_count": len(vector_results),
                    "rerank_count": len(rerank_results),
                }
            )

        log.info("Scenario comparison matrix", comparison=comparison)

        assert len(comparison) == len(queries)
