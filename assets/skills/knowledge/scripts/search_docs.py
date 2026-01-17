"""
assets/skills/knowledge/scripts/search_docs.py
Phase 70: The Knowledge Matrix - Project Knowledge Search Tool

Provides semantic + keyword search over project documentation.
"""

from __future__ import annotations

import json
from agent.skills.decorators import skill_command


@skill_command(
    name="search_project_knowledge",
    category="read",
    description="""
    [Knowledge RAG] Searches project documentation, specs, and guides using hybrid search.

    Use this for architecture, conventions, and how-to guides.
    Combines semantic similarity with keyword boosting.

    Args:
        query: Natural language query (e.g., "coding standards", "git workflow").
        limit: Maximum results to return. Defaults to `5`. Maximum: `10`.
        keywords: Optional list of keywords to boost relevance.
                  Example: `["python", "style"]`

    Returns:
        JSON string with results or advice if table missing.
        Includes `content`, `preview`, `doc_path`, `title`, `section`, `score`.

    Example:
        @omni("knowledge.search_project_knowledge", {"query": "coding standards", "limit": 5})
    """,
)
async def search_project_knowledge(
    query: str,
    limit: int = 5,
    keywords: list[str] | None = None,
) -> str:
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 5
    limit = min(max(1, limit), 10)
    keywords = keywords or []

    from agent.core.vector_store import get_vector_memory

    vm = get_vector_memory()

    try:
        results = await vm.search_knowledge_hybrid(
            query=query,
            keywords=keywords,
            limit=limit,
            table_name="knowledge",
        )

        if not results:
            return json.dumps(
                {
                    "query": query,
                    "results": [],
                    "message": "No matching knowledge found in documentation. Try searching memory/experience instead.",
                },
                ensure_ascii=False,
                indent=2,
            )

        formatted_results = []
        for r in results:
            formatted_results.append(
                {
                    "content": r.get("content", ""),
                    "preview": r.get("preview", ""),
                    "doc_path": r.get("doc_path", ""),
                    "title": r.get("title", ""),
                    "section": r.get("section", ""),
                    "score": round(1.0 - r.get("distance", 1.0), 3),
                }
            )

        response = {
            "query": query,
            "keywords": keywords,
            "found": len(formatted_results),
            "results": formatted_results,
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = str(e)
        if "Table not found" in error_msg or "knowledge" in error_msg.lower():
            return json.dumps(
                {
                    "query": query,
                    "error": "Knowledge Base Not Initialized",
                    "message": "The documentation index (knowledge table) is empty. Please run 'omni ingest' to build it.",
                    "suggestion": "Try using 'search_memory' to find past experiences instead.",
                },
                indent=2,
            )

        error_response = {
            "query": query,
            "error": str(e),
            "results": [],
        }
        return json.dumps(error_response, ensure_ascii=False)


def format_knowledge_results(json_output: str) -> str:
    """Format knowledge search results as markdown for display."""
    try:
        data = json.loads(json_output)

        if "error" in data:
            msg = data.get("message", "")
            sugg = data.get("suggestion", "")
            return f"**Knowledge Search Error**: {data['error']}\n\n{msg}\n{sugg}"

        results = data.get("results", [])
        if not results:
            return f"**No documentation found for**: `{data.get('query')}`"

        lines = [
            f"# Knowledge Search Results",
            f"**Query**: `{data.get('query', '')}`",
            f"**Found**: {data.get('found', 0)} results",
            "",
            "---",
        ]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Unknown")
            section = result.get("section", "")
            doc_path = result.get("doc_path", "")
            score = result.get("score", 0)
            preview = result.get("preview", "")[:300]

            lines.append(f"## {i}. {title}")
            if section:
                lines.append(f"**Section**: {section}")
            lines.append(f"**Relevance**: {score:.1%}")
            lines.append(f"**Source**: `{doc_path}`")
            lines.append("")
            lines.append(f"> {preview}...")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    except json.JSONDecodeError:
        return json_output


__all__ = ["search_project_knowledge", "format_knowledge_results"]
