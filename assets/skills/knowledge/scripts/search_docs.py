"""
assets/skills/knowledge/scripts/search_docs.py
Phase 70: The Knowledge Matrix - Project Knowledge Search Tool

Provides semantic + keyword search over project documentation.
[Omni-Dev 1.0] Added safety check for missing knowledge table.
"""

from __future__ import annotations

import json
from agent.skills.decorators import skill_script


@skill_script(
    name="search_project_knowledge",
    description="[Knowledge RAG] Search project documentation, specs, and guides using hybrid search. Use this for architecture, conventions, and how-to guides.",
    category="knowledge",
)
async def search_project_knowledge(
    query: str,
    limit: int = 5,
    keywords: list[str] | None = None,
) -> str:
    """
    Search the project knowledge base for relevant documentation.

    Returns: JSON string with results or advice if table missing.
    """
    # [FIX] Force convert limit to int, prevent TypeError caused by LLM passing string
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 5
    limit = min(max(1, limit), 10)  # Clamp between 1 and 10
    keywords = keywords or []

    from agent.core.vector_store import get_vector_memory

    vm = get_vector_memory()

    try:
        # Perform hybrid search on knowledge table
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

        # Format results for display
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
        # [FIX] Handle missing table gracefully
        if "Table not found" in error_msg or "knowledge" in error_msg.lower():
            return json.dumps({
                "query": query,
                "error": "Knowledge Base Not Initialized",
                "message": "The documentation index (knowledge table) is empty. Please run 'omni ingest' to build it.",
                "suggestion": "Try using 'search_memory' to find past experiences instead."
            }, indent=2)

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
            msg = data.get('message', '')
            sugg = data.get('suggestion', '')
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
