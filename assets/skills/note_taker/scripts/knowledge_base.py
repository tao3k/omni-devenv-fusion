"""
assets/skills/note_taker/scripts/knowledge_base.py
Knowledge Base Manager.

Manages persistent knowledge storage and retrieval.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.dirs import PRJ_DATA


def save(
    category: str,
    title: str,
    content: str,
    tags: list[str],
) -> str:
    """Save knowledge entry to the knowledge base.

    Args:
        category: Knowledge category (patterns, solutions, errors, techniques)
        title: Title of the knowledge entry
        content: Markdown content of the knowledge
        tags: Optional tags for categorization

    Returns:
        Path to the saved knowledge file
    """
    # Normalize category
    category = category.lower().strip()
    valid_categories = ["patterns", "solutions", "errors", "techniques", "notes"]
    if category not in valid_categories:
        category = "notes"

    # Ensure knowledge directory exists (using PRJ_DATA for runtime data)
    knowledge_dir = PRJ_DATA("knowledge", "harvested", category)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    # Create filename from title
    filename = re.sub(r"[^\w\-]", "_", title.lower())[:50]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}.md"

    # Generate markdown with frontmatter
    timestamp_full = datetime.utcnow().isoformat()

    markdown = f"""---
title: {title}
category: {category}
tags: {tags}
created: {timestamp_full}
---

# {title}

{content}
"""

    # Write to file
    output_path = knowledge_dir / filename
    output_path.write_text(markdown)

    # Update index
    _update_index(category, title, tags, str(output_path))

    return str(output_path)


def search(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> str:
    """Search notes and knowledge entries.

    Args:
        query: Search query string
        category: Optional category filter
        limit: Maximum number of results

    Returns:
        Markdown-formatted search results
    """
    results = []
    query_lower = query.lower()

    # Determine which categories to search
    if category:
        categories = [category.lower()]
    else:
        categories = ["patterns", "solutions", "errors", "techniques", "notes"]

    for cat in categories:
        knowledge_dir = PRJ_DATA("knowledge", "harvested", cat)
        if not knowledge_dir.exists():
            continue

        for md_file in knowledge_dir.glob("*.md"):
            content = md_file.read_text().lower()
            if query_lower in content:
                # Extract title from frontmatter
                frontmatter = _parse_frontmatter(md_file.read_text())
                title = frontmatter.get("title", md_file.stem)

                if len(results) < limit:
                    results.append(
                        {
                            "category": cat,
                            "title": title,
                            "path": str(md_file),
                            "tags": frontmatter.get("tags", []),
                        }
                    )

    # Format results
    if not results:
        return f"No results found for '{query}'"

    markdown = f"""# Search Results: "{query}"

Found {len(results)} matching entries:

"""

    for i, result in enumerate(results, 1):
        markdown += f"## {i}. {result['title']}\n\n"
        markdown += f"**Category**: {result['category']}\n\n"
        markdown += f"**Path**: `{result['path']}`\n\n"
        if result["tags"]:
            markdown += f"**Tags**: {' '.join(f'`{t}`' for t in result['tags'])}\n\n"
        markdown += "---\n\n"

    return markdown


def _update_index(category: str, title: str, tags: list[str], path: str) -> None:
    """Update the knowledge index for a category."""
    index_dir = PRJ_DATA("knowledge", "index")
    index_dir.mkdir(parents=True, exist_ok=True)

    index_file = index_dir / f"{category}.json"

    # Load existing index or create new
    if index_file.exists():
        import json

        index = json.loads(index_file.read_text())
    else:
        index = {"entries": []}

    # Add new entry
    entry = {
        "title": title,
        "tags": tags,
        "path": path,
        "added": datetime.utcnow().isoformat(),
    }
    index["entries"].append(entry)

    # Write updated index
    import json

    index_file.write_text(json.dumps(index, indent=2))


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content."""
    frontmatter = {}

    if content.startswith("---"):
        # Extract frontmatter block
        end_marker = content.find("---", 3)
        if end_marker != -1:
            yaml_content = content[3:end_marker].strip()
            # Simple YAML parsing for basic key-value pairs
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle list values
                    if value.startswith("[") and value.endswith("]"):
                        value = value[1:-1].replace('"', "").split(",")
                        value = [v.strip().strip("'\"") for v in value if v.strip()]

                    frontmatter[key] = value

    return frontmatter
