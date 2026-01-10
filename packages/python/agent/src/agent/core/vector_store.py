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
from common.gitops import get_project_root

# Lazy imports to avoid slow module loading
_cached_chromadb: Any = None
_cached_settings: Any = None
_cached_logger: Any = None


def _get_chromadb() -> Any:
    """Get chromadb lazily to avoid slow import."""
    global _cached_chromadb
    if _cached_chromadb is None:
        import chromadb

        _cached_chromadb = chromadb
    return _cached_chromadb


def _get_chroma_settings() -> Any:
    """Get chromadb Settings lazily."""
    global _cached_settings
    if _cached_settings is None:
        from chromadb.config import Settings

        _cached_settings = Settings
    return _cached_settings


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


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
    _client: Any = None  # chromadb.PersistentClient, lazy loaded
    _cache_path: Optional[Path] = None

    def __new__(cls) -> "VectorMemory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._client = None
            cls._instance._cache_path = None
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Defer ChromaDB client creation - only compute path
        project_root = get_project_root()
        self._cache_path = project_root / ".cache" / "chromadb"
        self._cache_path.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        self._default_collection = "project_knowledge"

    def _ensure_client(self) -> Any:
        """Lazily create ChromaDB client only when needed."""
        if self._client is None and self._cache_path is not None:
            try:
                chromadb = _get_chromadb()
                Settings = _get_chroma_settings()
                self._client = chromadb.PersistentClient(
                    path=str(self._cache_path), settings=Settings(anonymized_telemetry=False)
                )
                _get_logger().info("Vector memory initialized", db_path=str(self._cache_path))
            except Exception as e:
                _get_logger().error("Failed to initialize vector memory", error=str(e))
                self._client = None
        return self._client

    @property
    def client(self) -> Any:  # chromadb.PersistentClient | None
        """Get the ChromaDB client (lazy)."""
        return self._ensure_client()

    def _get_or_create_collection(
        self, name: str | None = None
    ) -> Any:  # chromadb.Collection | None
        """Get or create a collection by name."""
        client = self._ensure_client()
        if not client:
            _get_logger().warning("Vector memory not available")
            return None

        collection_name = name or self._default_collection

        try:
            return client.get_or_create_collection(
                name=collection_name,
                metadata={"description": f"Project knowledge base: {collection_name}"},
            )
        except Exception as e:
            _get_logger().error(
                "Failed to get collection", collection=collection_name, error=str(e)
            )
            return None

    async def search(
        self,
        query: str,
        n_results: int = 5,
        collection: str | None = None,
        where_filter: Dict[str, str] | None = None,
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
        client = self._ensure_client()
        if not client:
            _get_logger().warning("Vector memory not available for search")
            return []

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return []

        try:
            # Perform similarity search
            results = chroma_collection.query(
                query_texts=[query], n_results=n_results, where=where_filter
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
                search_results.append(
                    SearchResult(
                        content=doc,
                        metadata=metadatas[i] if i < len(metadatas) else {},
                        distance=distances[i] if i < len(distances) else 0.0,
                        id=ids[i] if i < len(ids) else f"result_{i}",
                    )
                )

            _get_logger().info(
                "Vector search completed", query=query[:50], results=len(search_results)
            )

            return search_results

        except Exception as e:
            _get_logger().error("Search failed", error=str(e))
            return []

    async def add(
        self,
        documents: list[str],
        ids: list[str],
        collection: str | None = None,
        metadatas: list[Dict[str, Any]] | None = None,
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
        client = self._ensure_client()
        if not client:
            _get_logger().warning("Vector memory not available for add")
            return False

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return False

        try:
            chroma_collection.add(documents=documents, ids=ids, metadatas=metadatas)

            _get_logger().info(
                "Documents added to vector store",
                count=len(documents),
                collection=collection or self._default_collection,
            )
            return True

        except Exception as e:
            _get_logger().error("Failed to add documents", error=str(e))
            return False

    async def delete(self, ids: list[str], collection: str | None = None) -> bool:
        """Delete documents by IDs."""
        client = self._ensure_client()
        if not client:
            return False

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return False

        try:
            chroma_collection.delete(ids=ids)
            return True
        except Exception as e:
            _get_logger().error("Failed to delete documents", error=str(e))
            return False

    async def count(self, collection: str | None = None) -> int:
        """Get the number of documents in a collection."""
        client = self._ensure_client()
        if not client:
            return 0

        chroma_collection = self._get_or_create_collection(collection)
        if not chroma_collection:
            return 0

        return chroma_collection.count()

    async def list_collections(self) -> list[str]:
        """List all collection names."""
        client = self._ensure_client()
        if not client:
            return []

        try:
            collections = client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            _get_logger().error("Failed to list collections", error=str(e))
            return []


# Singleton accessor
def get_vector_memory() -> VectorMemory:
    """Get the vector memory singleton instance."""
    return VectorMemory()


# Convenience functions
async def search_knowledge(
    query: str, n_results: int = 5, collection: str | None = None
) -> list[SearchResult]:
    """Search project knowledge base."""
    return await get_vector_memory().search(query, n_results, collection)


async def ingest_knowledge(
    documents: list[str],
    ids: list[str],
    collection: str | None = None,
    metadatas: list[Dict[str, Any]] | None = None,
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
    - Preloaded skill definitions (SKILL.md)
    """
    from common.gitops import get_project_root

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
            "metadata": {"domain": "git", "priority": "high"},
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
            "metadata": {"domain": "architecture", "priority": "high"},
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
            "metadata": {"domain": "standards", "priority": "medium"},
        },
    ]

    vm = get_vector_memory()

    for doc in bootstrap_docs:
        await vm.add(
            documents=[doc["content"].strip()], ids=[doc["id"]], metadatas=[doc["metadata"]]
        )

    # Also ingest preloaded skill definitions (SKILL.md)
    await ingest_preloaded_skill_definitions()

    _get_logger().info("Knowledge base bootstrapped", docs=len(bootstrap_docs))


async def ingest_preloaded_skill_definitions() -> None:
    """
    Ingest SKILL.md (definition file) from all preloaded skills into the knowledge base.

    This ensures that when Claude processes user requests, it has access to
    the skill rules even if not explicitly loading the skill.

    The following skills are preloaded and their definitions will be ingested:
    - git: Commit authorization protocol
    - knowledge: Project rules and scopes
    - writer: Writing quality standards
    - filesystem: Safe file operations
    - terminal: Command execution rules
    - testing_protocol: Testing workflow
    """
    from agent.core.registry import get_skill_registry
    from common.skills_path import SKILLS_DIR

    registry = get_skill_registry()
    preload_skills = registry.get_preload_skills()

    if not preload_skills:
        _get_logger().info("No preload skills configured")
        return

    vm = get_vector_memory()
    skills_ingested = 0

    for skill_name in preload_skills:
        definition_path = SKILLS_DIR.definition_file(skill_name)

        if not definition_path.exists():
            _get_logger().debug(f"Skill {skill_name} has no definition file")
            continue

        try:
            content = definition_path.read_text(encoding="utf-8")

            # Ingest with skill name as domain for filtering
            success = await vm.add(
                documents=[content],
                ids=[f"skill-{skill_name}-definition"],
                metadatas=[
                    {
                        "domain": "skill",
                        "skill": skill_name,
                        "priority": "high",
                        "source_file": str(definition_path),
                    }
                ],
            )

            if success:
                skills_ingested += 1
                _get_logger().info(f"Ingested definition for skill: {skill_name}")

        except Exception as e:
            _get_logger().error(f"Failed to ingest definition for skill {skill_name}: {e}")

    _get_logger().info(
        f"Preloaded skill definitions ingested: {skills_ingested}/{len(preload_skills)}"
    )


__all__ = [
    "VectorMemory",
    "get_vector_memory",
    "SearchResult",
    "search_knowledge",
    "ingest_knowledge",
    "bootstrap_knowledge_base",
    "ingest_preloaded_skill_definitions",
]
