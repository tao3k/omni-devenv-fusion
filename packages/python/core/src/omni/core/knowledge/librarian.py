"""Librarian - Unified Knowledge Ingestion with Smart Incremental Support.

Architecture:
    Librarian (main class)
        ├── Config: references.yaml settings
        ├── Chunking: Text (docs) or AST (code) modes
        ├── Manifest: Hash-based change tracking (.omni/cache/knowledge_manifest.json)
        └── Storage: LanceDB operations

Smart Features:
- Incremental Ingestion: Only processes changed files (O(1) update)
- Manifest Tracking: Tracks file hashes for change detection
- Hot Indexing: Single file upsert via upsert_file() for live updates

Usage:
    from omni.core.knowledge import Librarian, ChunkMode

    # Full ingestion (first time or after clean)
    librarian = Librarian(project_root=".")
    result = librarian.ingest(clean=True)

    # Incremental ingestion (only changed files)
    result = librarian.ingest()

    # Hot-index a single file (for watcher integration)
    librarian.upsert_file("/path/to/changed/file.py")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omni_core_rs import PyVectorStore

from .config import get_knowledge_config
from .ingestion import FileIngestor
from .storage import KnowledgeStorage

logger = logging.getLogger(__name__)


class ChunkMode(Enum):
    """Chunking strategy for knowledge ingestion."""

    AUTO = "auto"  # Auto-detect based on file type
    TEXT = "text"  # Simple text chunking for documentation
    AST = "ast"  # AST-based semantic chunking for code


class Librarian:
    """Unified knowledge ingestion with smart incremental support.

    - TEXT mode: Simple section-based chunking for Markdown documentation
    - AST mode: Rust-accelerated AST parsing for semantic code understanding
    - Manifest Tracking: Hash-based change detection for O(1) updates

    Stores chunks in LanceDB for hybrid search.
    """

    # Constants
    TABLE_NAME = "knowledge_chunks"
    MANIFEST_FILE = "knowledge_manifest.json"

    def __init__(
        self,
        project_root: str | Path = ".",
        store: PyVectorStore | None = None,
        embedder: EmbeddingService | None = None,
        batch_size: int = 50,
        max_files: int | None = None,
        use_knowledge_dirs: bool = True,
        chunk_mode: str | ChunkMode = "auto",
        config_path: Path | None = None,
        table_name: str = TABLE_NAME,
    ):
        """Initialize the Librarian.

        Args:
            project_root: Root directory of the project
            store: LanceDB vector store (auto-created if None)
            embedder: Embedding service (auto-created if None)
            batch_size: Batch size for processing
            max_files: Maximum files to process (None for unlimited)
            use_knowledge_dirs: Use knowledge_dirs from references.yaml
            chunk_mode: "text", "ast", or "auto" (detect from file type)
            config_path: Path to references.yaml
            table_name: Name of the LanceDB table
        """
        from omni_core_rs import PyVectorStore as RustStore
        from omni.foundation.config.dirs import get_database_path
        from omni.foundation.services.embedding import EmbeddingService

        self.root = Path(project_root).resolve()
        self.batch_size = batch_size
        self.max_files = max_files
        self.use_knowledge_dirs = use_knowledge_dirs
        self.chunk_mode = ChunkMode(chunk_mode) if isinstance(chunk_mode, str) else chunk_mode
        self.table_name = table_name

        # Load configuration
        self.config = get_knowledge_config(config_path)

        # Initialize embedder
        self.embedder = embedder or EmbeddingService()

        # Initialize storage using unified database path
        if store is None:
            db_path = get_database_path("knowledge")
            store = RustStore(db_path, self.embedder.dimension, True)
        self.storage = KnowledgeStorage(store, table_name=table_name)

        # Initialize ingestion
        self.ingestor = FileIngestor(self.config)

        # Load manifest for incremental tracking
        self.manifest: dict[str, str] = self._load_manifest()

    # =========================================================================
    # Manifest Management
    # =========================================================================

    def _get_manifest_path(self) -> Path:
        """Get manifest path in vector DB directory."""
        from omni.foundation.config.dirs import get_vector_db_path

        return get_vector_db_path() / self.MANIFEST_FILE

    def _load_manifest(self) -> dict[str, str]:
        """Load manifest from disk using unified cache path."""
        manifest_path = self._get_manifest_path()
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load manifest: {e}")
                return {}
        return {}

    def _save_manifest(self) -> None:
        """Save manifest to disk using unified cache path."""
        manifest_path = self._get_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(self.manifest, indent=2))

    def _compute_hash(self, content: str) -> str:
        """Compute MD5 hash of content."""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_rel_path(self, file_path: Path) -> str:
        """Get relative path for manifest key."""
        return str(file_path.relative_to(self.root))

    # =========================================================================
    # Core Ingestion
    # =========================================================================

    def ingest(self, clean: bool = False) -> dict[str, int]:
        """Ingest the project into the knowledge base.

        Args:
            clean: If True, drop existing table and start fresh

        Returns:
            Dictionary with files_processed, chunks_indexed, errors
        """
        return asyncio.run(self._ingest_async(clean=clean))

    async def _ingest_async(self, clean: bool = False) -> dict[str, int]:
        """Async implementation of ingest with incremental support."""
        if clean:
            self.storage.drop_table()
            self.manifest = {}
            logger.info("🗑️ Clean ingestion: dropped table and cleared manifest")
        elif self.manifest:
            logger.info("🔍 Incremental mode: checking for changed files...")

        # Log prompt loading status
        try:
            from omni.foundation.config import get_setting

            prompt_path = get_setting("prompts.system_core", "assets/prompts/system_core.md")
            logger.info(f"📝 Prompt loaded: {prompt_path}")
        except Exception:
            logger.info("📝 Prompt: using default")

        # Discover files
        files = self.ingestor.discover_files(
            self.root,
            max_files=self.max_files,
            use_knowledge_dirs=self.use_knowledge_dirs,
        )

        # Log discovered files
        if files:
            logger.info(f"Discovered {len(files)} files to scan:")
            # Group files by directory for readability
            dirs: dict[str, list[Path]] = {}
            for f in files:
                parent = f.parent.relative_to(self.root)
                parent_str = str(parent) if parent != Path(".") else "."
                if parent_str not in dirs:
                    dirs[parent_str] = []
                dirs[parent_str].append(f)

            # Show files grouped by directory
            for dir_path, dir_files in sorted(dirs.items()):
                dir_display = f"./{dir_path}" if dir_path != "." else "."
                logger.info(f"  [{dir_display}]")
                for f in sorted(dir_files):
                    logger.info(f"  |-- {f.name}")
        else:
            logger.info("No files discovered for scanning")

        # Calculate diff: only process changed or new files
        to_process: list[tuple[Path, str, str]] = []  # (path, content, hash)
        current_files: set[str] = set()

        for file_path in files:
            rel_path = self._get_rel_path(file_path)
            current_files.add(rel_path)

            try:
                content = file_path.read_text(errors="ignore")
                file_hash = self._compute_hash(content)

                # Check if file is new or changed
                if self.manifest.get(rel_path) != file_hash:
                    to_process.append((file_path, content, file_hash))
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {rel_path}: {e}")

        # Handle deleted files
        deleted = set(self.manifest.keys()) - current_files
        if deleted:
            logger.info(f"🗑️ Detected {len(deleted)} deleted files")
            for rel_path in deleted:
                self._delete_by_path(rel_path)
                del self.manifest[rel_path]

        if not to_process:
            logger.info("✅ Knowledge base is up-to-date. No changes detected.")
            return {"files_processed": 0, "chunks_indexed": 0, "errors": 0, "updated": 0}

        logger.info(f"Processing {len(to_process)} changed/new files...")

        # Create records for changed files only
        paths = [f[0] for f in to_process] if to_process else []
        records = self.ingestor.create_records(paths, self.root, mode=self.chunk_mode.value)

        # Update manifest while processing
        for file_path, _, file_hash in to_process:
            rel_path = self._get_rel_path(file_path)
            self.manifest[rel_path] = file_hash

        # Save manifest IMMEDIATELY after updating to prevent data loss on interruption
        self._save_manifest()

        if not records:
            return {
                "files_processed": len(to_process),
                "chunks_indexed": 0,
                "errors": 0,
                "updated": len(to_process),
            }

        # Process in batches
        total_chunks = 0
        errors = 0
        total_batches = (len(records) + self.batch_size - 1) // self.batch_size

        logger.info(f"Processing {total_batches} batches ({len(records)} chunks)...")

        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1

            if batch_num == 1 or batch_num % 5 == 0 or batch_num == total_batches:
                progress = (batch_num * 100) // total_batches
                logger.info(f"[{progress:3d}%] Batch {batch_num}/{total_batches}")

            try:
                await self._process_batch(batch)
                total_chunks += len(batch)
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                errors += 1

        logger.info(
            f"Done! Processed {len(to_process)} files, generated {total_chunks} chunks, {errors} errors"
        )

        return {
            "files_processed": len(to_process),
            "chunks_indexed": total_chunks,
            "errors": errors,
            "updated": len(to_process),
        }

    def _delete_by_path(self, rel_path: str) -> None:
        """Delete all chunks for a file by its relative path.

        Uses the optimized delete_by_file_path method from PyVectorStore if available.
        """
        try:
            # Use direct delete_by_file_path if available (supported in PyVectorStore)
            if hasattr(self.storage._store, "delete_by_file_path"):
                # Rust signature: delete_by_file_path(table_name: Option<String>, file_paths: Vec<String>)
                self.storage._store.delete_by_file_path(self.table_name, [rel_path])
            elif hasattr(self.storage._store, "list_all"):
                # Legacy fallback: list all and delete by ID
                all_entries = asyncio.run(self.storage._store.list_all(self.table_name))
                for entry in all_entries:
                    meta = entry.get("metadata", {})
                    if isinstance(meta, str):
                        meta = json.loads(meta)
                    if meta.get("file_path") == rel_path:
                        entry_id = entry.get("id")
                        if entry_id:
                            asyncio.run(self.storage._store.delete(entry_id))
            else:
                logger.warning(
                    f"Cannot delete chunks for {rel_path}: store doesn't support delete_by_file_path or list_all"
                )
        except Exception as e:
            logger.warning(f"Failed to delete chunks for {rel_path}: {e}")

    # =========================================================================
    # Hot Indexing (for Watcher Integration)
    # =========================================================================

    def upsert_file(self, file_path: str) -> bool:
        """Hot-index a single file immediately.

        This is the primary interface for watcher integration.
        Only re-indexes if the file content has changed.

        Args:
            file_path: Absolute path to the file

        Returns:
            True if file was indexed, False if unchanged
        """
        path = Path(file_path).resolve()

        if not path.exists():
            # File was deleted - remove from index and manifest
            try:
                rel_path = str(path.relative_to(self.root))
                self._delete_by_path(rel_path)
                if rel_path in self.manifest:
                    del self.manifest[rel_path]
                    self._save_manifest()
                return True
            except ValueError:
                return False

        try:
            rel_path = self._get_rel_path(path)
            content = path.read_text(errors="ignore")
            file_hash = self._compute_hash(content)

            # Debounce: skip if hash matches
            if self.manifest.get(rel_path) == file_hash:
                return False

            logger.info(f"⚡ Hot-indexing: {rel_path}")

            # Delete old chunks for this file
            self._delete_by_path(rel_path)

            # Create chunks for the file
            records = self.ingestor.create_records([path], self.root, mode=self.chunk_mode.value)

            if records:
                # Embed and store
                asyncio.run(self._process_batch(records))

            # Update manifest
            self.manifest[rel_path] = file_hash
            self._save_manifest()

            return True

        except Exception as e:
            logger.error(f"Failed to hot-index {file_path}: {e}")
            return False

    # =========================================================================
    # Batch Processing
    # =========================================================================

    async def _process_batch(self, records: list[dict]) -> None:
        """Embed and store a batch of records."""
        texts = [r["text"] for r in records]
        vectors = self.embedder.embed_batch(texts)

        for r, v in zip(records, vectors):
            r["vector"] = v

        self.storage.add_batch(records)

    # =========================================================================
    # Query & Context
    # =========================================================================

    def query(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search the knowledge base.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results
        """
        vectors = self.embedder.embed(query)
        vector = vectors[0]  # Extract first embedding from batch result
        return self.storage.search(vector, limit=limit)

    def get_context(self, query: str, limit: int = 5) -> str:
        """Get formatted context blocks for LLM consumption.

        Args:
            query: Query to get context for
            limit: Number of context blocks

        Returns:
            Formatted context string
        """
        results = self.query(query, limit=limit)

        if not results:
            return ""

        blocks = []
        for res in results:
            meta = res.get("metadata", {})
            path = meta.get("file_path", "unknown")
            lines = f"L{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
            chunk_type = meta.get("chunk_type", "code")

            block = f"[{chunk_type.upper()}] {path} ({lines})\n```\n{res['text']}\n```"
            blocks.append(block)

        return "\n\n".join(blocks)

    def clear(self) -> None:
        """Clear all indexed knowledge and reset manifest."""
        self.storage.drop_table()
        self.manifest = {}
        self._save_manifest()
        logger.info("🗑️ Knowledge base cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        try:
            count = self.storage.count()
            manifest_count = len(self.manifest)
            return {
                "table": self.storage.table_name,
                "record_count": count,
                "tracked_files": manifest_count,
            }
        except Exception as e:
            return {"table": self.storage.table_name, "record_count": 0, "error": str(e)}

    def get_manifest_status(self) -> dict[str, Any]:
        """Get manifest status for debugging."""
        manifest_path = self._get_manifest_path()
        return {
            "manifest_path": str(manifest_path),
            "manifest_exists": manifest_path.exists(),
            "tracked_files": len(self.manifest),
            "last_modified": manifest_path.stat().st_mtime if manifest_path.exists() else None,
        }


# Re-exports
__all__ = [
    "Librarian",
    "ChunkMode",
]
