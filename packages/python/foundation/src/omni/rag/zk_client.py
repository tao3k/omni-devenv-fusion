"""
zk_client.py - Full-Featured Asynchronous zk CLI Wrapper

Comprehensive wrapper for zk CLI providing all search capabilities:
- Full-text search (FTS, regex, exact)
- Graph operations (linked_by, link_to, mention, related)
- Date filtering with natural language support
- Recursive link traversal with distance limiting
- Multi-field sorting

Usage:
    from omni.rag.zk_client import ZkClient, ZkNote

    client = ZkClient("/path/to/notebook")
    notes = await client.list_notes(
        match="python",
        tags=["programming"],
        linked_by=["concept-a"],
        created_after="last week",
        sort=["modified-", "title+"],
        limit=10,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ZkNote:
    """Represents a note from zk list --format json output."""

    path: str
    abs_path: str
    title: str
    raw_content: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    link: str = ""
    lead: Optional[str] = None
    filename_stem: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    word_count: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZkNote":
        """Create ZkNote from zk JSON dictionary."""
        return cls(
            path=data.get("path", ""),
            abs_path=data.get("absPath", ""),
            title=data.get("title", "Untitled"),
            raw_content=data.get("body"),
            tags=data.get("tags", []),
            link=data.get("link", ""),
            lead=data.get("lead"),
            filename_stem=data.get("filenameStem"),
            created=data.get("created"),
            modified=data.get("modified"),
            word_count=data.get("wordCount"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "absPath": self.abs_path,
            "title": self.title,
            "body": self.raw_content,
            "tags": self.tags,
            "link": self.link,
            "lead": self.lead,
            "filenameStem": self.filename_stem,
            "created": self.created,
            "modified": self.modified,
            "wordCount": self.word_count,
        }


@dataclass
class ZkListConfig:
    """Complete configuration for zk list command."""

    # Core search
    match: Optional[str] = None
    match_strategy: str = "fts"  # fts, re, exact

    # Path filtering
    paths: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)

    # Tag filtering
    tags: List[str] = field(default_factory=list)
    tagless: bool = False
    orphan: bool = False

    # Graph operations
    link_to: List[str] = field(default_factory=list)
    linked_by: List[str] = field(default_factory=list)
    mention: List[str] = field(default_factory=list)
    mentioned_by: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)

    # Graph traversal
    recursive: bool = False
    max_distance: Optional[int] = None

    # Date filtering (natural language supported)
    created: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    modified: Optional[str] = None
    modified_after: Optional[str] = None
    modified_before: Optional[str] = None

    # Sorting (field+/- format)
    sort: List[str] = field(default_factory=list)

    # Output control
    limit: Optional[int] = None
    format_json: bool = True


class ZkClient:
    """
    Full-featured asynchronous zk CLI wrapper.

    Provides complete access to all zk CLI capabilities including:
    - Full-text search with multiple strategies
    - Graph-based link traversal
    - Date filtering with natural language parsing
    - Recursive neighbor discovery

    Attributes:
        bin_path: Path to zk executable.
        notebook_dir: Directory containing .zk/zk.toml.
    """

    def __init__(self, notebook_dir: Optional[Union[str, Path]] = None) -> None:
        """Initialize zk client.

        Args:
            notebook_dir: Directory containing .zk/zk.toml. Uses CWD if None.
        """
        bin_path = shutil.which("zk")
        if not bin_path:
            raise FileNotFoundError("zk binary not found in PATH")
        self.bin_path: str = bin_path

        self.notebook_dir = str(notebook_dir) if notebook_dir else None

    async def _run_command(self, args: List[str]) -> List[Dict[str, Any]]:
        """Execute zk command and parse JSON output.

        Args:
            args: Command arguments (without 'zk' prefix).

        Returns:
            List of parsed JSON objects from command output.
        """
        cmd = [self.bin_path] + args

        env = None
        if self.notebook_dir:
            env = os.environ.copy()
            env["ZK_NOTEBOOK_DIR"] = self.notebook_dir

        logger.debug(f"Executing zk command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"zk command failed: {error_msg}")
            raise RuntimeError(f"zk command failed: {error_msg}")

        output = stdout.decode().strip()
        if not output:
            return []

        # zk outputs JSON array or JSONL
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            results = []
            for line in output.splitlines():
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return results

    async def list_notes(
        self,
        match: Optional[str] = None,
        tags: Optional[List[str]] = None,
        link_to: Optional[List[str]] = None,
        linked_by: Optional[List[str]] = None,
        mention: Optional[List[str]] = None,
        mentioned_by: Optional[List[str]] = None,
        related: Optional[List[str]] = None,
        orphan: bool = False,
        tagless: bool = False,
        recursive: bool = False,
        max_distance: Optional[int] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        modified_after: Optional[str] = None,
        modified_before: Optional[str] = None,
        sort: Optional[List[str]] = None,
        limit: Optional[int] = None,
        match_strategy: str = "fts",
    ) -> List[ZkNote]:
        """List notes matching specified criteria.

        Args:
            match: Full-text search query.
            tags: Tags to filter by.
            link_to: Find notes linking to these paths.
            linked_by: Find notes linked by these paths.
            mention: Find notes mentioning titles of given paths.
            mentioned_by: Find notes whose titles are mentioned in given paths.
            related: Find notes related to given paths.
            orphan: Find notes with no backlinks.
            tagless: Find notes without tags.
            recursive: Follow links recursively.
            max_distance: Maximum link distance for recursive traversal.
            created_after: Filter by creation date (supports natural language).
            created_before: Filter by creation date.
            modified_after: Filter by modification date.
            modified_before: Filter by modification date.
            sort: Sort fields (e.g., ["modified-", "title+"]).
            limit: Maximum number of results.
            match_strategy: Search strategy (fts, re, exact).

        Returns:
            List of matching ZkNote objects.
        """
        try:
            config = ZkListConfig(
                match=match,
                match_strategy=match_strategy,
                tags=tags or [],
                link_to=link_to or [],
                linked_by=linked_by or [],
                mention=mention or [],
                mentioned_by=mentioned_by or [],
                related=related or [],
                orphan=orphan,
                tagless=tagless,
                recursive=recursive,
                max_distance=max_distance,
                created_after=created_after,
                created_before=created_before,
                modified_after=modified_after,
                modified_before=modified_before,
                sort=sort or [],
                limit=limit,
            )
            return await self.list_notes_with_config(config)
        except Exception as e:
            logger.error(f"list_notes failed: {e}")
            return []

    async def list_notes_with_config(self, config: ZkListConfig) -> List[ZkNote]:
        """List notes using full configuration object.

        Args:
            config: ZkListConfig with all filtering options.

        Returns:
            List of matching ZkNote objects.
        """
        args = ["list", "--format", "json"]

        # Core search
        if config.match:
            args.extend(["--match", config.match])

        if config.match_strategy and config.match_strategy != "fts":
            args.extend(["--match-strategy", config.match_strategy])

        # Path filtering
        if config.paths:
            args.extend(config.paths)

        if config.exclude:
            for path in config.exclude:
                args.extend(["--exclude", path])

        # Tag filtering
        if config.tags:
            args.extend(["--tag", ",".join(config.tags)])

        if config.tagless:
            args.append("--tagless")

        # Graph operations
        for path in config.link_to:
            args.extend(["--link-to", path])

        for path in config.linked_by:
            args.extend(["--linked-by", path])

        for path in config.mention:
            args.extend(["--mention", path])

        for path in config.mentioned_by:
            args.extend(["--mentioned-by", path])

        for path in config.related:
            args.extend(["--related", path])

        if config.orphan:
            args.append("--orphan")

        # Graph traversal
        if config.recursive:
            args.append("--recursive")

        if config.max_distance is not None:
            args.extend(["--max-distance", str(config.max_distance)])

        # Date filtering
        if config.created:
            args.extend(["--created", config.created])
        if config.created_after:
            args.extend(["--created-after", config.created_after])
        if config.created_before:
            args.extend(["--created-before", config.created_before])
        if config.modified:
            args.extend(["--modified", config.modified])
        if config.modified_after:
            args.extend(["--modified-after", config.modified_after])
        if config.modified_before:
            args.extend(["--modified-before", config.modified_before])

        # Sorting
        if config.sort:
            args.extend(["--sort", ",".join(config.sort)])

        # Output control
        if config.limit:
            args.extend(["--limit", str(config.limit)])

        # Execute
        data_list = await self._run_command(args)
        return [ZkNote.from_dict(data) for data in data_list]

    # Convenience methods
    async def search(self, query: str, limit: Optional[int] = None) -> List[ZkNote]:
        """Full-text search for notes.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching notes.
        """
        try:
            return await self.list_notes(match=query, limit=limit)
        except Exception as e:
            logger.error(f"search failed: {e}")
            return []

    async def find_by_tags(self, tags: List[str], limit: Optional[int] = None) -> List[ZkNote]:
        """Find notes by tags (AND semantics).

        Args:
            tags: Tags to match.
            limit: Maximum results.

        Returns:
            Notes matching all tags.
        """
        try:
            return await self.list_notes(tags=tags, limit=limit)
        except Exception as e:
            logger.error(f"find_by_tags failed: {e}")
            return []

    async def find_linked_by(self, note_id: str, limit: Optional[int] = None) -> List[ZkNote]:
        """Find notes linked by the given note.

        Args:
            note_id: Note ID (filename stem).
            limit: Maximum results.

        Returns:
            Notes that this note links to.
        """
        try:
            return await self.list_notes(linked_by=[note_id], limit=limit)
        except Exception as e:
            logger.error(f"find_linked_by failed: {e}")
            return []

    async def find_link_to(self, note_id: str, limit: Optional[int] = None) -> List[ZkNote]:
        """Find notes linking to the given note.

        Args:
            note_id: Note ID (filename stem).
            limit: Maximum results.

        Returns:
            Notes that link to this note.
        """
        try:
            return await self.list_notes(link_to=[note_id], limit=limit)
        except Exception as e:
            logger.error(f"find_link_to failed: {e}")
            return []

    async def find_related(
        self,
        note_id: str,
        recursive: bool = False,
        max_distance: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ZkNote]:
        """Find notes related to the given note.

        Args:
            note_id: Starting note ID.
            recursive: Follow links recursively.
            max_distance: Maximum link distance.
            limit: Maximum results.

        Returns:
            Related notes.
        """
        try:
            return await self.list_notes(
                related=[note_id],
                recursive=recursive,
                max_distance=max_distance,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"find_related failed: {e}")
            return []

    async def find_recents(self, days: int = 7, limit: int = 20) -> List[ZkNote]:
        """Find recently modified notes.

        Args:
            days: Look back period.
            limit: Maximum results.

        Returns:
            Recently modified notes.
        """
        try:
            return await self.list_notes(
                created_after=f"last {days} days",
                sort=["modified-"],
                limit=limit,
            )
        except Exception as e:
            logger.error(f"find_recents failed: {e}")
            return []

    async def find_orphans(self, limit: Optional[int] = None) -> List[ZkNote]:
        """Find notes without backlinks.

        Args:
            limit: Maximum results.

        Returns:
            Orphan notes.
        """
        try:
            return await self.list_notes(orphan=True, limit=limit)
        except Exception as e:
            logger.error(f"find_orphans failed: {e}")
            return []

    async def find_mentions(self, note_title: str, limit: Optional[int] = None) -> List[ZkNote]:
        """Find notes mentioning the given title.

        Args:
            note_title: Title to search for.
            limit: Maximum results.

        Returns:
            Notes mentioning this title.
        """
        try:
            return await self.list_notes(mention=[note_title], limit=limit)
        except Exception as e:
            logger.error(f"find_mentions failed: {e}")
            return []

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about the ZK notebook.

        Returns:
            Dictionary with note count, link count, etc.
        """
        try:
            # Get total notes count
            notes_list = await self.list_notes(limit=1000)
            total_notes = len(notes_list)

            # Count orphans
            orphans = await self.find_orphans(limit=1000)
            orphan_count = len(orphans)

            return {
                "total_notes": total_notes,
                "orphan_count": orphan_count,
                "linked_notes": total_notes - orphan_count,
            }
        except Exception as e:
            logger.error(f"get_stats failed: {e}")
            return {"error": str(e)}

    async def get_links(
        self, note_id: str, direction: str = "both"
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Get links for a specific note.

        Args:
            note_id: Note ID (filename stem).
            direction: "both", "to", or "from".

        Returns:
            Tuple of (outgoing_links, incoming_links).
        """
        try:
            outgoing: list[dict[str, Any]] = []
            incoming: list[dict[str, Any]] = []

            if direction in ("both", "from"):
                # Notes linked BY this note (outgoing - links to other notes)
                linked_notes = await self.find_linked_by(note_id)
                for note in linked_notes:
                    outgoing.append(
                        {
                            "source": note_id,
                            "sourceTitle": "",
                            "target": note.filename_stem or "",
                            "targetTitle": note.title,
                            "type": "wiki",
                        }
                    )

            if direction in ("both", "to"):
                # Notes linking TO this note (incoming - other notes link here)
                linking_notes = await self.find_link_to(note_id)
                for note in linking_notes:
                    incoming.append(
                        {
                            "source": note.filename_stem or "",
                            "sourceTitle": note.title,
                            "target": note_id,
                            "targetTitle": "",
                            "type": "wiki",
                        }
                    )

            return outgoing, incoming
        except Exception as e:
            logger.error(f"get_links failed: {e}")
            return [], []


def get_zk_client(notebook_dir: Optional[Union[str, Path]] = None) -> ZkClient:
    """Factory function for ZkClient.

    Args:
        notebook_dir: Optional notebook directory.

    Returns:
        ZkClient instance.
    """
    return ZkClient(notebook_dir)


__all__ = [
    "ZkNote",
    "ZkListConfig",
    "ZkClient",
    "get_zk_client",
]
