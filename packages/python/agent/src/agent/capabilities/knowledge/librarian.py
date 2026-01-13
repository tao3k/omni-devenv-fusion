# capabilities/knowledge/librarian.py
"""
Librarian - RAG-powered Knowledge Base Functions

One Tool compatible - call directly or route via @omni.

Functions:
- consult_knowledge_base: Semantic search across project knowledge
- ingest_knowledge: Add new knowledge to the vector store
- bootstrap_knowledge: Bootstrap knowledge base with core documentation
- list_knowledge_domains: List available knowledge domains
- search_project_rules: Search for project rules and workflows

Phase 32: Modularized from librarian.py
"""

from __future__ import annotations

from typing import Any, Dict, List

from common.gitops import get_project_root
import structlog

from agent.core.vector_store import (
    get_vector_memory,
    search_knowledge,
    ingest_knowledge as _ingest_knowledge,
    bootstrap_knowledge_base,
)

logger = structlog.get_logger(__name__)


async def consult_knowledge_base(
    query: str,
    n_results: int = 5,
    collection: str | None = None,
    domain_filter: str | None = None,
) -> Dict[str, Any]:
    """
    Query the project knowledge base using semantic search.

    Uses RAG (Retrieval-Augmented Generation) to find relevant
    documentation, rules, and context for the given query.

    Args:
        query: The search query (what you're looking for)
        n_results: Number of results to return (default: 5)
        collection: Optional collection name to search
        domain_filter: Optional domain tag to filter by
                     (e.g., "git", "architecture", "standards")

    Returns:
        Dict containing:
        - results: List of matching documents with content and metadata
        - query: The original query
        - count: Number of results found
    """
    vm = get_vector_memory()

    if not vm.client:
        return {
            "success": False,
            "error": "Vector memory not available",
            "query": query,
            "results": [],
            "count": 0,
        }

    where_filter: Dict[str, str] | None = None
    if domain_filter:
        where_filter = {"domain": domain_filter}

    results = await vm.search(
        query=query, n_results=n_results, collection=collection, where_filter=where_filter
    )

    formatted_results: List[Dict[str, Any]] = []
    for r in results:
        formatted_results.append(
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "relevance_score": max(0.0, 1.0 - r.distance),
            }
        )

    response: Dict[str, Any] = {
        "success": True,
        "query": query,
        "results": formatted_results,
        "count": len(formatted_results),
    }

    if not results:
        response["message"] = (
            "No matching knowledge found. Try a different query or ingest relevant knowledge."
        )

    logger.info(
        "Knowledge base consulted",
        query=query[:50],
        results=len(formatted_results),
        domain=domain_filter,
    )

    return response


async def ingest_knowledge(
    documents: List[str],
    ids: List[str],
    collection: str | None = None,
    domains: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Add new knowledge to the vector store for future retrieval.

    Use this to teach the system about:
    - Project-specific workflows
    - Architectural decisions
    - Code patterns and examples
    - Documentation and guides

    Args:
        documents: List of document texts to add
        ids: Unique identifiers for each document (must match documents order)
        collection: Optional collection name
        domains: Optional domain tags for each document (must match documents order)

    Returns:
        Dict containing success status and details
    """
    if len(documents) != len(ids):
        return {
            "success": False,
            "error": f"Documents count ({len(documents)}) must match IDs count ({len(ids)})",
        }

    metadatas = None
    if domains:
        metadatas = [{"domain": d} for d in domains]

    success = await _ingest_knowledge(
        documents=documents, ids=ids, collection=collection, metadatas=metadatas
    )

    result: Dict[str, Any] = {
        "success": success,
        "documents_ingested": len(documents) if success else 0,
        "collection": collection or "project_knowledge",
    }

    if success:
        logger.info("Knowledge ingested", count=len(documents), collection=result["collection"])
    else:
        result["error"] = "Failed to ingest knowledge"

    return result


async def bootstrap_knowledge() -> str:
    """
    Bootstrap the knowledge base with essential project documentation.

    This is typically called once on first setup to populate the vector
    store with core project knowledge (git workflow, architecture, etc.).

    Returns:
        Formatted status message
    """
    try:
        await bootstrap_knowledge_base()
        return "✅ Knowledge base bootstrapped successfully with core project documentation."
    except Exception as e:
        logger.error("Bootstrap failed", error=str(e))
        return f"❌ Bootstrap failed: {e}"


async def list_knowledge_domains() -> str:
    """
    List available knowledge domains and their document counts.

    Returns:
        Formatted list of domains
    """
    vm = get_vector_memory()

    collections = await vm.list_collections()

    domain_counts = {}
    for coll in collections:
        count = await vm.count(collection=coll)
        domain_counts[coll] = count

    total = sum(domain_counts.values())

    if not domain_counts:
        return "📚 No knowledge domains found."

    lines = ["📚 **Knowledge Domains:**", ""]
    for domain, count in domain_counts.items():
        lines.append(f"- **{domain}**: {count} documents")
    lines.append(f"\n**Total**: {total} documents")

    return "\n".join(lines)


async def search_project_rules(query: str) -> str:
    """
    Search specifically for project rules and workflows.

    This is a convenience wrapper around consult_knowledge_base
    that filters for high-priority rules and workflows.
    """
    all_results = await search_knowledge(query=query, n_results=10)

    relevant = [r for r in all_results if r.metadata.get("priority") in ["high", "medium"]]

    if not relevant:
        relevant = all_results[:5]

    if not relevant:
        return f"No matching rules found for: '{query}'"

    lines = [f"🔍 **Search Results for**: '{query}'", ""]
    for r in relevant:
        source = r.metadata.get("domain", "general")
        relevance = "⭐" * int((1.0 - r.distance) * 5)
        lines.append(f"{relevance} **{source}**")
        lines.append(f"> {r.content[:200]}...")
        lines.append("")

    return "\n".join(lines)


async def get_skill_lessons(skills: List[str], limit: int = 5) -> str:
    """
    [Phase 44] Retrieve lessons specifically tagged for these skills.

    Searches the vector store for harvested insights (past mistakes, pitfalls,
    best practices) that are relevant to the given skills.

    Args:
        skills: List of skill names to search lessons for
        limit: Maximum number of lessons to return (default: 5)

    Returns:
        Formatted string with lessons, or empty string if none found
    """
    if not skills:
        return ""

    vm = get_vector_memory()

    if not vm.client:
        return ""

    # Build query from skill names
    query = f"mistakes pitfalls best practices for {' '.join(skills)}"

    # Search specifically for harvested insights
    results = await vm.search(
        query=query, n_results=limit, where_filter={"type": "harvested_insight"}
    )

    if not results:
        return ""

    # Format results with header
    lines = ["### 🛑 KNOWN PITFALLS & PAST LESSONS", ""]

    for r in results:
        skill_tag = r.metadata.get("skill", "general")
        relevance = "⭐" * int((1.0 - r.distance) * 5)
        lines.append(f"{relevance} **{skill_tag}**: {r.content}")
        lines.append("")

    logger.info("Skill lessons retrieved", skills=skills, lessons=len(results))

    return "\n".join(lines)


logger.info("Librarian functions loaded (One Tool compatible)")


__all__ = [
    "consult_knowledge_base",
    "ingest_knowledge",
    "bootstrap_knowledge",
    "list_knowledge_domains",
    "search_project_rules",
    "get_skill_lessons",
]
