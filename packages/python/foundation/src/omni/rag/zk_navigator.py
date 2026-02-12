"""
zk_navigator.py - Graph-Based Reasoning Search for Knowledge Navigation

Provides holographic context retrieval using zk's bidirectional links:
1. Anchor: Find core notes matching the query
2. Expand: Traverse bidirectional links recursively
3. Filter: Apply date/content filters if needed
4. Format: Output as structured XML for LLM prompt injection

Usage:
    from omni.rag.zk_navigator import ZkGraphNavigator

    navigator = ZkGraphNavigator(client)
    context = await navigator.get_holographic_context("python async patterns")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .zk_client import ZkClient, ZkNote

logger = logging.getLogger(__name__)


@dataclass
class NavigationConfig:
    """Configuration for graph navigation."""

    # Anchor settings
    anchor_limit: int = 3
    anchor_sort: List[str] = field(default_factory=lambda: ["match-"])

    # Expansion settings
    max_backlinks: int = 5
    max_outlinks: int = 5
    recursive_depth: int = 1
    max_total_notes: int = 20

    # Filtering
    created_after: Optional[str] = None
    include_content: bool = True
    content_preview_len: int = 200


class ZkGraphNavigator:
    """
    Graph-based reasoning search navigator.

    Implements "Anchor & Expand" pattern for knowledge retrieval:
    - Anchor: Find entry points via full-text search
    - Expand: Traverse bidirectional links to build context
    - Format: Output structured context for LLM consumption
    """

    def __init__(
        self,
        client: ZkClient,
        config: Optional[NavigationConfig] = None,
    ) -> None:
        """Initialize navigator.

        Args:
            client: ZkClient instance.
            config: Navigation configuration.
        """
        self.client = client
        self.config = config or NavigationConfig()

    async def get_holographic_context(self, query: str, max_nodes: Optional[int] = None) -> str:
        """Get holographic context for query.

        Builds a local subgraph around relevant notes:
        1. Find anchor nodes (core matching notes)
        2. Expand to neighbors (backlinks + outlinks)
        3. Format as XML for LLM prompt injection

        Args:
            query: Search query.
            max_nodes: Maximum nodes to include.

        Returns:
            XML-formatted knowledge context.
        """
        max_nodes = max_nodes or self.config.max_total_notes

        # Step 1: Anchor - Find core nodes
        anchors = await self._find_anchors(query)

        if not anchors:
            return "<knowledge_graph>\n  <empty/>\n</knowledge_graph>"

        context_xml = "<knowledge_graph>\n"

        # Step 2: Expand - Build local subgraph
        for anchor in anchors[:max_nodes]:
            node_xml = self._build_node_xml(anchor)
            context_xml += node_xml

        context_xml += "</knowledge_graph>"
        return context_xml

    async def get_subgraph(
        self,
        note_ids: List[str],
        max_backlinks: Optional[int] = None,
        max_outlinks: Optional[int] = None,
    ) -> str:
        """Build subgraph around specific notes.

        Args:
            note_ids: Starting note IDs.
            max_backlinks: Maximum backlinks per node.
            max_outlinks: Maximum outlinks per node.

        Returns:
            XML-formatted subgraph.
        """
        max_backlinks = max_backlinks or self.config.max_backlinks
        max_outlinks = max_outlinks or self.config.max_outlinks

        context_xml = "<knowledge_subgraph>\n"

        for note_id in note_ids:
            # Get backlinks
            backlinks = await self.client.find_linked_by(note_id, limit=max_backlinks)

            # Get outlinks
            outlinks = await self.client.find_link_to(note_id, limit=max_outlinks)

            context_xml += f'  <center id="{note_id}">\n'

            if backlinks:
                context_xml += "    <referenced_by>\n"
                for note in backlinks:
                    context_xml += f'      <link id="{note.filename_stem}">{note.title}</link>\n'
                context_xml += "    </referenced_by>\n"

            if outlinks:
                context_xml += "    <references>\n"
                for note in outlinks:
                    context_xml += f'      <link id="{note.filename_stem}">{note.title}</link>\n'
                context_xml += "    </references>\n"

            context_xml += "  </center>\n"

        context_xml += "</knowledge_subgraph>"
        return context_xml

    async def get_related_context(
        self, note_id: str, depth: int = 2, limit_per_level: int = 10
    ) -> str:
        """Get recursively related context.

        Args:
            note_id: Starting note ID.
            depth: Recursion depth.
            limit_per_level: Maximum notes per level.

        Returns:
            XML-formatted recursive context.
        """
        context_xml = f'<related_context center="{note_id}" depth="{depth}">\n'

        visited = set()
        current_level = [note_id]
        level = 0

        while level < depth and current_level:
            next_level = []
            context_xml += f'  <level n="{level}">\n'

            for nid in current_level:
                if nid in visited:
                    continue
                visited.add(nid)

                # Get neighbors
                linked_by = await self.client.find_linked_by(nid, limit=limit_per_level)
                link_to = await self.client.find_link_to(nid, limit=limit_per_level)

                context_xml += f'    <node id="{nid}">\n'

                if linked_by:
                    context_xml += "      <from>\n"
                    for note in linked_by:
                        if note.filename_stem not in visited:
                            next_level.append(note.filename_stem)
                        context_xml += (
                            f'        <link id="{note.filename_stem}">{note.title}</link>\n'
                        )
                    context_xml += "      </from>\n"

                if link_to:
                    context_xml += "      <to>\n"
                    for note in link_to:
                        if note.filename_stem not in visited:
                            next_level.append(note.filename_stem)
                        context_xml += (
                            f'        <link id="{note.filename_stem}">{note.title}</link>\n'
                        )
                    context_xml += "      </to>\n"

                context_xml += "    </node>\n"

            context_xml += "  </level>\n"
            current_level = next_level
            level += 1

        context_xml += "</related_context>"
        return context_xml

    async def _find_anchors(self, query: str) -> List[ZkNote]:
        """Find anchor nodes for the query.

        Args:
            query: Search query.

        Returns:
            List of anchor notes.
        """
        return await self.client.list_notes(
            match=query,
            limit=self.config.anchor_limit,
            sort=self.config.anchor_sort,
        )

    def _build_node_xml(self, note: ZkNote) -> str:
        """Build XML for a single node and its neighbors.

        Args:
            note: Anchor note.

        Returns:
            XML string for the node.
        """
        # Note: We can't use await here, so this is a sync helper
        # Callers should use the async methods directly if they need neighbors
        preview = ""
        if self.config.include_content and note.raw_content:
            preview = note.raw_content[: self.config.content_preview_len]

        return f"""  <node id="{note.filename_stem or note.path}" title="{note.title}">
    <preview>{preview}</preview>
    <tags>{",".join(note.tags)}</tags>
  </node>
"""

    def format_as_xml(
        self,
        anchors: List[ZkNote],
        backlinks: Dict[str, List[ZkNote]],
        outlinks: Dict[str, List[ZkNote]],
    ) -> str:
        """Format nodes and links as XML.

        Args:
            anchors: Anchor notes.
            backlinks: Map of note_id -> linking notes.
            outlinks: Map of note_id -> linked notes.

        Returns:
            XML-formatted context.
        """
        xml = "<knowledge_graph>\n"

        for anchor in anchors:
            note_id = anchor.filename_stem or anchor.path

            xml += f'  <node id="{note_id}" title="{anchor.title}">\n'

            # Backlinks
            anchor_backlinks = backlinks.get(note_id, [])
            if anchor_backlinks:
                xml += "    <referenced_by>\n"
                for note in anchor_backlinks[: self.config.max_backlinks]:
                    xml += f'      <link id="{note.filename_stem}">{note.title}</link>\n'
                xml += "    </referenced_by>\n"

            # Outlinks
            anchor_outlinks = outlinks.get(note_id, [])
            if anchor_outlinks:
                xml += "    <references>\n"
                for note in anchor_outlinks[: self.config.max_outlinks]:
                    xml += f'      <link id="{note.filename_stem}">{note.title}</link>\n'
                xml += "    </references>\n"

            # Preview
            if self.config.include_content and anchor.raw_content:
                preview = anchor.raw_content[: self.config.content_preview_len]
                xml += f"    <preview>{preview}</preview>\n"

            xml += "  </node>\n"

        xml += "</knowledge_graph>"
        return xml


def get_zk_navigator(
    client: ZkClient, config: Optional[NavigationConfig] = None
) -> ZkGraphNavigator:
    """Factory function for ZkGraphNavigator.

    Args:
        client: ZkClient instance.
        config: Navigation configuration.

    Returns:
        ZkGraphNavigator instance.
    """
    return ZkGraphNavigator(client, config)


__all__ = [
    "NavigationConfig",
    "ZkGraphNavigator",
    "get_zk_navigator",
]
