"""
Fake VectorStore for Testing.

A lightweight in-memory implementation of VectorStoreProtocol for fast testing.
Supports filtering and search results compatible with omni-vector (LanceDB).
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Fake search result compatible with omni-vector (LanceDB) SearchResult."""

    id: str
    content: str
    metadata: dict[str, Any]
    distance: float = 0.0

    @property
    def score(self) -> float:
        """Convert distance to similarity score."""
        return 1.0 - self.distance


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Protocol for vector store operations."""

    async def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None: ...

    async def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        where_filter: dict[str, str] | None = None,
    ) -> list[SearchResult]: ...

    async def delete_collection(self, collection: str) -> None: ...

    async def get_collection(self, collection: str) -> dict[str, Any] | None: ...


class FakeVectorStore:
    """
    In-memory fake vector store for testing.

    Implements VectorStoreProtocol for seamless replacement in tests.
    Supports filtering via where_filter for metadata filtering.

    Usage:
        store = FakeVectorStore()
        await store.add_documents("test", ["doc1", "doc2"], ["id1", "id2"])
        results = await store.search("test", "query")

    Filtering:
        await store.search("test", "query", where_filter={"installed": "true"})
    """

    def __init__(self):
        self._collections: dict[str, dict[str, Any]] = {}

    async def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to a collection."""
        if collection not in self._collections:
            self._collections[collection] = {
                "documents": [],
                "ids": [],
                "metadata": [],
            }

        for doc, doc_id, meta in zip(documents, ids, metadata or []):
            self._collections[collection]["documents"].append(doc)
            self._collections[collection]["ids"].append(doc_id)
            self._collections[collection]["metadata"].append(meta or {})

    async def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        where_filter: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """
        Search for documents in a collection using simple keyword matching.

        Supports filtering via where_filter:
            where_filter={"installed": "true"}  # Only installed skills
            where_filter={"type": "remote"}      # Only remote skills
        """
        if collection not in self._collections:
            return []

        data = self._collections[collection]
        results = []
        query_lower = query.lower()

        for doc, doc_id, meta in zip(
            data["documents"],
            data["ids"],
            data["metadata"],
        ):
            # Apply where_filter if provided
            if where_filter:
                match = True
                for key, value in where_filter.items():
                    if meta.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # Simple keyword matching for testing
            if query_lower in doc.lower():
                # Calculate fake distance based on keyword relevance
                distance = 0.0 if query_lower in doc.lower() else 0.5
                results.append(
                    SearchResult(
                        id=doc_id,
                        content=doc,
                        metadata=meta,
                        distance=distance,
                    )
                )
                if len(results) >= n_results:
                    break

        return results

    async def delete_collection(self, collection: str) -> None:
        """Delete a collection."""
        self._collections.pop(collection, None)

    async def get_collection(self, collection: str) -> dict[str, Any] | None:
        """Get collection data."""
        return self._collections.get(collection)

    async def count(self, collection: str) -> int:
        """Count documents in a collection."""
        if collection not in self._collections:
            return 0
        return len(self._collections[collection]["documents"])

    async def clear(self) -> None:
        """Clear all collections."""
        self._collections.clear()

    def has_collection(self, collection: str) -> bool:
        """Check if a collection exists."""
        return collection in self._collections

    def count_documents(self, collection: str) -> int:
        """Count documents in a collection."""
        if collection not in self._collections:
            return 0
        return len(self._collections[collection]["documents"])

    async def search_tools_hybrid(
        self,
        query: str,
        limit: int = 5,
        collection: str = "skill_registry",
    ) -> list[dict[str, Any]]:
        """
        Hybrid search for tools/skills.

        Used by SkillDiscovery for semantic skill search.
        Returns results in format expected by SkillContext.

        Args:
            query: Search query
            limit: Maximum results to return
            collection: Collection to search in (default: skill_registry)

        Returns:
            List of dicts with 'id', 'content', 'metadata', 'distance' keys
        """
        # Reuse the regular search method
        results = await self.search(
            collection=collection,
            query=query,
            n_results=limit,
        )

        # Transform to dict format
        return [
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "distance": r.distance,
            }
            for r in results
        ]

    async def sync_skills(
        self,
        base_path: str,
        table_name: str = "skills",
    ) -> dict[str, Any]:
        """
        Sync skills from base_path to vector store.

        Returns stats about added/modified/deleted skills.
        """
        from pathlib import Path

        skills_dir = Path(base_path)
        if not skills_dir.exists():
            return {"total": 0, "added": 0, "modified": 0, "deleted": 0}

        # Find all skill directories
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        stats = {"total": len(skill_dirs), "added": 0, "modified": 0, "deleted": 0}

        for skill_dir in skill_dirs:
            skill_name = skill_dir.name
            doc_id = f"skill_{skill_name}"

            # Try to find manifest
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                # Extract manifest YAML frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 3)
                    if len(parts) >= 2:
                        import yaml

                        manifest = yaml.safe_load(parts[1])
                    else:
                        manifest = {}
                else:
                    manifest = {}

                routing_kw = manifest.get("routing_keywords", [])
                intents = manifest.get("intents", [])
                deps = manifest.get("dependencies", [])

                document = f"""# {manifest.get("name", skill_name)}

{manifest.get("description", "No description.")}

**Version:** {manifest.get("version", "unknown")}
**Routing Keywords:** {", ".join(routing_kw)}
**Intents:** {", ".join(intents)}
**Dependencies:** {", ".join(deps) if deps else "None"}
"""

                # Check if already exists
                existing = await self.get_collection(table_name)
                is_new = True
                if existing and doc_id in existing.get("ids", []):
                    is_new = False

                await self.add_documents(
                    collection=table_name,
                    documents=[document],
                    ids=[doc_id],
                    metadata=[
                        {
                            "type": "skill_manifest",
                            "skill_name": skill_name,
                            "version": manifest.get("version", "unknown"),
                            "routing_keywords": routing_kw,
                            "intents": intents,
                        }
                    ],
                )

                if is_new:
                    stats["added"] += 1
                else:
                    stats["modified"] += 1

            except Exception:
                continue

        return stats
