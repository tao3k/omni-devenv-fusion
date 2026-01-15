"""
assets/skills/knowledge/scripts/search_docs.py
Phase 70: The Knowledge Matrix - Project Knowledge Search Tool

Provides semantic + keyword search over project documentation.

Usage:
    @omni("knowledge.search_project_knowledge", {"query": "git commit 规范", "limit": 3})
"""

from __future__ import annotations

import json

from agent.skills.decorators import skill_script


@skill_script(
    name="search_project_knowledge",
    description="[Knowledge RAG] Search project documentation, specs, and guides using hybrid search (semantic + keywords). Use this to find project rules, architecture decisions, and technical documentation.",
    category="knowledge",
)
async def search_project_knowledge(
    query: str,
    limit: int = 5,
    keywords: list[str] | None = None,
) -> str:
    """
    Search the project knowledge base for relevant documentation.

    **When to use:**
    - User asks about project conventions, standards, or rules
    - User wants to understand architecture or design decisions
    - User needs to reference technical documentation
    - User asks "what is our X policy?" or "how do we do Y?"

    **Examples:**
    - "What's our git commit workflow?"
    - "Show me the coding standards"
    - "How do we handle PR reviews?"
    - "What are the architecture principles?"

    Args:
        query: Natural language question about the project.
              Example: "git commit 规范是什么", "coding standards"
        limit: Maximum results to return (default: 5, max: 10)
        keywords: Optional keywords to boost relevance.
                 Example: ["git", "commit"] for git-related docs

    Returns:
        JSON string containing matching knowledge chunks with:
        - content: Full chunk text
        - preview: Truncated preview
        - doc_path: Source file path
        - title: Document title
        - section: Section title
        - distance: Relevance score (lower = better)

    Usage:
        @omni("knowledge.search_project_knowledge", {"query": "git commit 规范", "limit": 3})
    """
    limit = min(max(1, limit), 10)  # Clamp between 1 and 10
    keywords = keywords or []

    # Import here to avoid slow startup
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
                    "message": "No matching knowledge found. Try different keywords or a broader query.",
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
                    "score": round(
                        1.0 - r.get("distance", 1.0), 3
                    ),  # Convert distance to similarity
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
        error_response = {
            "query": query,
            "error": str(e),
            "results": [],
        }
        return json.dumps(error_response, ensure_ascii=False)


def format_knowledge_results(json_output: str) -> str:
    """
    Format knowledge search results as markdown for display.

    Args:
        json_output: Raw JSON output from search_project_knowledge.

    Returns:
        Formatted markdown string.
    """
    try:
        data = json.loads(json_output)

        if "error" in data:
            return f"**Search Error**: {data['error']}"

        results = data.get("results", [])
        if not results:
            return "**No matching knowledge found**"

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
