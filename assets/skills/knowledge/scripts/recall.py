"""
assets/skills/knowledge/scripts/recall.py
The Neural Matrix - Unified Knowledge Recall System

Provides semantic + keyword hybrid search over project knowledge.
Uses Rust-powered LanceDB for high-performance retrieval.

Commands:
- recall: Semantic search with hybrid ranking
- ingest: Add content to knowledge base
- stats: Get knowledge base statistics
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from omni.foundation import get_vector_store
from omni.foundation.api.decorators import skill_command

logger = structlog.get_logger(__name__)


# =============================================================================
# Types
# =============================================================================


class RecallResult:
    """Result from a knowledge recall operation."""

    def __init__(
        self,
        content: str,
        source: str,
        score: float,
        title: str = "",
        section: str = "",
    ):
        self.content = content
        self.source = source
        self.score = score
        self.title = title
        self.section = section

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "source": self.source,
            "score": round(self.score, 4),
            "title": self.title,
            "section": self.section,
        }


# =============================================================================
# Knowledge Recall Commands (The Neural Matrix)
# =============================================================================


@skill_command(
    name="recall",
    category="search",
    description="""
    Semantic + Keyword Hybrid Search over Project Knowledge (The Neural Matrix).

    PRIMARY interface for retrieving knowledge from the vector store.

    Args:
        - query: str - Natural language query (e.g., ActionGuard infinite loop prevention) (required)
        - limit: int = 5 - Maximum results to return (max: 10)
        - keywords: Optional[list[str]] - List of keywords to boost precision
        - collection: str = knowledge - Collection to search

    Returns:
        JSON with recall results including content, source, score, and metadata.
    """,
)
async def recall(
    query: str,
    limit: int = 5,
    keywords: list[str] | None = None,
    collection: str = "knowledge",
) -> str:
    """
    Recall knowledge using hybrid semantic + keyword search.

    Args:
        query: Search query (natural language).
        limit: Maximum results to return.
        keywords: Optional keywords for boosting.
        collection: Collection name to search.

    Returns:
        JSON string with recall results.
    """
    # Validate and normalize parameters
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 5
    limit = min(max(1, limit), 10)

    keywords = keywords or []

    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                {
                    "query": query,
                    "status": "unavailable",
                    "message": "Vector store not initialized. Run 'omni skill reload' first.",
                    "results": [],
                },
                indent=2,
            )

        # Execute search
        if keywords:
            # Hybrid search via raw Rust store
            from omni.foundation.services.embedding import get_embedding_service

            embedding_service = get_embedding_service()
            vector = embedding_service.embed(query)[0]
            json_results = vector_store.store.search_hybrid(collection, vector, keywords, limit)
        else:
            # Pure semantic search via VectorStoreClient
            raw_results = await vector_store.search(query, limit, collection)

            # Convert SearchResult to our RecallResult format
            results = []
            for r in raw_results:
                distance = getattr(r, "distance", 0.0)
                score = max(0.0, 1.0 - distance)

                results.append(
                    RecallResult(
                        content=r.content,
                        source=r.id,
                        score=score,
                        title=r.metadata.get("title", ""),
                        section=r.metadata.get("section", ""),
                    )
                )

            # Format response
            response = {
                "query": query,
                "keywords": keywords,
                "collection": collection,
                "found": len(results),
                "status": "success",
                "results": [r.to_dict() for r in results],
            }

            return json.dumps(response, indent=2, ensure_ascii=False)

        # Parse hybrid search results
        results = []
        for json_str in json_results:
            try:
                data = json.loads(json_str)
                distance = data.get("distance", 1.0)
                score = max(0.0, 1.0 - distance)

                payload = data.get("metadata", {})
                results.append(
                    RecallResult(
                        content=payload.get("content", data.get("content", "")),
                        source=payload.get("source", data.get("id", "")),
                        score=score,
                        title=payload.get("title", ""),
                        section=payload.get("section", ""),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"Failed to parse search result: {e}")
                continue

        # Format response
        response = {
            "query": query,
            "keywords": keywords,
            "collection": collection,
            "found": len(results),
            "status": "success",
            "results": [r.to_dict() for r in results],
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Recall failed: {e}")
        return json.dumps(
            {
                "query": query,
                "status": "error",
                "error": str(e),
                "results": [],
            },
            indent=2,
            ensure_ascii=False,
        )


@skill_command(
    name="ingest",
    category="write",
    description="""
    Add content to the knowledge base for semantic retrieval.

    Args:
        - content: str - Text content to embed and store (required)
        - source: str - Source path/identifier (e.g., docs/guide.md) (required)
        - metadata: Optional[Dict[str, Any]] - Dictionary of metadata (tags, title, etc.)
        - collection: str = knowledge - Collection name

    Returns:
        JSON with ingestion status, document_id, source, and content_length.
    """,
)
async def ingest(
    content: str,
    source: str,
    metadata: dict[str, Any] | None = None,
    collection: str = "knowledge",
) -> str:
    """
    Ingest content into the knowledge base.

    Args:
        content: Text content to embed and store.
        source: Source identifier (file path, URL, etc.).
        metadata: Optional metadata dictionary.
        collection: Collection name.

    Returns:
        JSON with ingestion result.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                {
                    "status": "unavailable",
                    "message": "Vector store not initialized.",
                },
                indent=2,
            )

        # Add via VectorStoreClient
        success = await vector_store.add(content, metadata, collection)

        if success:
            doc_id = f"doc_{hash(source) % 100000:05d}"
            return json.dumps(
                {
                    "status": "success",
                    "document_id": doc_id,
                    "source": source,
                    "content_length": len(content),
                    "collection": collection,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Failed to add content to vector store",
                },
                indent=2,
            )

    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
            },
            indent=2,
        )


@skill_command(
    name="stats",
    category="view",
    description="""
    Get knowledge base statistics including document count and vector dimension.

    Args:
        - collection: str = knowledge - Collection name

    Returns:
        JSON with status, collection, document_count, and vector_dimension.
    """,
)
async def stats(collection: str = "knowledge") -> str:
    """
    Get knowledge base statistics.

    Args:
        collection: Collection name.

    Returns:
        JSON with statistics.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                {
                    "status": "unavailable",
                    "message": "Vector store not initialized.",
                },
                indent=2,
            )

        count = await vector_store.count(collection)

        # Get dimension from embedding service
        from omni.foundation.services.embedding import get_embedding_service

        dimension = get_embedding_service().dimension

        return json.dumps(
            {
                "status": "success",
                "collection": collection,
                "document_count": count,
                "vector_dimension": dimension,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
            },
            indent=2,
        )


@skill_command(
    name="clear",
    category="write",
    description="""
    Clear all knowledge from a collection. WARNING: Permanently deletes indexed knowledge.

    Args:
        - collection: str = knowledge - Collection name to clear

    Returns:
        JSON with status and message.
    """,
)
async def clear(collection: str = "knowledge") -> str:
    """
    Clear all knowledge from a collection.

    Args:
        collection: Collection name.

    Returns:
        JSON with operation status.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                {
                    "status": "unavailable",
                    "message": "Vector store not initialized.",
                },
                indent=2,
            )

        # Drop and recreate the table
        vector_store.store.drop_table(collection)

        return json.dumps(
            {
                "status": "success",
                "message": f"Collection '{collection}' cleared.",
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Clear failed: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
            },
            indent=2,
        )


# =============================================================================
# Helper Functions
# =============================================================================


def format_recall_results(json_output: str) -> str:
    """Format recall results as markdown for display."""
    try:
        data = json.loads(json_output)

        if "error" in data or data.get("status") == "error":
            return f"**Recall Error**: {data.get('error', 'Unknown error')}"

        if data.get("status") == "unavailable":
            return f"**Knowledge Base Unavailable**: {data.get('message', '')}"

        results = data.get("results", [])
        if not results:
            return f"**No knowledge found for**: `{data.get('query', '')}`"

        lines = [
            "# Knowledge Recall",
            f"**Query**: `{data.get('query', '')}`",
            f"**Found**: {data.get('found', 0)} results",
            "",
            "---",
        ]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Unknown")
            section = result.get("section", "")
            source = result.get("source", "")
            score = result.get("score", 0)
            content = result.get("content", "")[:400]

            lines.append(f"## {i}. {title}")
            if section:
                lines.append(f"**Section**: {section}")
            lines.append(f"**Relevance**: {score:.1%}")
            lines.append(f"**Source**: `{source}`")
            lines.append("")
            lines.append(f"> {content}...")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    except json.JSONDecodeError:
        return json_output


__all__ = ["clear", "format_recall_results", "ingest", "recall", "stats"]
