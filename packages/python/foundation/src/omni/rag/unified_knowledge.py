"""Unified knowledge manager built on common LinkGraph backend."""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omni.rag.link_graph import LinkGraphDirection, get_link_graph_backend

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class UnifiedEntity:
    """Entity representation compatible with LinkGraph notes."""

    name: str
    entity_type: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    note_id: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None

    def to_note_content(self) -> str:
        """Generate markdown content for note creation."""
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
    """Manager using common LinkGraph APIs."""

    def __init__(
        self,
        notebook_dir: str | Path | None = None,
        backend: Any | None = None,
    ):
        """Initialize manager.

        Args:
            notebook_dir: Notebook directory.
            backend: Optional LinkGraph backend override.
        """
        self.notebook_dir = Path(notebook_dir) if notebook_dir else Path.cwd()
        self.backend = backend or get_link_graph_backend(notebook_dir=str(self.notebook_dir))

        logger.info("Initialized UnifiedKnowledgeManager at %s", self.notebook_dir)

    @staticmethod
    def _resolve_result(value: Any) -> Any:
        """Resolve maybe-awaitable result into concrete value."""
        if not inspect.isawaitable(value):
            return value

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(value)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, value).result()

    @staticmethod
    def _extract_planned_hits(payload: Any) -> list[Any]:
        """Extract hit list from search_planned payload."""
        if not isinstance(payload, dict):
            return []
        hits = payload.get("hits")
        return hits if isinstance(hits, list) else []

    @staticmethod
    def _extract_note_id(note: Any) -> str:
        """Best-effort extraction for note id/stem from backend writer result."""
        if isinstance(note, dict):
            for key in ("id", "stem", "filename_stem", "filenameStem"):
                value = str(note.get(key) or "").strip()
                if value:
                    return value
            path_value = str(note.get("path") or "").strip()
            if path_value:
                return Path(path_value).stem
            return ""

        for attr in ("id", "stem", "filename_stem", "filenameStem"):
            value = str(getattr(note, attr, "") or "").strip()
            if value:
                return value

        path_value = str(getattr(note, "path", "") or "").strip()
        if path_value:
            return Path(path_value).stem
        return ""

    @staticmethod
    def _extract_note_time(note: Any, *keys: str) -> Any:
        """Best-effort extraction for note timestamps from writer result."""
        if isinstance(note, dict):
            for key in keys:
                value = note.get(key)
                if value is not None:
                    return value
            return None

        for key in keys:
            value = getattr(note, key, None)
            if value is not None:
                return value
        return None

    def add_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        aliases: list[str] | None = None,
    ) -> UnifiedEntity:
        """Add entity to LinkGraph notebook.

        Args:
            name: Entity name.
            entity_type: Entity type (SKILL, TOOL, etc.).
            description: Entity description.
            aliases: Alternative names.

        Returns:
            UnifiedEntity with note metadata.
        """
        entity = UnifiedEntity(
            name=name,
            entity_type=entity_type.upper(),
            description=description,
            aliases=aliases or [],
        )

        # Check if exists using common link graph search first.
        try:
            existing_payload = self._resolve_result(self.backend.search_planned(name, limit=1))
            existing_hits = self._extract_planned_hits(existing_payload)
        except Exception:
            existing_hits = []
        if isinstance(existing_hits, list) and existing_hits:
            first = existing_hits[0]
            entity.note_id = str(getattr(first, "stem", "") or "")
            if entity.note_id:
                logger.debug("Found existing note via link_graph: %s", name)
                return entity

        # Create new note through backend writer API when available.
        content = entity.to_note_content()
        create_note = getattr(self.backend, "create_note", None)
        if not callable(create_note):
            logger.warning(
                "UnifiedKnowledgeManager add_entity skipped create_note; backend writer unavailable"
            )
            return entity

        try:
            note = self._resolve_result(
                create_note(
                    title=name,
                    body=content,
                    tags=[entity.entity_type.lower()],
                )
            )
        except Exception as exc:
            logger.warning("UnifiedKnowledgeManager add_entity create_note failed: %s", exc)
            return entity

        if note:
            entity.note_id = self._extract_note_id(note)
            entity.created_at = self._extract_note_time(note, "created")
            entity.modified_at = self._extract_note_time(note, "modified")
            logger.info("Created note via backend: %s", name)

        return entity

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search using common LinkGraph backend.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            Dict with search results.
        """
        planned_query = str(query or "")
        try:
            planned_payload = self._resolve_result(
                self.backend.search_planned(query, limit=max(1, int(limit)))
            )
            if isinstance(planned_payload, dict):
                planned_query = str(planned_payload.get("query") or query)
            hits = self._extract_planned_hits(planned_payload)
        except Exception:
            hits = []

        notes: list[dict[str, Any]] = []
        for hit in hits if isinstance(hits, list) else []:
            stem = str(getattr(hit, "stem", "") or "").strip()
            title = str(getattr(hit, "title", "") or "")
            path = str(getattr(hit, "path", "") or "")
            score = float(getattr(hit, "score", 0.0) or 0.0)
            tags: list[str] = []
            if stem:
                try:
                    metadata = self._resolve_result(self.backend.metadata(stem))
                except Exception:
                    metadata = None
                if metadata is not None:
                    raw_tags = getattr(metadata, "tags", []) or []
                    tags = [str(tag) for tag in raw_tags if str(tag).strip()]

            notes.append(
                {
                    "id": stem,
                    "title": title,
                    "path": path,
                    "snippet": "",
                    "tags": tags,
                    "score": score,
                }
            )
        return {
            "query": query,
            "parsed_query": planned_query,
            "notes": notes,
            "total": len(notes),
        }

    def get_graph(self, limit: int = 100) -> dict[str, Any]:
        """Get graph using common LinkGraph backend.

        Args:
            limit: Maximum nodes.

        Returns:
            Graph with nodes and links.
        """
        max_nodes = max(1, int(limit))
        try:
            toc_rows = self._resolve_result(self.backend.toc(limit=max_nodes))
        except Exception:
            toc_rows = []

        nodes: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        for row in toc_rows if isinstance(toc_rows, list) else []:
            if not isinstance(row, dict):
                continue
            stem = str(row.get("id") or "").strip()
            if not stem or stem in node_ids:
                continue
            node_ids.add(stem)
            raw_tags = row.get("tags", [])
            tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
            nodes.append(
                {
                    "id": stem,
                    "title": str(row.get("title") or ""),
                    "path": str(row.get("path") or ""),
                    "tags": tags,
                }
            )

        links: list[dict[str, str]] = []
        seen_links: set[tuple[str, str]] = set()
        for node in nodes:
            source = node["id"]
            try:
                neighbors = self._resolve_result(
                    self.backend.neighbors(
                        source,
                        direction=LinkGraphDirection.OUTGOING,
                        hops=1,
                        limit=max_nodes,
                    )
                )
            except Exception:
                neighbors = []

            for neighbor in neighbors if isinstance(neighbors, list) else []:
                target = str(getattr(neighbor, "stem", "") or "").strip()
                if not target:
                    continue
                key = (source, target)
                if key in seen_links:
                    continue
                seen_links.add(key)
                links.append({"source": source, "target": target})

        return {"nodes": nodes, "links": links}

    def find_related(self, note_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find related notes using common LinkGraph backend.

        Args:
            note_id: Note filename stem.
            limit: Maximum results.

        Returns:
            List of related notes.
        """
        try:
            related = self._resolve_result(
                self.backend.related(note_id, max_distance=2, limit=max(1, int(limit)))
            )
        except Exception:
            related = []
        out: list[dict[str, Any]] = []
        for item in related if isinstance(related, list) else []:
            out.append(
                {
                    "id": str(getattr(item, "stem", "") or ""),
                    "title": str(getattr(item, "title", "") or ""),
                    "path": str(getattr(item, "path", "") or ""),
                }
            )
        return out

    def get_stats(self) -> dict[str, Any]:
        """Get statistics using common LinkGraph backend."""
        try:
            stats = self._resolve_result(self.backend.stats())
            return stats if isinstance(stats, dict) else {}
        except Exception:
            return {}

    def list_by_tag(self, tag: str, limit: int = 100) -> list[dict[str, Any]]:
        """List notes by tag using common LinkGraph ToC rows.

        Args:
            tag: Tag to search.
            limit: Maximum results.

        Returns:
            List of notes with the tag.
        """
        target = str(tag or "").strip().lower()
        if not target:
            return []

        scan_limit = max(1, int(limit)) * 5
        try:
            toc_rows = self._resolve_result(self.backend.toc(limit=scan_limit))
        except Exception:
            toc_rows = []

        out: list[dict[str, Any]] = []
        for row in toc_rows if isinstance(toc_rows, list) else []:
            if not isinstance(row, dict):
                continue
            raw_tags = row.get("tags", [])
            tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            normalized = {t.strip().lower() for t in tags if t.strip()}
            if target not in normalized:
                continue
            out.append(
                {
                    "id": str(row.get("id") or ""),
                    "title": str(row.get("title") or ""),
                    "path": str(row.get("path") or ""),
                    "snippet": "",
                    "tags": tags,
                }
            )
            if len(out) >= max(1, int(limit)):
                break
        return out


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
