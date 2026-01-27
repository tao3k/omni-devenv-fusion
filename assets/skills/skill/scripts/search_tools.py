"""
skill/scripts/search_tools.py
Adaptive Context - Intent-Driven Tool Loading

Provides semantic + keyword search over registered tools.
Allows Agent to dynamically discover tools based on intent.

Queries loaded skills directly to get accurate input schemas.
"""

import json
import re
from typing import Any

from omni.foundation.api.decorators import skill_command


def _tokenize(text: str) -> set[str]:
    """Convert text to lowercase words."""
    return set(re.findall(r"\w+", text.lower()))


def _calculate_score(query: str, tool_name: str, description: str, skill_name: str) -> float:
    """Calculate relevance score based on keyword matching."""
    query_tokens = _tokenize(query)
    name_tokens = _tokenize(tool_name)
    desc_tokens = _tokenize(description)
    skill_tokens = _tokenize(skill_name)

    # Calculate token overlap
    query_set = set(query_tokens)
    name_overlap = len(query_set & name_tokens)
    desc_overlap = len(query_set & desc_tokens)
    skill_overlap = len(query_set & skill_tokens)

    # Weighted scoring: name matches are most important
    score = name_overlap * 3.0 + desc_overlap * 1.0 + skill_overlap * 2.0

    # Boost for exact prefix match
    if tool_name.lower().startswith(query.lower()):
        score += 5.0

    return score


@skill_command(
    name="search_tools",
    category="read",
    description="""
    [CRITICAL] Searches for available tools using keyword matching.

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
    """Search for tools matching the query."""
    limit = min(max(1, limit), 50)
    keywords = keywords or []

    try:
        # Get tools from loaded skills (includes schemas)
        from omni.core.kernel import get_kernel

        kernel = get_kernel()
        ctx = kernel.skill_context

        # Collect tools from all loaded skills with their schemas
        all_tools = []
        skills_to_search = ctx.list_skills()

        # Fallback: Use SkillDiscoveryService if kernel has no skills or skills have no commands
        use_fallback = False
        if not skills_to_search:
            use_fallback = True
        else:
            # Check if any skill has commands loaded
            for skill_name in skills_to_search[:5]:  # Check first 5 skills
                skill_obj = ctx.get_skill(skill_name)
                if skill_obj and hasattr(skill_obj, "_script_loader") and skill_obj._script_loader:
                    if (
                        hasattr(skill_obj._script_loader, "commands")
                        and skill_obj._script_loader.commands
                    ):
                        break
            else:
                # No skills have commands, use fallback
                use_fallback = True

        if use_fallback:
            try:
                from omni.core.skills.discovery import SkillDiscoveryService

                service = SkillDiscoveryService()
                tools = service.search_tools(query, limit=50)
                # Get schema from registry for each tool
                registry = service._load_registry()
                for tool in tools:
                    record = registry.get(tool.name)
                    input_schema = {}
                    if record:
                        try:
                            input_schema = (
                                json.loads(record.input_schema) if record.input_schema else {}
                            )
                        except json.JSONDecodeError:
                            pass
                    all_tools.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "schema": input_schema,
                            "skill": tool.skill_name,
                        }
                    )
            except Exception:
                pass  # Fallback also failed, continue with empty list

        for skill_name in skills_to_search:
            skill_obj = ctx.get_skill(skill_name)
            if skill_obj is None:
                continue

            # Get commands with their configs
            if hasattr(skill_obj, "_script_loader") and skill_obj._script_loader:
                loader = skill_obj._script_loader
                for cmd_name, cmd_func in loader.commands.items():
                    # Get skill config (includes input_schema)
                    config = getattr(cmd_func, "_skill_config", {})
                    description = config.get("description", "") or f"Execute {cmd_name}"
                    input_schema = config.get("input_schema", {})

                    all_tools.append(
                        {
                            "name": cmd_name,
                            "description": description,
                            "schema": input_schema,
                            "skill": skill_name,
                        }
                    )

        if not all_tools:
            return json.dumps(
                {
                    "error": "No tools loaded",
                    "tools": [],
                    "total": 0,
                    "query": query,
                },
                ensure_ascii=False,
            )

        # Combine query with keywords for scoring
        full_query = query
        if keywords:
            full_query = f"{query} {' '.join(keywords)}"

        # Calculate scores
        scored_tools = []
        for tool in all_tools:
            score = _calculate_score(full_query, tool["name"], tool["description"], tool["skill"])
            if score > 0:
                scored_tools.append(
                    {
                        **tool,
                        "score": min(score / 10.0, 1.0),
                    }
                )

        # Sort by score descending
        scored_tools.sort(key=lambda t: t["score"], reverse=True)

        # Apply limit
        scored_tools = scored_tools[:limit]

        response = {
            "tools": scored_tools,
            "total": len(scored_tools),
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


__all__ = ["format_search_result", "search_tools"]
