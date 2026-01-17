"""
assets/skills/note_taker/scripts/update_knowledge_base.py
Phase 63: Knowledge Base Update Command.

Saves extracted knowledge to the knowledge base for future retrieval.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.skills.decorators import skill_command
from common.prj_dirs import PRJ_DATA


@skill_command(
    name="update_knowledge_base",
    category="write",
    description="""
    Saves extracted knowledge to the knowledge base for future retrieval.

    Stores knowledge in PRJ_DATA/knowledge/harvested/ for runtime persistence.

    Args:
        category: Knowledge category (`patterns`, `solutions`, `errors`,
                  `techniques`, `notes`).
        title: Title of the knowledge entry.
        content: Markdown content of the knowledge.
        tags: Optional tags for categorization.

    Returns:
        Dict with success status, path to saved file, category, and title.

    Example:
        @omni("note_taker.update_knowledge_base", {"category": "patterns", "title": "Fix pattern", "content": "...", "tags": ["fix", "pattern"]})
    """,
)
def update_knowledge_base(
    category: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    category = category.lower().strip()
    valid_categories = ["patterns", "solutions", "errors", "techniques", "notes"]
    if category not in valid_categories:
        category = "notes"

    knowledge_dir = PRJ_DATA("knowledge", "harvested", category)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = re.sub(r"[^\w\-]", "_", title.lower())[:50]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}.md"

    timestamp_full = datetime.now(timezone.utc).isoformat()

    markdown = f"""---
title: {title}
category: {category}
tags: {tags or []}
created: {timestamp_full}
---

# {title}

{content}
"""

    output_path = knowledge_dir / filename
    output_path.write_text(markdown)

    _update_index(category, title, tags or [], str(output_path))

    return {
        "success": True,
        "path": str(output_path),
        "category": category,
        "title": title,
    }


@skill_command(
    name="search_notes",
    category="read",
    description="""
    Searches existing notes and knowledge entries.

    Args:
        query: Search query string.
        category: Optional category filter (`patterns`, `solutions`, etc.).
        limit: Maximum number of results. Defaults to `10`.

    Returns:
        Dict with success status, query, count, and list of results.
        Each result includes category, title, path, tags, and content snippet.
    """,
)
def search_notes(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    results = []
    query_lower = query.lower()

    if category:
        categories = [category.lower()]
    else:
        categories = ["patterns", "solutions", "errors", "techniques", "notes"]

    for cat in categories:
        knowledge_dir = PRJ_DATA("knowledge", "harvested", cat)
        if not knowledge_dir.exists():
            continue

        for md_file in knowledge_dir.glob("*.md"):
            try:
                content = md_file.read_text().lower()
                if query_lower in content:
                    frontmatter = _parse_frontmatter(md_file.read_text())
                    title = frontmatter.get("title", md_file.stem)

                    if len(results) < limit:
                        results.append(
                            {
                                "category": cat,
                                "title": title,
                                "path": str(md_file),
                                "tags": frontmatter.get("tags", []),
                                "snippet": _get_snippet(content, query_lower),
                            }
                        )
            except Exception:
                continue

    return {
        "success": True,
        "query": query,
        "count": len(results),
        "results": results,
    }


def _update_index(category: str, title: str, tags: list[str], path: str) -> None:
    """Update the knowledge index for a category."""
    index_dir = PRJ_DATA("knowledge", "index")
    index_dir.mkdir(parents=True, exist_ok=True)

    index_file = index_dir / f"{category}.json"

    if index_file.exists():
        index = json.loads(index_file.read_text())
    else:
        index = {"entries": []}

    entry = {
        "title": title,
        "tags": tags,
        "path": path,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    index["entries"].append(entry)

    index_file.write_text(json.dumps(index, indent=2))


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content."""
    frontmatter = {}

    if content.startswith("---"):
        end_marker = content.find("---", 3)
        if end_marker != -1:
            yaml_content = content[3:end_marker].strip()
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if value.startswith("[") and value.endswith("]"):
                        value = value[1:-1].replace('"', "").split(",")
                        value = [v.strip().strip("'\"") for v in value if v.strip()]

                    frontmatter[key] = value

    return frontmatter


def _get_snippet(content: str, query: str, context_chars: int = 100) -> str:
    """Get a snippet around the match."""
    idx = content.find(query)
    if idx == -1:
        return ""

    start = max(0, idx - context_chars)
    end = min(len(content), idx + len(query) + context_chars)

    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


if __name__ == "__main__":
    result = update_knowledge_base(
        category="patterns",
        title="Test Pattern",
        content="This is a test pattern content.",
        tags=["test", "example"],
    )
    print(json.dumps(result, indent=2))

    search_result = search_notes("test")
    print(json.dumps(search_result, indent=2))
