"""
unified_knowledge.py - zk Notebook Integration

Unified interface between code entities and zk notebook.
Uses zk's native capabilities for deduplication and linking.

Usage:
    from omni.rag.unified_knowledge import UnifiedKnowledgeManager

    ukm = UnifiedKnowledgeManager(notebook_dir="assets/knowledge")

    # Add entity - zk handles deduplication
    ukm.add_entity("Python", "SKILL", "Programming language")

    # Query using zk's native search
    results = ukm.search("python")

    # Get graph using zk
    graph = ukm.get_graph()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.rag.zk_integration import ZkClient, get_zk_client

logger = logging.getLogger(__name__)


@dataclass
class UnifiedEntity:
    """Entity representation compatible with zk notes."""

    name: str
    entity_type: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    zk_note_id: str | None = None
    zk_created: datetime | None = None
    zk_modified: datetime | None = None

    def to_zk_content(self) -> str:
        """Generate zk note content."""
        lines = [
            f"# {self.name}",
            "",
            f"> **Type**: {self.entity_type}",
            "",
            self.description,
            "",
        ]

        if self.aliases:
            lines.append(f"**Aliases**: {', '.join(self.aliases)}")
            lines.append("")

        lines.append(f"#{self.entity_type.lower()}")

        return "\n".join(lines)


class UnifiedKnowledgeManager:
    """Manager using zk's native capabilities."""

    def __init__(
        self,
        notebook_dir: str | Path | None = None,
        zk_client: ZkClient | None = None,
    ):
        """Initialize manager.

        Args:
            notebook_dir: zk notebook directory.
            zk_client: ZkClient instance.
        """
        self.notebook_dir = Path(notebook_dir) if notebook_dir else Path.cwd()
        self.zk_client = zk_client or get_zk_client(str(self.notebook_dir))

        logger.info(f"Initialized UnifiedKnowledgeManager at {self.notebook_dir}")

    def add_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        aliases: list[str] | None = None,
    ) -> UnifiedEntity:
        """Add entity to zk notebook.

        Args:
            name: Entity name.
            entity_type: Entity type (SKILL, TOOL, etc.).
            description: Entity description.
            aliases: Alternative names.

        Returns:
            UnifiedEntity with zk note info.
        """
        entity = UnifiedEntity(
            name=name,
            entity_type=entity_type.upper(),
            description=description,
            aliases=aliases or [],
        )

        # Check if exists using zk's search
        existing = self.zk_client.search_notes(name, limit=1)
        if existing:
            entity.zk_note_id = existing[0].filename_stem
            entity.zk_created = existing[0].created
            entity.zk_modified = existing[0].modified
            logger.debug(f"Found existing zk note: {name}")
            return entity

        # Create new note - zk handles deduplication
        content = entity.to_zk_content()
        note = self.zk_client.create_note(
            title=name,
            body=content,
            tags=[entity.entity_type.lower()],
        )

        if note:
            entity.zk_note_id = note.filename_stem
            entity.zk_created = note.created
            entity.zk_modified = note.modified
            logger.info(f"Created zk note: {name}")

        return entity

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search using zk's native search.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            Dict with search results.
        """
        notes = self.zk_client.search_notes(query, limit=limit)

        return {
            "query": query,
            "notes": [
                {
                    "title": n.title,
                    "path": n.path,
                    "snippet": n.lead or n.body[:200] if n.body else "",
                    "tags": n.tags,
                }
                for n in notes
            ],
            "total": len(notes),
        }

    def get_graph(self, limit: int = 100) -> dict[str, Any]:
        """Get graph using zk's native graph.

        Args:
            limit: Maximum nodes.

        Returns:
            Graph with nodes and links.
        """
        return self.zk_client.get_graph(limit=limit)

    def find_related(self, note_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find related notes using zk.

        Args:
            note_id: Note filename stem.
            limit: Maximum results.

        Returns:
            List of related notes.
        """
        related = self.zk_client.find_related(note_id, limit=limit)
        return [{"title": r.title, "path": r.path} for r in related]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics using zk's native stats."""
        return self.zk_client.get_stats()

    def list_by_tag(self, tag: str, limit: int = 100) -> list[dict[str, Any]]:
        """List notes by tag using zk search.

        Args:
            tag: Tag to search.
            limit: Maximum results.

        Returns:
            List of notes with the tag.
        """
        query = f"#{tag}"
        return self.search(query, limit=limit)["notes"]


# Convenience function
def get_unified_manager(
    notebook_dir: str | None = None,
) -> UnifiedKnowledgeManager:
    """Get a unified knowledge manager."""
    return UnifiedKnowledgeManager(notebook_dir=notebook_dir)


__all__ = [
    "UnifiedEntity",
    "UnifiedKnowledgeManager",
    "get_unified_manager",
]
