"""Graph navigation over notebook knowledge using the common LinkGraph backend."""

from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omni.rag.link_graph import LinkGraphDirection, get_link_graph_backend

logger = logging.getLogger(__name__)


@dataclass
class NavigationConfig:
    """Configuration for graph navigation."""

    # Anchor settings
    anchor_limit: int = 3
    anchor_sort: list[str] = field(default_factory=lambda: ["match-"])

    # Expansion settings
    max_backlinks: int = 5
    max_outlinks: int = 5
    recursive_depth: int = 1
    max_total_notes: int = 20

    # Filtering
    created_after: str | None = None
    include_content: bool = True
    content_preview_len: int = 200


class LinkGraphNavigator:
    """
    Graph-based reasoning search navigator over LinkGraph.

    Implements "Anchor & Expand" retrieval:
    - Anchor: find entry nodes via graph search
    - Expand: traverse incoming/outgoing neighbors
    - Format: output XML context blocks for prompt injection
    """

    def __init__(
        self,
        backend: Any | None = None,
        *,
        notebook_dir: str | Path | None = None,
        config: NavigationConfig | None = None,
    ) -> None:
        """Initialize navigator from backend or notebook path."""
        if backend is None:
            resolved = str(Path(notebook_dir).resolve()) if notebook_dir else None
            backend = get_link_graph_backend(notebook_dir=resolved)
        self.backend = backend
        self.config = config or NavigationConfig()

    @staticmethod
    def _esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    @staticmethod
    def _extract_planned_hits(payload: Any) -> list[Any]:
        if not isinstance(payload, dict):
            return []
        hits = payload.get("hits")
        return hits if isinstance(hits, list) else []

    async def get_holographic_context(self, query: str, max_nodes: int | None = None) -> str:
        """Build XML context around anchor hits for query."""
        cap = max(1, int(max_nodes or self.config.max_total_notes))
        anchors = await self._find_anchors(query)
        if not anchors:
            return "<knowledge_graph>\n  <empty/>\n</knowledge_graph>"

        xml = "<knowledge_graph>\n"
        for anchor in anchors[:cap]:
            xml += self._build_node_xml(anchor)
        xml += "</knowledge_graph>"
        return xml

    async def get_subgraph(
        self,
        note_ids: list[str],
        max_backlinks: int | None = None,
        max_outlinks: int | None = None,
    ) -> str:
        """Build one-hop subgraph XML for given note ids."""
        in_limit = max(1, int(max_backlinks or self.config.max_backlinks))
        out_limit = max(1, int(max_outlinks or self.config.max_outlinks))

        xml = "<knowledge_subgraph>\n"
        for note_id in note_ids:
            center = str(note_id or "").strip()
            if not center:
                continue
            incoming, outgoing = await asyncio.gather(
                self.backend.neighbors(
                    center,
                    direction=LinkGraphDirection.INCOMING,
                    hops=1,
                    limit=in_limit,
                ),
                self.backend.neighbors(
                    center,
                    direction=LinkGraphDirection.OUTGOING,
                    hops=1,
                    limit=out_limit,
                ),
            )

            xml += f'  <center id="{self._esc(center)}">\n'
            if incoming:
                xml += "    <referenced_by>\n"
                for note in incoming[:in_limit]:
                    stem = self._esc(getattr(note, "stem", ""))
                    title = self._esc(getattr(note, "title", "") or getattr(note, "stem", ""))
                    xml += f'      <link id="{stem}">{title}</link>\n'
                xml += "    </referenced_by>\n"
            if outgoing:
                xml += "    <references>\n"
                for note in outgoing[:out_limit]:
                    stem = self._esc(getattr(note, "stem", ""))
                    title = self._esc(getattr(note, "title", "") or getattr(note, "stem", ""))
                    xml += f'      <link id="{stem}">{title}</link>\n'
                xml += "    </references>\n"
            xml += "  </center>\n"

        xml += "</knowledge_subgraph>"
        return xml

    async def get_related_context(
        self,
        note_id: str,
        depth: int = 2,
        limit_per_level: int = 10,
    ) -> str:
        """Build recursive related-context XML by traversing neighbors."""
        max_depth = max(1, int(depth))
        per_level = max(1, int(limit_per_level))

        center = str(note_id or "").strip()
        context_xml = f'<related_context center="{self._esc(center)}" depth="{max_depth}">\n'

        visited: set[str] = set()
        current_level = [center]
        level = 0

        while level < max_depth and current_level:
            next_level: list[str] = []
            context_xml += f'  <level n="{level}">\n'

            for nid in current_level:
                clean_id = str(nid or "").strip()
                if not clean_id or clean_id in visited:
                    continue
                visited.add(clean_id)

                incoming, outgoing = await asyncio.gather(
                    self.backend.neighbors(
                        clean_id,
                        direction=LinkGraphDirection.INCOMING,
                        hops=1,
                        limit=per_level,
                    ),
                    self.backend.neighbors(
                        clean_id,
                        direction=LinkGraphDirection.OUTGOING,
                        hops=1,
                        limit=per_level,
                    ),
                )

                context_xml += f'    <node id="{self._esc(clean_id)}">\n'

                if incoming:
                    context_xml += "      <from>\n"
                    for note in incoming[:per_level]:
                        target = str(getattr(note, "stem", "") or "").strip()
                        if target and target not in visited:
                            next_level.append(target)
                        context_xml += (
                            f'        <link id="{self._esc(target)}">'
                            f"{self._esc(getattr(note, 'title', '') or target)}</link>\n"
                        )
                    context_xml += "      </from>\n"

                if outgoing:
                    context_xml += "      <to>\n"
                    for note in outgoing[:per_level]:
                        target = str(getattr(note, "stem", "") or "").strip()
                        if target and target not in visited:
                            next_level.append(target)
                        context_xml += (
                            f'        <link id="{self._esc(target)}">'
                            f"{self._esc(getattr(note, 'title', '') or target)}</link>\n"
                        )
                    context_xml += "      </to>\n"

                context_xml += "    </node>\n"

            context_xml += "  </level>\n"
            current_level = next_level
            level += 1

        context_xml += "</related_context>"
        return context_xml

    async def _find_anchors(self, query: str) -> list[dict[str, Any]]:
        """Find anchor nodes and enrich with metadata tags."""
        planned_payload = await self.backend.search_planned(
            query, limit=max(1, int(self.config.anchor_limit))
        )
        hits = self._extract_planned_hits(planned_payload)
        out: list[dict[str, Any]] = []
        for hit in hits:
            stem = str(getattr(hit, "stem", "") or "").strip()
            if not stem:
                continue
            title = str(getattr(hit, "title", "") or stem)
            path = str(getattr(hit, "path", "") or "")
            tags: list[str] = []
            try:
                meta = await self.backend.metadata(stem)
            except Exception:
                meta = None
            if meta is not None:
                raw = getattr(meta, "tags", []) or []
                tags = [str(tag) for tag in raw if str(tag).strip()]
            out.append(
                {
                    "id": stem,
                    "title": title,
                    "path": path,
                    "tags": tags,
                    "preview": "",
                }
            )
        return out

    def _build_node_xml(self, note: dict[str, Any]) -> str:
        """Build XML for one anchor node."""
        note_id = self._esc(note.get("id"))
        title = self._esc(note.get("title"))
        preview = self._esc(note.get("preview") or "")
        tags_raw = note.get("tags")
        tags = tags_raw if isinstance(tags_raw, list) else []
        tags_csv = self._esc(",".join(str(tag) for tag in tags))

        return (
            f'  <node id="{note_id}" title="{title}">\n'
            f"    <preview>{preview}</preview>\n"
            f"    <tags>{tags_csv}</tags>\n"
            "  </node>\n"
        )

    def format_as_xml(
        self,
        anchors: list[dict[str, Any]],
        backlinks: dict[str, list[dict[str, Any]]],
        outlinks: dict[str, list[dict[str, Any]]],
    ) -> str:
        """Format explicit anchors/backlinks/outlinks payloads as XML."""
        xml = "<knowledge_graph>\n"
        for anchor in anchors:
            note_id = str(anchor.get("id") or "").strip()
            title = str(anchor.get("title") or "")
            xml += f'  <node id="{self._esc(note_id)}" title="{self._esc(title)}">\n'

            anchor_backlinks = backlinks.get(note_id, [])
            if anchor_backlinks:
                xml += "    <referenced_by>\n"
                for note in anchor_backlinks[: self.config.max_backlinks]:
                    nid = self._esc(note.get("id"))
                    ntitle = self._esc(note.get("title") or note.get("id"))
                    xml += f'      <link id="{nid}">{ntitle}</link>\n'
                xml += "    </referenced_by>\n"

            anchor_outlinks = outlinks.get(note_id, [])
            if anchor_outlinks:
                xml += "    <references>\n"
                for note in anchor_outlinks[: self.config.max_outlinks]:
                    nid = self._esc(note.get("id"))
                    ntitle = self._esc(note.get("title") or note.get("id"))
                    xml += f'      <link id="{nid}">{ntitle}</link>\n'
                xml += "    </references>\n"

            if self.config.include_content:
                preview = self._esc(anchor.get("preview") or "")
                xml += f"    <preview>{preview}</preview>\n"

            xml += "  </node>\n"

        xml += "</knowledge_graph>"
        return xml


def get_link_graph_navigator(
    backend: Any | None = None,
    *,
    notebook_dir: str | Path | None = None,
    config: NavigationConfig | None = None,
) -> LinkGraphNavigator:
    """Factory function for `LinkGraphNavigator`."""
    return LinkGraphNavigator(backend=backend, notebook_dir=notebook_dir, config=config)


__all__ = [
    "LinkGraphNavigator",
    "NavigationConfig",
    "get_link_graph_navigator",
]
