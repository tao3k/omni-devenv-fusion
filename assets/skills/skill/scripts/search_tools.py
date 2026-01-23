"""
skill/scripts/search_tools.py
Adaptive Context - Intent-Driven Tool Loading

Provides semantic + keyword search over registered tools.
Allows Agent to dynamically discover tools based on intent.
"""

import json
from typing import Any

from omni.foundation.api.decorators import skill_command


@skill_command(
    name="search_tools",
    category="read",
    description="""
    [CRITICAL] Searches for available tools using semantic + keyword matching.

    MUST call this tool if you cannot find a suitable tool in your current context.
    Enables dynamic discovery of relevant tools when the default toolset doesn't
    match the current intent.

    Args:
        query: Natural language description of what you need.
               Example: "git commit changes", "search files", "write tests"
        limit: Maximum number of tools to return. Defaults to `10`.
               Maximum: `50`.
        keywords: Optional list of keywords to boost relevance.
                  Example: `["git", "commit"]` for git commit related tools.

    Returns:
        JSON string containing matching tools with their schemas.

        Format:
        {
            "tools": [
                {
                    "name": "git.commit",
                    "description": "...",
                    "schema": {...},
                    "score": 0.95,
                    "skill": "git"
                },
                ...
            ],
            "total": 5,
            "query": "git commit"
        }

    Usage:
        @omni("skill.search_tools", {"query": "git commit", "keywords": ["git"]})
    """,
)
async def search_tools(
    query: str,
    limit: int = 10,
    keywords: list[str] | None = None,
) -> str:
    limit = min(max(1, limit), 50)
    keywords = keywords or []

    from omni.foundation import get_vector_store

    vm = get_vector_store()

    try:
        results = await vm.search_tools_hybrid(query, keywords=keywords, limit=limit)

        tools = []
        for r in results:
            try:
                metadata = r.get("metadata", {}) or {}
                input_schema = metadata.get("input_schema", "{}")
                if isinstance(input_schema, str):
                    schema = json.loads(input_schema)
                else:
                    schema = input_schema

                tools.append(
                    {
                        "name": r.get("id", ""),
                        "description": r.get("content", ""),
                        "schema": schema,
                        "score": 1.0 - r.get("distance", 1.0),
                        "skill": metadata.get("skill_name", ""),
                        "file_path": metadata.get("file_path", ""),
                        "docstring": metadata.get("docstring", ""),
                    }
                )
            except (json.JSONDecodeError, TypeError):
                continue

        response = {
            "tools": tools,
            "total": len(tools),
            "query": query,
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        error_response = {
            "error": str(e),
            "tools": [],
            "total": 0,
            "query": query,
        }
        return json.dumps(error_response, ensure_ascii=False)


def format_search_result(json_output: str) -> str:
    """
    Format search results as markdown for display.

    Args:
        json_output: Raw JSON output from search_tools.

    Returns:
        Formatted markdown string.
    """
    try:
        data = json.loads(json_output)

        if "error" in data:
            return f"**Search Error**: {data['error']}"

        tools = data.get("tools", [])
        if not tools:
            return "**No matching tools found**\n\nTry different keywords or a broader query."

        lines = [
            "# Search Results",
            f"**Query**: `{data.get('query', '')}`",
            f"**Found**: {len(tools)} tools",
            "",
            "## Tools",
        ]

        for tool in tools:
            lines.append(f"### `{tool['name']}`")
            lines.append(f"**Skill**: {tool.get('skill', 'unknown')}")
            if tool.get("description"):
                lines.append(f">{tool['description']}")
            lines.append("")

        return "\n".join(lines)

    except json.JSONDecodeError:
        return json_output


__all__ = ["search_tools", "format_search_result"]
