"""
Code Search Skill - Semantic Code Search via Librarian

Provides Agent with the ability to semantically search the codebase using
the Librarian's hybrid search capabilities.

Commands:
- code_search: Semantic search for code implementation
- code_context: Get LLM-ready context blocks
- knowledge_status: Check knowledge base status
"""

from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.code.search")


@skill_command(
    name="code_search",
    category="search",
    description="""
    Semantically search the codebase for implementation details, functions, or classes.

    Use this when you need to find:
    - How a particular feature is implemented
    - Where a function or class is defined
    - Code related to a specific concept

    Args:
        - query: str - Natural language query about the code (required)
        - limit: int - Maximum number of results (default 5)

    Returns:
        Dictionary with success, query, count, and results with file, lines, and content.
    """,
    autowire=True,
)
def code_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Perform semantic search on the codebase using Librarian."""
    from omni.core.runtime.services import get_librarian

    librarian = get_librarian()

    if librarian is None:
        return {
            "success": False,
            "error": "Librarian service not available. Knowledge base may not be initialized.",
            "hint": "Run 'omni knowledge ingest' first to initialize the knowledge base.",
        }

    try:
        results = librarian.query(query, limit=limit)

        if not results:
            return {
                "success": True,
                "query": query,
                "count": 0,
                "results": [],
                "message": f"No results found for '{query}'. Try different keywords.",
            }

        # Format results
        formatted_results = []
        for res in results:
            meta = res.get("metadata", {})
            if isinstance(meta, str):
                import json

                meta = json.loads(meta)

            formatted_results.append(
                {
                    "file": meta.get("file_path", "unknown"),
                    "lines": f"L{meta.get('start_line', '?')}-{meta.get('end_line', '?')}",
                    "type": meta.get("chunk_type", "code"),
                    "score": res.get("score", 0),
                    "content": res["text"][:500] + "..." if len(res["text"]) > 500 else res["text"],
                }
            )

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Code search failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
        }


@skill_command(
    name="code_context",
    category="search",
    description="""
    Get LLM-ready context blocks for a query.

    This returns formatted context suitable for passing directly to an LLM.
    Each context block includes the file path, line numbers, and the code content
    wrapped in markdown code fences.

    Args:
        - query: str - Query to get context for (required)
        - limit: int - Number of context blocks (default 3)

    Returns:
        Formatted context string with code blocks, or error message.
    """,
    autowire=True,
)
def code_context(query: str, limit: int = 3) -> dict[str, Any]:
    """Get formatted LLM-ready context blocks from the codebase."""
    from omni.core.runtime.services import get_librarian

    librarian = get_librarian()

    if librarian is None:
        return {
            "success": False,
            "error": "Librarian service not available.",
        }

    try:
        context = librarian.get_context(query, limit=limit)

        if not context:
            return {
                "success": True,
                "query": query,
                "context": "",
                "message": "No context found. Try a different query or ingest the project first.",
            }

        return {
            "success": True,
            "query": query,
            "context": context,
            "blocks": limit,
        }

    except Exception as e:
        logger.error(f"Failed to get code context: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@skill_command(
    name="knowledge_status",
    category="system",
    description="""
    Check the status of the knowledge base indexing.

    Returns information about:
    - Whether the knowledge base is online
    - Number of indexed files
    - Number of chunks in the database
    - Manifest status

    Useful for debugging and verifying that the knowledge base is working.
    """,
    autowire=True,
)
def knowledge_status() -> dict[str, Any]:
    """Get knowledge base status."""
    from omni.core.runtime.services import get_librarian

    librarian = get_librarian()

    if librarian is None:
        return {
            "status": "offline",
            "message": "Librarian service not initialized.",
            "hint": "Ensure SkillManager is started with ingest_knowledge=True",
        }

    try:
        stats = librarian.get_stats()
        manifest = librarian.get_manifest_status()

        return {
            "status": "online",
            "indexed_files": manifest.get("tracked_files", 0),
            "total_chunks": stats.get("record_count", 0),
            "table": stats.get("table", "unknown"),
            "manifest_exists": manifest.get("manifest_exists", False),
            "manifest_path": manifest.get("manifest_path", ""),
        }

    except Exception as e:
        logger.error(f"Failed to get knowledge status: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@skill_command(
    name="ingest_knowledge",
    category="system",
    description="""
    Ingest or update the project knowledge base.

    Performs incremental ingestion by default - only processes changed files.
    Use clean=True to force a full re-index.

    Args:
        - clean: bool - If True, drop and recreate the entire index (default False)

    Returns:
        Dictionary with files_processed, chunks_indexed, and errors.
    """,
    autowire=True,
)
def ingest_knowledge(clean: bool = False) -> dict[str, Any]:
    """Ingest project knowledge into the knowledge base."""
    from omni.core.runtime.services import get_librarian

    librarian = get_librarian()

    if librarian is None:
        return {
            "success": False,
            "error": "Librarian service not available.",
        }

    try:
        result = librarian.ingest(clean=clean)

        return {
            "success": True,
            "files_processed": result.get("files_processed", 0),
            "chunks_indexed": result.get("chunks_indexed", 0),
            "errors": result.get("errors", 0),
            "updated": result.get("updated", 0),
            "mode": "incremental" if not clean else "full",
        }

    except Exception as e:
        logger.error(f"Knowledge ingestion failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


__all__ = ["code_search", "code_context", "knowledge_status", "ingest_knowledge"]
