"""
Knowledge Search Commands - Simplified

Commands:
- knowledge_status: Check the status of the knowledge base indexing.

Note:
- search (unified text search) - see search.py
- recall (semantic search) - see recall.py
"""

from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.knowledge.search")


@skill_command(
    name="knowledge_status",
    category="system",
    description="Check the status of the knowledge base indexing.",
    autowire=True,
)
async def knowledge_status() -> dict[str, Any]:
    """Get knowledge base status."""
    from omni.core.runtime.services import get_librarian

    librarian = get_librarian()

    if librarian is None:
        return {
            "status": "offline",
            "message": "Librarian service not initialized.",
            "hint": "Ensure SkillManager is started with ingest_knowledge=True",
        }

    try:
        stats = librarian.get_stats()
        manifest = librarian.get_manifest_status()

        return {
            "status": "online",
            "indexed_files": manifest.get("tracked_files", 0),
            "total_chunks": stats.get("record_count", 0),
            "table": stats.get("table", "unknown"),
            "manifest_exists": manifest.get("manifest_exists", False),
            "manifest_path": manifest.get("manifest_path", ""),
        }

    except Exception as e:
        logger.error(f"Failed to get knowledge status: {e}")
        raise


__all__ = ["knowledge_status"]
