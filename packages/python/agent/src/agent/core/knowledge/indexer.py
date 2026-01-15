"""
agent/core/knowledge/indexer.py
 The Knowledge Matrix - Markdown Document Indexer

Indexes Markdown documents into LanceDB for semantic search.

Features:
- File-level and Section-level chunking
- Frontmatter extraction
- SHA256 hash for incremental updates
- Metadata enrichment

Usage:
    from agent.core.knowledge.indexer import scan_markdown_files, extract_markdown_schema

    # Scan and index docs
    records = scan_markdown_files("docs/")
    chunks = extract_markdown_schema(record)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

# Try to import frontmatter, fallback to simple parsing
try:
    import frontmatter

    FRONTMATTER_AVAILABLE = True
except ImportError:
    FRONTMATTER_AVAILABLE = False


@dataclass
class DocRecord:
    """A scanned Markdown document."""

    id: str  # file_path relative to root
    file_path: str  # Full path
    content: str  # Full content (with frontmatter)
    body: str  # Just the body (without frontmatter)
    file_hash: str  # SHA256 of content
    metadata: Dict[str, Any]  # Frontmatter metadata
    title: str = ""  # Extracted title


@dataclass
class DocChunk:
    """A chunk of a document for indexing."""

    id: str  # e.g., "docs/api.md#chunk-0"
    doc_id: str  # Parent document ID
    content: str  # Chunk text content
    file_hash: str  # Parent document hash
    metadata: Dict[str, Any]  # Inherited from document
    section_title: str = ""  # Section header if available


# Minimum chunk size to avoid noise
MIN_CHUNK_SIZE = 50


def scan_markdown_files(root_dir: str) -> List[DocRecord]:
    """
    Scan directory for Markdown files and extract metadata.

    Args:
        root_dir: Root directory to scan (e.g., "docs/")

    Returns:
        List of DocRecord objects
    """
    root = Path(root_dir)
    if not root.exists():
        return []

    records: List[DocRecord] = []

    for path in root.rglob("*.md"):
        # Skip certain directories
        skip_patterns = [".git", "node_modules", ".cache", "__pycache__"]
        if any(p in path.parts for p in skip_patterns):
            continue

        try:
            content = path.read_text(encoding="utf-8")
            file_hash = hashlib.sha256(content.encode()).hexdigest()

            # Parse frontmatter
            metadata: Dict[str, Any] = {}
            body = content
            title = ""

            if FRONTMATTER_AVAILABLE:
                try:
                    post = frontmatter.loads(content)
                    metadata = dict(post.metadata)
                    body = post.content
                except Exception:
                    pass
            else:
                # Simple frontmatter parsing
                if content.startswith("---"):
                    end_marker = content.find("---", 4)
                    if end_marker > 0:
                        fm_content = content[4:end_marker]
                        body = content[end_marker + 3 :]
                        for line in fm_content.split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                metadata[key.strip()] = value.strip()

            # Extract title from first # heading or metadata
            title = metadata.get("title", "")
            if not title:
                h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
                if h1_match:
                    title = h1_match.group(1).strip()

            # Create relative ID
            rel_path = str(path.relative_to(root))

            records.append(
                DocRecord(
                    id=rel_path,
                    file_path=str(path),
                    content=content,
                    body=body,
                    file_hash=file_hash,
                    metadata=metadata,
                    title=title,
                )
            )
        except Exception as e:
            print(f"Warning: Failed to scan {path}: {e}")

    return records


def extract_markdown_schema(record: DocRecord, strategy: str = "section") -> List[Dict[str, Any]]:
    """
    Convert a DocRecord into vector store records (chunks).

    Args:
        record: DocRecord to process
        strategy: Chunking strategy ("file", "section", "paragraph")

    Returns:
        List of dictionaries suitable for LanceDB insertion
    """
    chunks: List[Dict[str, Any]] = []

    if strategy == "file":
        # Single chunk for entire document
        chunks.append(
            _make_chunk(
                doc_id=record.id,
                chunk_idx=0,
                content=record.body,
                file_hash=record.file_hash,
                metadata=_build_metadata(record, ""),
            )
        )
    else:
        # Section-based chunking
        sections = _split_by_headers(record.body)

        for idx, section in enumerate(sections):
            if len(section.strip()) < MIN_CHUNK_SIZE:
                continue

            chunks.append(
                _make_chunk(
                    doc_id=record.id,
                    chunk_idx=idx,
                    content=section,
                    file_hash=record.file_hash,
                    metadata=_build_metadata(record, _extract_section_title(section)),
                )
            )

    return chunks


def _split_by_headers(text: str) -> List[str]:
    """
    Split text by Markdown headers (##).

    Returns list of sections (including header).
    """
    # Split by ## at the beginning of a line
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)

    # First part is before any ## (title/intro)
    if parts[0].strip():
        # If there's content before first ##, it might be an H1 title
        # Check if it starts with #
        h1_match = re.match(r"^#\s+(.+)$", parts[0].strip(), re.MULTILINE)
        if h1_match:
            # Content before first ## is just the H1 title, skip it for sections
            sections = ["## " + p for p in parts[1:]] if len(parts) > 1 else []
        else:
            sections = [parts[0]] + ["## " + p for p in parts[1:] if p.strip()]
    else:
        sections = ["## " + p for p in parts if p.strip()]

    return sections


def _extract_section_title(section: str) -> str:
    """Extract section title from section text."""
    # Section starts with ## Title
    match = re.match(r"^##\s+(.+)$", section, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def _make_chunk(
    doc_id: str,
    chunk_idx: int,
    content: str,
    file_hash: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a chunk record for LanceDB."""
    chunk_id = f"{doc_id}#chunk-{chunk_idx}"

    # Truncate content for embedding ( LanceDB handles large text, but we want clean storage)
    # Keep full content for retrieval
    preview = content[:200].replace("\n", " ").strip() + "..."

    # Sanitize metadata for JSON serialization
    def _sanitize(value: Any) -> Any:
        """Convert non-JSON-serializable values to strings."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [_sanitize(v) for v in value]
        if isinstance(value, dict):
            return {k: _sanitize(v) for k, v in value.items()}
        # Convert any other type to string
        return str(value)

    sanitized = _sanitize(metadata)

    return {
        "id": chunk_id,
        "doc_id": doc_id,
        "content": content,
        "preview": preview,
        "file_hash": file_hash,
        "metadata": json.dumps(sanitized, ensure_ascii=False),
        "type": "knowledge",
        **sanitized,  # Flatten metadata for easier querying
    }


def _build_metadata(record: DocRecord, section_title: str) -> Dict[str, Any]:
    """Build metadata for a chunk."""
    return {
        "title": record.title,
        "section": section_title,
        "doc_path": record.id,
        "source_file": record.file_path,
        **record.metadata,
    }


def get_existing_hashes(store: Any, table_name: str) -> Dict[str, str]:
    """
    Get existing file hashes from vector store.

    Args:
        store: omni_vector store instance
        table_name: Table to query

    Returns:
        Dict mapping doc_id -> file_hash
    """
    try:
        if hasattr(store, "get_all_file_hashes"):
            result = store.get_all_file_hashes(table_name)
            if result:
                return json.loads(result)
        # Fallback: return empty
        return {}
    except Exception:
        return {}


async def sync_knowledge(
    store: Any,
    docs_dir: str,
    table_name: str = "knowledge",
) -> Dict[str, int]:
    """
    Incrementally sync knowledge documents.

    Args:
        store: omni_vector store instance
        docs_dir: Directory containing Markdown files
        table_name: Table to store in

    Returns:
        Dict with keys: added, updated, deleted, total
    """
    # Step 1: Get existing hashes from DB
    existing = get_existing_hashes(store, table_name)

    # Step 2: Scan filesystem
    records = scan_markdown_files(docs_dir)

    # Step 3: Compute diff
    current_ids = {r.id for r in records}
    existing_ids = set(existing.keys())

    to_add = [r for r in records if r.id not in existing_ids]
    to_update = [r for r in records if r.id in existing_ids and existing[r.id] != r.file_hash]
    to_delete = existing_ids - current_ids

    stats = {"added": 0, "updated": 0, "deleted": 0, "total": len(records)}

    # Step 4: Execute changes
    if to_delete:
        ids_to_delete = list(to_delete)
        if hasattr(store, "delete_by_doc_id"):
            store.delete_by_doc_id(ids_to_delete, table_name)
        stats["deleted"] = len(ids_to_delete)

    work_items = to_add + to_update
    if work_items:
        all_chunks: List[Dict[str, Any]] = []

        for record in work_items:
            chunks = extract_markdown_schema(record)
            all_chunks.extend(chunks)

        if all_chunks:
            # Generate embeddings and add to store
            from agent.core.vector_store import VectorMemory

            vm = VectorMemory()

            ids = [c["id"] for c in all_chunks]
            contents = [c["content"] for c in all_chunks]
            # Filter out non-serializable metadata (like datetime objects)
            metadatas = []
            for c in all_chunks:
                meta = {k: v for k, v in c.items() if k not in ["id", "content"]}
                # Convert non-JSON-serializable values
                for k, v in meta.items():
                    if hasattr(v, "__dict__"):
                        meta[k] = str(v)
                metadatas.append(meta)

            # Use VectorMemory.add() method
            await vm.add(
                documents=contents,
                ids=ids,
                collection=table_name,
                metadatas=metadatas,
            )

            stats["added"] = len(to_add)
            stats["updated"] = len(to_update)

    return stats


__all__ = [
    "DocRecord",
    "DocChunk",
    "scan_markdown_files",
    "extract_markdown_schema",
    "sync_knowledge",
]
