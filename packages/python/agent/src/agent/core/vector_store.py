# agent/core/vector_store.py
"""
Vector Memory Store - ChromaDB-based RAG for Project Knowledge

Provides semantic search over project documentation and code.

Philosophy:
- Fast semantic retrieval for contextual answers
- Persistent storage across sessions
- Auto-ingestion of key knowledge bases

Usage:
    from agent.core.vector_store import get_vector_memory, ingest_knowledge

    # Query the knowledge base
    results = await get_vector_memory().search("git workflow rules", n_results=5)

    # Ingest new knowledge
    await ingest_knowledge(
        documents=[
            "Git workflow requires smart_commit for all commits.",
            "Code reviews must pass before merging."
        ],
        ids=["doc1", "doc2"],
        collection="workflow_rules"
    )
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# In uv workspace, 'common' package is available directly
from common.mcp_core.gitops import get_project_root

import chromadb
from chromadb.config import Settings
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result from vector store."""
    content: str
    metadata: Dict[str, Any]
    distance: float
    id: str


class VectorMemory:
    """
    ChromaDB-based Vector Memory for RAG.

    Stores and retrieves semantic embeddings for:
    - Project documentation
    - Workflow rules
    - Architectural decisions
    - Code patterns and examples

    Features:
    - Persistent storage in .chromadb/
    - Multiple collections for different knowledge domains
    - Configurable similarity threshold
    """

    _instance: Optional["VectorMemory"] = None
    _client: chromadb.PersistentClient | None = None

    def __new__(cls) -> "VectorMemory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Create ChromaDB client with persistent storage
        # Following prj-spec: store in .cache/ at git toplevel
        project_root = get_project_root()  # Uses: git rev-parse --show-toplevel
        cache_path = project_root / ".cache" / "chromadb"
        cache_path.mkdir(parents=True, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(
                path=str(cache_path),
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info("Vector memory initialized", db_path=str(cache_path))
        except Exception as e:
            logger.error("Failed to initialize vector memory", error=str(e))
            self._client = None

        self._initialized = True
        self._default_collection = "project_knowledge"

    @property
    def client(self) -> chromadb.PersistentClient | None:
        """Get the ChromaDB client."""
        return self._client

    def _get_or_create_collection(
        self,
        name: str | None = None
    ) -> chromadb.Collection | None:
        """Get or create a collection by name."""
        if not self._client:
            logger.warning("Vector memory not available")
            return None

        collection_name = name or self._default_collection

        try:
            return self._client.get_or_create_collection(
                name=collection_name,
                metadata={"description": f"Project knowledge base: {collection_name}"}
            )
        except Exception as e:
            logger.error("Failed to get collection", collection=collection_name, error=str(e))
            return None

    async def search(
        self,
        query: str,
        n_results: int = 5,
        collection: str | None = None,
        where_filter: Dict[str, str] | None = None
    ) -> list[SearchResult]:
        """
        Search the vector store for similar documents.

        Args:
            query: The search query (will be embedded)
            n_results: Number of results to return
            collection: Optional collection name (defaults to project_knowledge)
            where_filter: Optional metadata filter

        Returns:
            List of SearchResult objects sorted by similarity
        """
        if not self._client:
            logger.warning("Vector memory not available for search")
            return []

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return []

        try:
            # Perform similarity search
            results = chroma_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )

            if not results or not results.get("documents"):
                return []

            # Convert to SearchResult objects
            search_results: list[SearchResult] = []
            documents = results["documents"][0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]

            for i, doc in enumerate(documents):
                search_results.append(SearchResult(
                    content=doc,
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    distance=distances[i] if i < len(distances) else 0.0,
                    id=ids[i] if i < len(ids) else f"result_{i}"
                ))

            logger.info(
                "Vector search completed",
                query=query[:50],
                results=len(search_results)
            )

            return search_results

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    async def add(
        self,
        documents: list[str],
        ids: list[str],
        collection: str | None = None,
        metadatas: list[Dict[str, Any]] | None = None
    ) -> bool:
        """
        Add documents to the vector store.

        Args:
            documents: List of document texts to add
            ids: Unique identifiers for each document
            collection: Optional collection name
            metadatas: Optional metadata for each document

        Returns:
            True if successful
        """
        if not self._client:
            logger.warning("Vector memory not available for add")
            return False

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return False

        try:
            chroma_collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )

            logger.info(
                "Documents added to vector store",
                count=len(documents),
                collection=collection or self._default_collection
            )
            return True

        except Exception as e:
            logger.error("Failed to add documents", error=str(e))
            return False

    async def delete(
        self,
        ids: list[str],
        collection: str | None = None
    ) -> bool:
        """Delete documents by IDs."""
        if not self._client:
            return False

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return False

        try:
            chroma_collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error("Failed to delete documents", error=str(e))
            return False

    async def count(self, collection: str | None = None) -> int:
        """Get the number of documents in a collection."""
        if not self._client:
            return 0

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return 0

        return chroma_collection.count()

    async def list_collections(self) -> list[str]:
        """List all collection names."""
        if not self._client:
            return []

        try:
            collections = self._client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error("Failed to list collections", error=str(e))
            return []


# Singleton accessor
def get_vector_memory() -> VectorMemory:
    """Get the vector memory singleton instance."""
    return VectorMemory()


# Convenience functions
async def search_knowledge(
    query: str,
    n_results: int = 5,
    collection: str | None = None
) -> list[SearchResult]:
    """Search project knowledge base."""
    return await get_vector_memory().search(query, n_results, collection)


async def ingest_knowledge(
    documents: list[str],
    ids: list[str],
    collection: str | None = None,
    metadatas: list[Dict[str, Any]] | None = None
) -> bool:
    """Ingest documents into knowledge base."""
    return await get_vector_memory().add(documents, ids, collection, metadatas)


# Auto-ingestion for common project knowledge
async def bootstrap_knowledge_base() -> None:
    """
    Bootstrap the knowledge base with essential project documentation.

    Should be called on first run to populate with:
    - Git workflow rules
    - Coding standards
    - Architecture decisions
    - Preloaded skill prompts.md (git, knowledge, writer, etc.)
    """
    from common.mcp_core.gitops import get_project_root

    project_root = get_project_root()

    # Default knowledge to ingest
    bootstrap_docs = [
        {
            "id": "git-workflow-001",
            "content": """
            Git Workflow Protocol:
            - All commits MUST use git_commit tool
            - Direct git commit is PROHIBITED
            - Commit message must follow conventional commits format
            - Authorization Protocol: Show analysis → Wait "yes" → Execute
            """,
            "metadata": {"domain": "git", "priority": "high"}
        },
        {
            "id": "tri-mcp-001",
            "content": """
            Tri-MCP Architecture:
            - orchestrator (The Brain): Planning, routing, reviewing
            - executor (The Hands): Git, testing, shell operations
            - coder (File Operations): Read/Write/Search files

            Each MCP server has a specific role and tools.
            """,
            "metadata": {"domain": "architecture", "priority": "high"}
        },
        {
            "id": "coding-standards-001",
            "content": """
            Coding Standards:
            - Follow agent/standards/lang-*.md for language-specific rules
            - Use Pydantic for type validation
            - Use structlog for logging
            - Write docstrings for all public functions
            """,
            "metadata": {"domain": "standards", "priority": "medium"}
        }
    ]

    vm = get_vector_memory()

    for doc in bootstrap_docs:
        await vm.add(
            documents=[doc["content"].strip()],
            ids=[doc["id"]],
            metadatas=[doc["metadata"]]
        )

    # Also ingest preloaded skill prompts.md files
    await ingest_preloaded_skill_prompts()

    logger.info("Knowledge base bootstrapped", docs=len(bootstrap_docs))


async def ingest_preloaded_skill_prompts() -> None:
    """
    Ingest prompts.md from all preloaded skills into the knowledge base.

    This ensures that when Claude processes user requests, it has access to
    the skill rules even if not explicitly loading the skill.

    The following skills are preloaded and their prompts.md will be ingested:
    - git: Commit authorization protocol
    - knowledge: Project rules and scopes
    - writer: Writing quality standards
    - filesystem: Safe file operations
    - terminal: Command execution rules
    - testing_protocol: Testing workflow
    """
    from agent.core.skill_registry import get_skill_registry

    project_root = get_project_root()
    registry = get_skill_registry()
    preload_skills = registry.get_preload_skills()

    if not preload_skills:
        logger.info("No preload skills configured")
        return

    vm = get_vector_memory()
    skills_ingested = 0

    for skill_name in preload_skills:
        prompts_path = project_root / "agent" / "skills" / skill_name / "prompts.md"

        if not prompts_path.exists():
            logger.debug(f"Skill {skill_name} has no prompts.md")
            continue

        try:
            content = prompts_path.read_text(encoding="utf-8")

            # Ingest with skill name as domain for filtering
            success = await vm.add(
                documents=[content],
                ids=[f"skill-{skill_name}-prompts"],
                metadatas=[{
                    "domain": "skill",
                    "skill": skill_name,
                    "priority": "high",
                    "source_file": str(prompts_path)
                }]
            )

            if success:
                skills_ingested += 1
                logger.info(f"Ingested prompts.md for skill: {skill_name}")

        except Exception as e:
            logger.error(f"Failed to ingest prompts.md for skill {skill_name}: {e}")

    logger.info(f"Preloaded skill prompts ingested: {skills_ingested}/{len(preload_skills)}")


__all__ = [
    "VectorMemory",
    "get_vector_memory",
    "SearchResult",
    "search_knowledge",
    "ingest_knowledge",
    "bootstrap_knowledge_base",
    "ingest_preloaded_skill_prompts",
]
