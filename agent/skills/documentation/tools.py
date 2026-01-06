"""
agent/skills/documentation/tools.py
Documentation Skill - Knowledge base management.

Phase 25: Omni CLI Architecture
Skill implementation with @skill_command decorators.
"""

import os
import datetime
from pathlib import Path
from typing import List, Optional
from common.gitops import get_project_root
import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# Get knowledge directory
root = get_project_root()
knowledge_dir = root / "agent" / "knowledge"


# =============================================================================
# Core Tools
# =============================================================================


@skill_command(
    name="documentation_create_knowledge_entry",
    category="write",
    description="Create a new standardized knowledge entry.",
)
async def create_knowledge_entry(title: str, category: str, content: str) -> str:
    """
    Create a new standardized knowledge entry.

    Args:
        title: Human readable title (e.g., "Fixing Deadlocks").
        category: One of [architecture, debugging, pattern, workflow].
        content: The Markdown content (excluding the header which is auto-generated).
    """
    try:
        # 1. Prepare Paths
        harvest_dir = knowledge_dir / "harvested"
        harvest_dir.mkdir(parents=True, exist_ok=True)

        # 2. Format Filename
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        slug = title.lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"{date_str}-{category}-{slug}.md"
        file_path = harvest_dir / filename

        # 3. Format Content
        full_content = f"# {title}\n\n> **Category**: {category.upper()} | **Date**: {datetime.datetime.now().strftime('%Y-%m-%d')}\n\n{content}\n"

        # 4. Write
        file_path.write_text(full_content, encoding="utf-8")

        return f"Created knowledge entry: {filename}"
    except Exception as e:
        return f"Failed to create doc: {e}"


@skill_command(
    name="documentation_rebuild_knowledge_index",
    category="write",
    description="Scan all markdown files and update the main README.md index.",
)
async def rebuild_knowledge_index() -> str:
    """
    Scan all markdown files in agent/knowledge and update the main README.md index.
    Call this after adding or deleting files.
    """
    try:
        index_lines = [
            "# Knowledge Base Index",
            "",
            "| Date | Category | Title | File |",
            "|---|---|---|---|",
        ]

        # Scan harvested
        harvest_dir = knowledge_dir / "harvested"
        if harvest_dir.exists():
            files = sorted(harvest_dir.glob("*.md"), reverse=True)
            for f in files:
                # Parse filename: YYYYMMDD-category-title.md
                parts = f.stem.split("-", 2)
                if len(parts) >= 3:
                    date, cat, title = parts[0], parts[1], parts[2].replace("-", " ").title()
                    link = f"harvested/{f.name}"
                    index_lines.append(f"| {date} | {cat} | {title} | [`{f.name}`]({link}) |")

        # Update README
        readme_path = knowledge_dir / "README.md"
        readme_path.write_text("\n".join(index_lines), encoding="utf-8")

        return f"Index rebuilt. Found {len(index_lines) - 4} entries."
    except Exception as e:
        return f"Failed to rebuild index: {e}"


@skill_command(
    name="documentation_search_knowledge_base",
    category="read",
    description="Simple text search across the knowledge base.",
)
async def search_knowledge_base(query: str) -> str:
    """
    Simple text search across the knowledge base.
    """
    results = []
    try:
        for f in knowledge_dir.rglob("*.md"):
            if "node_modules" in str(f) or ".git" in str(f):
                continue

            content = f.read_text(encoding="utf-8", errors="ignore")
            if query.lower() in content.lower():
                snippet = content[:200].replace("\n", " ")
                results.append(f"- **{f.name}**: {snippet}...")

        if not results:
            return f"No matches found for '{query}'."
        return f"Found {len(results)} matches:\n" + "\n".join(results[:10])
    except Exception as e:
        return f"Search error: {e}"
