"""Librarian - Unified Knowledge Ingestion with Rust SyncEngine.

Architecture:
    Librarian (main class)
        ├── Config: references.yaml settings
        ├── Schemas: KnowledgeEntry type definitions
        ├── Chunking: Text (docs) or AST (code) modes
        ├── SyncEngine (Rust): xxhash-rust + manifest management
        └── Storage: LanceDB operations

Rust SyncEngine Benefits:
- xxhash-rust for 5-10x faster hashing vs MD5
- Optimized file discovery and diff computation
- Automatic manifest persistence

Usage:
    from omni.core.knowledge import Librarian, ChunkMode, KnowledgeCategory

    # Full ingestion (first time or after clean)
    librarian = Librarian(project_root=".")
    result = librarian.ingest(clean=True)

    # Incremental ingestion (only changed files)
    result = librarian.ingest()
"""

from __future__ import annotations

import json
import logging
import uuid
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omni.foundation.utils.asyncio import run_async_blocking

if TYPE_CHECKING:
    from omni_core_rs import PyVectorStore

from .config import get_knowledge_config
from .ingestion import FileIngestor
from .knowledge_types import KnowledgeCategory, KnowledgeEntry

logger = logging.getLogger(__name__)


class ChunkMode(Enum):
    """Chunking strategy for knowledge ingestion."""

    AUTO = "auto"  # Auto-detect based on file type
    TEXT = "text"  # Simple text chunking for documentation
    AST = "ast"  # AST-based semantic chunking for code


class KnowledgeStorage:
    """Storage wrapper for knowledge chunks."""

    def __init__(self, store: "PyVectorStore", table_name: str = "knowledge_chunks"):
        self._store = store
        self.table_name = table_name
        # Ensure table exists
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure the table exists, create if needed."""
        try:
            # Try to access the table - this will fail if it doesn't exist
            self._store.count(self.table_name)
        except Exception:
            # Table doesn't exist, create it
            try:
                self._store.create_index(self.table_name)
                logger.info(f"Created knowledge table: {self.table_name}")
            except Exception as e:
                logger.warning(f"Could not create table {self.table_name}: {e}")

    def add_batch(self, records: list[dict[str, Any]]) -> None:
        """Add batch of records using add_documents."""
        # Extract components from records for add_documents
        ids = []
        vectors = []
        contents = []
        metadatas = []

        for record in records:
            ids.append(record.get("id", ""))
            vectors.append(record.get("vector", []))
            # Support both 'content' and 'text' fields
            contents.append(record.get("content") or record.get("text", ""))
            metadatas.append(json.dumps(record.get("metadata", {})))

        self._store.add_documents(self.table_name, ids, vectors, contents, metadatas)

    @staticmethod
    def _parse_search_results(raw_results: list[Any]) -> list[dict[str, Any]]:
        """Parse JSON-encoded Rust search payloads into Python dicts."""
        parsed: list[dict[str, Any]] = []
        for raw in raw_results:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict):
                    parsed.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        return parsed

    def vector_search(self, vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Vector search over knowledge chunks."""
        raw_results = self._store.search_optimized(self.table_name, vector, limit, None)
        return self._parse_search_results(raw_results)

    def text_search(
        self, query_text: str, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        """Hybrid text search over knowledge chunks (keyword + vector)."""
        raw_results = self._store.search_hybrid(
            self.table_name,
            query_vector,
            [query_text],
            limit,
        )
        return self._parse_search_results(raw_results)

    def lexical_scan(self, query_text: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fallback lexical scan over all rows when hybrid ranking misses obvious hits."""
        if not hasattr(self._store, "list_all"):
            return []
        try:
            raw_rows = self._store.list_all(self.table_name)
            if hasattr(raw_rows, "__await__"):
                rows = run_async_blocking(raw_rows)
            else:
                rows = raw_rows
        except Exception:
            return []

        q = query_text.strip().lower()
        if not q:
            return []

        matches: list[dict[str, Any]] = []
        for row in rows:
            content = row.get("content", row.get("text", ""))
            if isinstance(content, str) and q in content.lower():
                matches.append(row)
                if len(matches) >= limit:
                    break
        return matches

    def count(self) -> int:
        return self._store.count(self.table_name)

    def drop_table(self) -> None:
        self._store.drop_table(self.table_name)

    def delete(self, entry_id: str) -> bool:
        self._store.delete(self.table_name, [entry_id])
        return True


class Librarian:
    """Unified knowledge ingestion with Rust SyncEngine.

    Uses:
    - Rust SyncEngine: xxhash-rust for fast incremental updates
    - LanceDB: Vector storage for hybrid search
    """

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
        """Initialize the Librarian."""
        from omni_core_rs import PySyncEngine
        from omni_core_rs import PyVectorStore as RustStore
        from omni.foundation.config.database import get_database_path, get_vector_db_path
        from omni.foundation.services.embedding import get_embedding_service

        self.root = Path(project_root).resolve()
        self.batch_size = batch_size
        self.max_files = max_files
        self.use_knowledge_dirs = use_knowledge_dirs
        self.chunk_mode = ChunkMode(chunk_mode) if isinstance(chunk_mode, str) else chunk_mode
        self.table_name = table_name

        # Load configuration
        self.config = get_knowledge_config(config_path)

        # Initialize embedder using singleton pattern to avoid loading model twice
        self.embedder = embedder or get_embedding_service()
        # Get dimension from settings (lazy load only when actually embedding)
        from omni.foundation.config.settings import get_setting

        dimension = get_setting("embedding.dimension", 1024)

        # Initialize storage using unified database path
        if store is None:
            db_path = get_database_path("knowledge")
            store = RustStore(db_path, dimension, True)
            logger.info(f"Created knowledge store with dimension: {dimension}")
        self.storage = KnowledgeStorage(store, table_name=table_name)

        # Initialize ingestion
        self.ingestor = FileIngestor(self.config)

        # Initialize Rust SyncEngine for manifest management
        manifest_path = get_vector_db_path() / self.MANIFEST_FILE
        self.sync_engine = PySyncEngine(str(self.root), str(manifest_path))
        logger.info(f"Using Rust SyncEngine with manifest: {manifest_path}")

        # Load manifest immediately
        self.manifest = self._load_manifest()

    # =========================================================================
    # Async Helper
    # =========================================================================

    # =========================================================================
    # Manifest Management (Rust)
    # =========================================================================

    def _load_manifest(self) -> dict[str, str]:
        """Load manifest using Rust SyncEngine."""
        manifest_json = self.sync_engine.load_manifest()
        if manifest_json and manifest_json != "{}":
            return json.loads(manifest_json)
        return {}

    def _save_manifest(self) -> None:
        """Save manifest using Rust SyncEngine."""
        manifest_json = json.dumps(self.manifest, indent=2)
        self.sync_engine.save_manifest(manifest_json)

    def _compute_hash(self, content: str) -> str:
        """Compute hash using Rust xxhash-rust."""
        from omni_core_rs import compute_hash

        return compute_hash(content)

    def _get_rel_path(self, file_path: Path) -> str:
        """Get relative path for manifest key."""
        return str(file_path.relative_to(self.root))

    # =========================================================================
    # Core Ingestion
    # =========================================================================

    def ingest(self, clean: bool = False) -> dict[str, int]:
        """Ingest the project into the knowledge base."""
        return run_async_blocking(self._ingest_async(clean=clean))

    async def _ingest_async(self, clean: bool = False) -> dict[str, int]:
        """Async implementation with Rust SyncEngine."""
        if clean:
            self.storage.drop_table()
            self.storage._ensure_table()
            self.manifest = {}
            self.sync_engine.save_manifest("{}")
            logger.info("Clean ingestion: dropped table and cleared manifest")
        else:
            # Ensure table exists before any operations
            self.storage._ensure_table()
            self.manifest = self._load_manifest()
            if self.manifest:
                logger.info("Incremental mode: checking for changed files...")

        # Log prompt loading status
        try:
            from omni.foundation.config import get_setting

            prompt_path = get_setting("prompts.system_core", "assets/prompts/system_core.md")
            logger.info(f"Prompt loaded: {prompt_path}")
        except Exception:
            logger.info("Prompt: using default")

        # Discover files
        files = self.ingestor.discover_files(
            self.root,
            max_files=self.max_files,
            use_knowledge_dirs=self.use_knowledge_dirs,
        )

        if files:
            logger.info(f"Discovered {len(files)} files to scan:")
            dirs: dict[str, list[Path]] = {}
            for f in files:
                parent = f.parent.relative_to(self.root)
                parent_str = str(parent) if parent != Path(".") else "."
                if parent_str not in dirs:
                    dirs[parent_str] = []
                dirs[parent_str].append(f)

            for dir_path, dir_files in sorted(dirs.items()):
                dir_display = f"./{dir_path}" if dir_path != "." else "."
                logger.info(f"  [{dir_display}]")
                for f in sorted(dir_files):
                    logger.info(f"  |-- {f.name}")
        else:
            logger.info("No files discovered for scanning")

        # Calculate diff: only process changed or new files
        to_process: list[tuple[Path, str, str]] = []
        current_files: set[str] = set()

        for file_path in files:
            rel_path = self._get_rel_path(file_path)
            current_files.add(rel_path)

            try:
                content = file_path.read_text(errors="ignore")
                file_hash = self._compute_hash(content)

                if self.manifest.get(rel_path) != file_hash:
                    to_process.append((file_path, content, file_hash))
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {rel_path}: {e}")

        # Handle deleted files
        deleted = set(self.manifest.keys()) - current_files
        if deleted:
            deleted_list = list(deleted)
            logger.info(f"Deleting {len(deleted_list)} files from index...")
            self._delete_by_paths_batch(deleted_list)
            for rel_path in deleted:
                del self.manifest[rel_path]
            self._save_manifest()
            logger.info(f"Cleanup complete: {len(deleted_list)} files removed")

        if not to_process:
            if deleted:
                logger.info("Cleanup complete. Deleted files removed from index.")
            else:
                logger.info("Knowledge base is up-to-date. No changes detected.")
            return {"files_processed": 0, "chunks_indexed": 0, "errors": 0, "updated": 0}

        logger.info(f"Processing {len(to_process)} changed/new files...")

        # Create records for changed files only
        paths = [f[0] for f in to_process] if to_process else []
        logger.info(f"Creating records from {len(paths)} files...")
        records = self.ingestor.create_records(paths, self.root, mode=self.chunk_mode.value)
        logger.info(f"Created {len(records)} chunks")

        # Update manifest while processing
        for file_path, _, file_hash in to_process:
            rel_path = self._get_rel_path(file_path)
            self.manifest[rel_path] = file_hash

        # Save manifest immediately
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
                logger.info(f"[{progress:3d}%] Batch {batch_num}/{total_batches} (embedding...)")

            try:
                await self._process_batch(batch)
                total_chunks += len(batch)
                logger.debug(f"Batch {batch_num} stored")
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
        """Delete all chunks for a file by its relative path."""
        if hasattr(self.storage._store, "delete_by_file_path"):
            self.storage._store.delete_by_file_path(self.table_name, [rel_path])
        elif hasattr(self.storage._store, "list_all"):
            all_entries = run_async_blocking(self.storage._store.list_all(self.table_name))
            for entry in all_entries:
                meta = entry.get("metadata", {})
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if meta.get("file_path") == rel_path:
                    entry_id = entry.get("id")
                    if entry_id:
                        run_async_blocking(self.storage._store.delete(entry_id))

    def _delete_by_paths_batch(self, rel_paths: list[str]) -> int:
        """Delete chunks for multiple files in batch."""
        if not rel_paths:
            return 0

        if hasattr(self.storage._store, "delete_by_file_path"):
            self.storage._store.delete_by_file_path(self.table_name, rel_paths)
            return len(rel_paths)
        return 0

    # =========================================================================
    # Hot Indexing (for Watcher Integration)
    # =========================================================================

    def upsert_file(self, file_path: str) -> bool:
        """Hot-index a single file immediately."""
        path = Path(file_path).resolve()

        if not path.exists():
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

            logger.info(f"Hot-indexing: {rel_path}")

            # Delete old chunks
            self._delete_by_path(rel_path)

            # Create chunks
            records = self.ingestor.create_records([path], self.root, mode=self.chunk_mode.value)

            if records:
                run_async_blocking(self._process_batch(records))

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

    @staticmethod
    def _lexical_signal(query: str, content: str) -> tuple[int, int]:
        """Return lexical relevance signal: (exact_phrase_hit, token_overlap_count)."""
        q = query.strip().lower()
        c = content.lower()
        if not q or not c:
            return (0, 0)
        exact = 1 if q in c else 0
        tokens = [t for t in q.split() if t]
        overlap = sum(1 for t in tokens if t in c)
        return (exact, overlap)

    def _source_lexical_fallback(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fallback lexical retrieval directly from source chunks."""
        q = query.strip().lower()
        if not q:
            return []
        try:
            files = self.ingestor.discover_files(
                self.root,
                max_files=self.max_files,
                use_knowledge_dirs=self.use_knowledge_dirs,
            )
            records = self.ingestor.create_records(files, self.root, mode=self.chunk_mode.value)
        except Exception:
            return []

        hits: list[dict[str, Any]] = []
        for rec in records:
            content = rec.get("text", "")
            if isinstance(content, str) and q in content.lower():
                hits.append(
                    {
                        "id": rec.get("id", ""),
                        "content": content,
                        "score": 0.0,
                        "metadata": rec.get("metadata", {}),
                    }
                )
                if len(hits) >= limit:
                    break
        return hits

    def query(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search the knowledge base."""
        vectors = self.embedder.embed(query)
        # embedder.embed returns list[list[float]], extract first vector
        query_vector = vectors[0] if vectors else [0.0] * self.embedder.dimension
        results = self.storage.text_search(query, query_vector, limit=limit)

        # If top-N misses obvious lexical hits (common with mock/noisy embeddings),
        # expand candidate pool once and rerank.
        has_lexical_hit = any(
            self._lexical_signal(query, r.get("content", r.get("text", "")))[1] > 0 for r in results
        )
        if not has_lexical_hit:
            expanded_limit = max(limit * 5, limit + 5)
            if expanded_limit > limit:
                results = self.storage.text_search(query, query_vector, limit=expanded_limit)
            has_lexical_hit = any(
                self._lexical_signal(query, r.get("content", r.get("text", "")))[1] > 0
                for r in results
            )
            if not has_lexical_hit:
                fallback = self.storage.lexical_scan(query, limit=max(limit * 5, 20))
                if fallback:
                    results = fallback
                else:
                    source_hits = self._source_lexical_fallback(query, limit=max(limit * 5, 20))
                    if source_hits:
                        results = source_hits

        def _sort_key(item: dict[str, Any]) -> tuple[int, int, float]:
            content = item.get("content", item.get("text", ""))
            exact, overlap = self._lexical_signal(query, content)
            score = float(item.get("score", 0.0) or 0.0)
            return (exact, overlap, score)

        ranked = sorted(results, key=_sort_key, reverse=True)
        return ranked[:limit]

    def search_raw(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search and return raw structured results."""
        results = self.query(query, limit=limit)

        raw_results = []
        for res in results:
            meta = res.get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}

            raw_results.append(
                {
                    "path": meta.get("file_path", "unknown"),
                    "score": res.get("score", 0.0),
                    "text": res.get("text", ""),
                    "metadata": meta,
                }
            )

        return raw_results

    def get_context(self, query: str, limit: int = 5) -> str:
        """Get formatted context blocks for LLM consumption."""
        results = self.query(query, limit=limit)

        if not results:
            return ""

        blocks = []
        for res in results:
            meta = res.get("metadata", {})
            # Handle metadata - it could be a dict or a JSON string
            if isinstance(meta, str):
                try:
                    import json

                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            path = meta.get("file_path", "unknown")
            lines = f"{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
            chunk_type = meta.get("chunk_type", "code")

            # Use 'content' field (not 'text')
            content = res.get("content", res.get("text", ""))
            block = f"[{chunk_type.upper()}] {path} ({lines})\n```\n{content}\n```"
            blocks.append(block)

        return "\n\n".join(blocks)

    def clear(self) -> None:
        """Clear all indexed knowledge and reset manifest."""
        self.storage.drop_table()
        self.manifest = {}
        self._save_manifest()
        logger.info("Knowledge base cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        count = self.storage.count()
        manifest_count = len(self.manifest)

        category_counts: dict[str, int] = {}
        for rel_path, _ in self.manifest.items():
            cat = self.infer_category(rel_path)
            cat_key = cat.value
            category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

        return {
            "table": self.storage.table_name,
            "record_count": count,
            "tracked_files": manifest_count,
            "entries_by_category": category_counts,
        }

    def get_manifest_status(self) -> dict[str, Any]:
        """Get manifest status for debugging."""
        from omni.foundation.config.dirs import get_vector_db_path

        manifest_path = get_vector_db_path() / self.MANIFEST_FILE
        return {
            "manifest_path": str(manifest_path),
            "manifest_exists": manifest_path.exists(),
            "tracked_files": len(self.manifest),
        }

    # =========================================================================
    # Schema Validation & KnowledgeEntry
    # =========================================================================

    def infer_category(self, file_path: Path | str) -> KnowledgeCategory:
        """Infer knowledge category from file path."""
        path = str(file_path).lower()

        if "/patterns/" in path or "-pattern" in path:
            return KnowledgeCategory.PATTERN
        elif "/solutions/" in path or "-solution" in path:
            return KnowledgeCategory.SOLUTION
        elif "/errors/" in path or "-error" in path:
            return KnowledgeCategory.ERROR
        elif "/techniques/" in path or "-technique" in path:
            return KnowledgeCategory.TECHNIQUE
        elif "/notes/" in path or "-note" in path:
            return KnowledgeCategory.NOTE
        elif "/reference" in path:
            return KnowledgeCategory.REFERENCE
        elif "/architecture/" in path or "/specs/" in path:
            return KnowledgeCategory.ARCHITECTURE
        elif "/workflows/" in path or "/workflow/" in path:
            return KnowledgeCategory.WORKFLOW

        if path.endswith(".md") or path.endswith(".markdown"):
            return KnowledgeCategory.NOTE
        elif path.endswith((".yaml", ".yml", ".json")):
            return KnowledgeCategory.REFERENCE

        return KnowledgeCategory.NOTE

    def extract_tags(self, content: str, file_path: Path | str | None = None) -> list[str]:
        """Extract tags from content."""
        import re

        tags = set()

        frontmatter_match = re.search(
            r"^---\s*\n(?:.*?\n)*?---\s*\n", content, re.MULTILINE | re.DOTALL
        )
        if frontmatter_match:
            yaml_section = frontmatter_match.group(0)
            tag_match = re.search(r"tags:\s*\[(.*?)\]", yaml_section, re.IGNORECASE)
            if tag_match:
                tag_str = tag_match.group(1)
                found_tags = re.findall(r'"([^"]+)"', tag_str)
                found_tags.extend(re.findall(r"'([^']+)'", tag_str))
                tags.update(found_tags)

        tag_patterns = [
            r"\[([a-zA-Z][a-zA-Z0-9_-]+)\]",
            r"#([a-zA-Z][a-zA-Z0-9_-]+)",
        ]
        for pattern in tag_patterns:
            matches = re.findall(pattern, content)
            tags.update(matches)

        if file_path:
            path = str(file_path)
            if "/patterns/" in path:
                tags.add("pattern")
            elif "/solutions/" in path:
                tags.add("solution")
            elif "/errors/" in path:
                tags.add("error")

        return sorted(list(tags))

    def create_entry(
        self,
        title: str,
        content: str,
        category: KnowledgeCategory | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        file_path: Path | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEntry:
        """Create a KnowledgeEntry with validation."""
        if category is None:
            category = self.infer_category(file_path) if file_path else KnowledgeCategory.NOTE

        if tags is None:
            tags = self.extract_tags(content, file_path)

        entry_id = str(uuid.uuid4())

        entry = KnowledgeEntry(
            id=entry_id,
            title=title,
            content=content,
            category=category,
            tags=tags,
            source=source,
            metadata=metadata or {},
        )

        logger.debug(f"Created KnowledgeEntry: {entry.id} ({entry.category.value})")
        return entry

    def entry_to_record(self, entry: KnowledgeEntry) -> dict[str, Any]:
        """Convert KnowledgeEntry to storage record."""
        return {
            "id": entry.id,
            "text": entry.content,
            "metadata": {
                "title": entry.title,
                "category": entry.category.value,
                "tags": entry.tags,
                "source": entry.source,
                "entry_version": entry.version,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
                "chunk_type": "knowledge_entry",
                **(entry.metadata or {}),
            },
            "vector": None,
        }

    def upsert_entry(self, entry: KnowledgeEntry) -> bool:
        """Upsert a KnowledgeEntry to storage."""
        try:
            record = self.entry_to_record(entry)
            texts = [record["text"]]
            vectors = self.embedder.embed_batch(texts)
            record["vector"] = vectors[0]

            self.storage.add_batch([record])
            logger.info(f"Upserted KnowledgeEntry: {entry.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert entry {entry.id}: {e}")
            return False

    def search_entries(
        self,
        query: str,
        category: KnowledgeCategory | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> list[KnowledgeEntry]:
        """Search knowledge entries with filtering."""
        results = self.query(query, limit=limit * 2)

        entries = []
        for res in results:
            meta = res.get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    continue

            if category:
                if meta.get("category") != category.value:
                    continue

            if tags:
                entry_tags = meta.get("tags", [])
                if not any(tag in entry_tags for tag in tags):
                    continue

            from datetime import datetime, timezone

            entry = KnowledgeEntry(
                id=res.get("id", ""),
                title=meta.get("title", ""),
                content=res.get("text", ""),
                category=KnowledgeCategory(meta.get("category", "notes")),
                tags=meta.get("tags", []),
                source=meta.get("source"),
                created_at=datetime.fromisoformat(meta.get("created_at", "")).replace(
                    tzinfo=timezone.utc
                )
                if meta.get("created_at")
                else datetime.now(timezone.utc),
                updated_at=datetime.fromisoformat(meta.get("updated_at", "")).replace(
                    tzinfo=timezone.utc
                )
                if meta.get("updated_at")
                else datetime.now(timezone.utc),
                version=meta.get("entry_version", 1),
                metadata={
                    k: v
                    for k, v in meta.items()
                    if k
                    not in (
                        "title",
                        "category",
                        "tags",
                        "source",
                        "entry_version",
                        "created_at",
                        "updated_at",
                        "chunk_type",
                    )
                },
            )
            entries.append(entry)

        return entries[:limit]


# Re-exports
__all__ = [
    "Librarian",
    "ChunkMode",
]
