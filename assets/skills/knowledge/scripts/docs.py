"""
Knowledge Documentation Commands

Commands:
- create_knowledge_entry: Create a new standardized knowledge entry
- rebuild_knowledge_index: Rebuild the knowledge base index
"""

import datetime
from pathlib import Path

import structlog

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.dirs import get_harvest_dir

logger = structlog.get_logger(__name__)


@skill_command(
    name="create_knowledge_entry",
    category="write",
    description="""
    Create a new standardized knowledge entry in assets/knowledge/harvested/.

    Args:
        - title: str - Human readable title (e.g., Fixing Deadlocks) (required)
        - category: str - One of [architecture, debugging, pattern, workflow] (required)
        - content: str - The Markdown content (header is auto-generated) (required)

    Returns:
        Success message with filename.
    """,
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
        # Get harvest directory using get_harvest_dir (SSOT)
        harvest_dir = get_harvest_dir(category)
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

        # 5. Return complete result for LLM (CLI display handles truncation)
        return (
            f"[{category.upper()}] {title}\n-> {filename}\n-> Content length: {len(content)} chars"
        )
    except Exception as e:
        logger.error("Failed to create knowledge entry", error=str(e))
        raise


@skill_command(
    name="rebuild_knowledge_index",
    category="write",
    description="""
    Scan all markdown files in assets/knowledge and update the main README.md index.

    Call this after adding or deleting files.

    Args:
        - None

    Returns:
        Success message with entry count.
    """,
)
async def rebuild_knowledge_index() -> str:
    """
    Scan all markdown files in assets/knowledge and update the main README.md index.
    Call this after adding or deleting files.
    """
    try:
        index_lines = [
            "# Knowledge Base Index",
            "",
            "| Date | Category | Title | File |",
            "|---|---|---|---|",
        ]

        # Get knowledge directory using get_harvest_dir
        harvest_dir = get_harvest_dir()
        if harvest_dir.exists():
            # Recursively find all markdown files in subdirectories
            for cat_dir in harvest_dir.iterdir():
                if cat_dir.is_dir():
                    for f in cat_dir.glob("*.md"):
                        # Parse filename: YYYYMMDD-category-title.md
                        parts = f.stem.split("-", 2)
                        if len(parts) >= 3:
                            date, cat, file_title = (
                                parts[0],
                                parts[1],
                                parts[2].replace("-", " ").title(),
                            )
                            link = f"harvested/{cat}/{f.name}"
                            index_lines.append(
                                f"| {date} | {cat} | {file_title} | [`{f.name}`]({link}) |"
                            )

        # Update README
        readme_path = harvest_dir.parent / "README.md"
        readme_path.write_text("\n".join(index_lines), encoding="utf-8")

        return f"Index rebuilt. Found {len(index_lines) - 4} entries."
    except Exception as e:
        logger.error("Failed to rebuild knowledge index", error=str(e))
        raise


__all__ = [
    "create_knowledge_entry",
    "rebuild_knowledge_index",
]
