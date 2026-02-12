"""
zk_integration.py - Zettelkasten integration for knowledge graph.

Uses zk CLI tool for managing bidirectional links and note relationships.

Usage:
    from omni.rag.zk_integration import ZkClient, ZkNote

    client = ZkClient("/path/to/notebook")
    notes = await client.search("python")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .zk_client import ZkClient as NewZkClient, ZkNote

logger = logging.getLogger(__name__)


class ZkClient(NewZkClient):
    """Client for interacting with zk CLI tool.

    Inherits from zk_client.ZkClient (full-featured async wrapper).
    """

    pass


@dataclass
class ZkLink:
    """Represents a link between notes."""

    source: str
    source_title: str
    target: str
    target_title: str
    link_type: str = "wiki"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZkLink":
        return cls(
            source=data.get("source", ""),
            source_title=data.get("sourceTitle", ""),
            target=data.get("target", ""),
            target_title=data.get("targetTitle", ""),
            link_type=data.get("type", "wiki"),
        )


@dataclass
class ZkEntityRef:
    """Represents a reference from zk note to code entity."""

    entity_name: str
    entity_type: str | None = None
    note_id: str | None = None
    note_title: str | None = None

    def to_wikilink(self) -> str:
        if self.entity_type:
            return f"[[{self.entity_name}#{self.entity_type}]]"
        return f"[[{self.entity_name}]]"

    def to_tag(self) -> str:
        if self.entity_type:
            return f"#entity-{self.entity_type.lower()}"
        return "#entity"


@dataclass
class RustEntityZkRef:
    """Represents a Rust Graph entity with zk note links."""

    name: str
    entity_type: str
    description: str

    zk_note_id: str | None = None
    zk_note_path: str | None = None
    zk_note_title: str | None = None

    referenced_by_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "zk_note_id": self.zk_note_id,
            "zk_note_path": self.zk_note_path,
            "zk_note_title": self.zk_note_title,
            "referenced_by_notes": self.referenced_by_notes,
        }


def get_zk_client(notebook_dir: str | None = None) -> ZkClient:
    """Get a zk client for the notebook.

    Args:
        notebook_dir: Optional notebook directory.

    Returns:
        ZkClient instance.
    """
    return ZkClient(notebook_dir)


__all__ = [
    "ZkNote",
    "ZkClient",
    "ZkLink",
    "ZkEntityRef",
    "RustEntityZkRef",
    "get_zk_client",
]
