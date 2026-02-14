"""
indexer.py - The Cortex Builder

Builds semantic index from skills' metadata and commands.
Uses RustVectorStore for high-performance vector operations.

Python 3.12+ Features:
- itertools.batched() for batch processing (Section 7.2)
- asyncio.TaskGroup for batch-internal parallelism (Section 7.3)
"""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel

try:
    import omni_core_rs as omni_rs

    _compute_hash = omni_rs.compute_hash
except ImportError:
    _compute_hash = None

from omni.foundation.bridge import RustVectorStore, SearchResult
from omni.foundation.config.logging import get_logger
from omni.foundation.services.vector_schema import parse_tool_search_payload

logger = get_logger("omni.core.router.indexer")

# Thread pool for blocking embedding operations (prevents event loop blocking)
_EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embedding")


@dataclass
class IndexedEntry:
    """An in-memory indexed entry used for test-only ':memory:' mode."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


class InMemoryIndex:
    """Simple in-memory index used only when storage_path == ':memory:'."""

    def __init__(self, dimension: int = 384):
        self._entries: list[IndexedEntry] = []
        self._dimension = dimension

    def add_batch(self, entries: list[tuple[str, dict[str, Any]]]) -> None:
        """Add a batch of entries."""
        for content, metadata in entries:
            self._entries.append(IndexedEntry(content=content, metadata=metadata))

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def search(self, query: str, embedding_service: Any, limit: int = 5) -> list[SearchResult]:
        """Keyword-style search for deterministic ':memory:' tests."""
        if not self._entries:
            return []

        query_words = set(query.lower().split())
        results = []
        for i, entry in enumerate(self._entries):
            content_lower = entry.content.lower()
            match_count = sum(1 for word in query_words if word in content_lower)
            if match_count > 0:
                score = min(0.9, match_count / max(len(query_words), 1))
                results.append(
                    SearchResult(
                        score=score,
                        payload=entry.metadata,
                        id=entry.metadata.get("id", f"entry_{i}"),
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def __len__(self) -> int:
        return len(self._entries)


class IndexedSkill(BaseModel):
    """Represents an indexed skill entry."""

    skill_name: str
    command_name: str | None
    content: str
    metadata: dict[str, Any]


class SkillIndexer:
    """
    [The Cortex Builder]

    Builds semantic index from all loaded skills.
    Indexes both skill descriptions and individual commands.
    Uses RustVectorStore for persisted paths, and in-memory index for ':memory:' tests.

    Smart Indexing:
    - Calculates hash of skills configuration
    - Saves metadata to .meta.json
    - Skips re-indexing if skills haven't changed
    - Reduces init time from ~200s to ~2s
    """

    def __init__(
        self,
        storage_path: str | None = None,
        dimension: int | None = None,
    ):
        """Initialize the skill indexer.

        Args:
            storage_path: Path to vector store (None = use unified path, ":memory:" for in-memory)
            dimension: Embedding dimension (default: from settings.yaml embedding.dimension)
        """
        from omni.foundation.config.settings import get_setting

        # Use unified base path if not specified (single skills table for routing and discovery).
        if storage_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            storage_path = str(get_vector_db_path())

        # Use dimension from settings.yaml (default to 1024 for LLM provider)
        if dimension is None:
            dimension = get_setting("embedding.dimension", 1024)

        self._storage_path = storage_path
        self._dimension = dimension
        self._store: RustVectorStore | None = None
        self._memory_index: InMemoryIndex | None = None
        self._indexed_count = 0

    @property
    def is_ready(self) -> bool:
        """Check if indexer is ready."""
        return self._store is not None or self._memory_index is not None

    @cached_property
    def _embedding_service(self) -> Any:
        """Lazily load and cache the embedding service."""
        from omni.foundation.services.embedding import get_embedding_service

        return get_embedding_service()

    def initialize(self) -> None:
        """Initialize the Rust vector store."""
        if self._store is not None or self._memory_index is not None:
            return

        if self._storage_path == ":memory:":
            self._memory_index = InMemoryIndex(dimension=self._dimension)
            logger.info("Cortex initialized in ':memory:' mode")
            return

        try:
            from omni.foundation.bridge.rust_vector import get_vector_store

            self._store = get_vector_store(
                self._storage_path,
                self._dimension,
                enable_keyword_index=True,
            )
            logger.info(f"Cortex initialized at {self._storage_path}")
        except RuntimeError as e:
            logger.error(f"RustVectorStore unavailable: {e}")

    async def index_skills(self, skills: list[dict[str, Any]]) -> int:
        """Index skills using batch operations for single commit.

        Performance:
        - Batches all entries into a single LanceDB commit
        - Smart Indexing: Checks hash to skip re-indexing unchanged skills
        - Reduces init time from ~200s to ~2s
        """
        self.initialize()

        if self._store is None and self._memory_index is None:
            logger.warning("Cannot index: vector store is unavailable")
            return 0

        # Smart Indexing: Calculate hash of current skills configuration
        # This prevents re-embedding static content on every startup
        current_hash = ""
        try:
            current_state = {
                "skills": sorted(
                    [
                        {
                            "name": s.get("name"),
                            "commands": sorted([c.get("name") for c in s.get("commands", [])]),
                            "description_hash": _compute_hash(s.get("description", ""))
                            if _compute_hash
                            else s.get("description", ""),
                            # Include routing keywords and intents in hash
                            "keywords_hash": _compute_hash(
                                json.dumps(s.get("routing_keywords", []), sort_keys=True)
                            )
                            if _compute_hash
                            else json.dumps(s.get("routing_keywords", []), sort_keys=True),
                            "intents_hash": _compute_hash(
                                json.dumps(s.get("intents", []), sort_keys=True)
                            )
                            if _compute_hash
                            else json.dumps(s.get("intents", []), sort_keys=True),
                        }
                        for s in skills
                    ],
                    key=lambda x: x["name"],
                )
            }
            current_hash = (
                _compute_hash(json.dumps(current_state, sort_keys=True))
                if _compute_hash
                else json.dumps(current_state, sort_keys=True)
            )

            # Check index metadata only if we have a valid storage path (not in-memory)
            if self._storage_path != ":memory:" and self._store is not None:
                meta_path = Path(self._storage_path).with_suffix(".meta.json")
                if meta_path.exists():
                    try:
                        saved_meta = json.loads(meta_path.read_text())
                        if saved_meta.get("hash") == current_hash:
                            self._indexed_count = saved_meta.get("count", 0)
                            logger.info(
                                f"Cortex index up-to-date ({self._indexed_count} entries), skipping build"
                            )
                            return self._indexed_count
                    except Exception:
                        pass  # Ignore read errors, proceed to index
        except Exception as e:
            logger.warning(f"Smart index check failed: {e}")

        # Collect all docs to index
        docs: list[dict[str, Any]] = []

        for skill in skills:
            skill_name = skill.get("name", "unknown")
            skill_desc = skill.get("description", "")
            entry_id = skill_name

            # Skill entry
            if skill_desc:
                content = f"Skill {skill_name}: {skill_desc}"
                docs.append(
                    {
                        "id": entry_id,
                        "content": content,
                        "metadata": {
                            "type": "skill",
                            "skill_name": skill_name,
                            "weight": 1.0,
                            "id": entry_id,
                        },
                    }
                )

            # Command entries
            for cmd in skill.get("commands", []):
                cmd_name_raw = cmd.get("name", "")
                cmd_name = str(cmd_name_raw).strip()
                if cmd_name.startswith(f"{skill_name}."):
                    cmd_name = cmd_name[len(skill_name) + 1 :]
                cmd_desc = cmd.get("description", "") or cmd_name
                cmd_keywords = list(cmd.get("routing_keywords", []) or [])
                # Inherit skill-level routing_keywords when command has none
                if not cmd_keywords and skill.get("routing_keywords"):
                    cmd_keywords = list(skill.get("routing_keywords", []))
                cmd_intents = skill.get("intents", [])  # Commands inherit skill intents

                # Optional: LLM enrichment to diversify routing_keywords (synonyms, related terms)
                try:
                    from omni.core.router.translate import enrich_routing_keywords

                    extra = await enrich_routing_keywords(cmd_desc, cmd_keywords)
                    if extra:
                        cmd_keywords = list(dict.fromkeys(cmd_keywords + extra))
                except Exception as e:
                    logger.debug("Enrichment skipped for command", cmd=cmd_name, error=str(e))

                # Field split for hybrid: vector = description (semantic), keyword = routing_keywords (BM25).
                # Embedding uses only COMMAND + DESCRIPTION + INTENTS so vector branch matches semantics.
                # Tantivy indexes description + routing_keywords (from metadata) with boost on keywords.
                doc_content = f"COMMAND: {skill_name}.{cmd_name}\n"
                doc_content += f"DESCRIPTION: {cmd_desc}\n"
                if cmd_intents:
                    doc_content += f"INTENTS: {', '.join(cmd_intents)}"

                cmd_id = f"{skill_name}.{cmd_name}" if cmd_name else entry_id

                # Match the metadata schema expected by Rust for Keyword Indexing
                metadata = {
                    "type": "command",
                    "skill_name": skill_name,
                    "tool_name": cmd_id,
                    "command": cmd_name,
                    "routing_keywords": cmd_keywords,
                    "intents": cmd_intents,
                    "weight": 2.0,
                    "id": cmd_id,
                }

                docs.append(
                    {
                        "id": cmd_id,
                        "content": doc_content,
                        "metadata": metadata,
                    }
                )

        if not docs:
            return 0

        if self._memory_index is not None:
            self._memory_index.clear()
            self._memory_index.add_batch([(d["content"], d["metadata"]) for d in docs])
            self._indexed_count = len(docs)
            return self._indexed_count

        # RustVectorStore: batch commit
        logger.info(f"Cortex batch indexing {len(docs)} entries...")

        # Compute embeddings in thread pool using embed_batch
        try:
            contents = [d["content"] for d in docs]

            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(
                _EMBEDDING_EXECUTOR, lambda: list(self._embedding_service.embed_batch(contents))
            )

            # Batch write to LanceDB (single commit)
            import json as _json

            await self._store.replace_documents(
                table_name="skills",
                ids=[d["id"] for d in docs],
                vectors=embeddings,
                contents=contents,
                metadatas=[_json.dumps(d["metadata"]) for d in docs],
            )
            self._indexed_count = len(docs)

            # Build and persist skill relationship graph (associative retrieval)
            try:
                from omni.core.router.skill_relationships import (
                    build_graph_from_docs,
                    get_relationship_graph_path,
                    save_relationship_graph,
                )

                graph_path = get_relationship_graph_path(self._storage_path)
                if graph_path is not None:
                    graph = build_graph_from_docs(docs)
                    if graph:
                        save_relationship_graph(graph, graph_path)
            except Exception as e:
                logger.debug("Skill relationship graph build skipped: %s", e)

            # Bridge 4: Register skill entities in KnowledgeGraph (Core 1 ← Core 2)
            try:
                from omni.rag.dual_core import register_skill_entities

                register_skill_entities(docs)
            except Exception as e:
                logger.debug("KnowledgeGraph entity registration skipped: %s", e)

            logger.info(f"Cortex indexed {len(docs)} entries (single commit)")

            # Save metadata for next run
            if self._storage_path != ":memory:" and current_hash:
                try:
                    meta_path = Path(self._storage_path).with_suffix(".meta.json")
                    meta_path.write_text(
                        json.dumps(
                            {
                                "hash": current_hash,
                                "count": self._indexed_count,
                                "timestamp": time.time(),
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to save index metadata: {e}")

        except Exception as e:
            logger.error(f"Failed to batch index Cortex: {e}")
            self._indexed_count = 0

        return self._indexed_count

    async def search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.0,
        intent_override: str | None = None,
    ) -> list[SearchResult]:
        """Search the index for matching skills/commands.

        Args:
            query: Search query
            limit: Maximum results
            threshold: Minimum score threshold
            intent_override: Optional intent hint (e.g. from an LLM). When set, used
                instead of rule-based classification ("exact", "semantic", "hybrid", "category").

        Returns:
            List of search results
        """
        if self._store is not None:
            # Use explicit Rust search_tools path (embed + hybrid retrieval).
            try:
                loop = asyncio.get_running_loop()
                query_embedding = await loop.run_in_executor(
                    _EMBEDDING_EXECUTOR,
                    self._embedding_service.embed,
                    query,
                )
                query_vector = (
                    query_embedding[0]
                    if query_embedding and isinstance(query_embedding[0], list)
                    else query_embedding
                )

                from omni.core.router.query_intent import classify_tool_search_intent

                intent = (
                    intent_override
                    if intent_override is not None
                    else classify_tool_search_intent(query)
                )
                if hasattr(self._store, "agentic_search"):
                    tool_results = await self._store.agentic_search(
                        table_name="skills",
                        query_vector=query_vector,
                        query_text=query,
                        limit=limit,
                        threshold=threshold,
                        intent=intent,
                    )
                else:
                    tool_results = await self._store.search_tools(
                        table_name="skills",
                        query_vector=query_vector,
                        query_text=query,
                        limit=limit,
                        threshold=threshold,
                    )

                results: list[SearchResult] = []
                for data in tool_results:
                    try:
                        parsed = parse_tool_search_payload(dict(data))
                    except Exception as exc:
                        logger.debug("Skipping invalid tool search payload: %s", exc)
                        continue

                    score = float(parsed.score)
                    if threshold > 0 and score < threshold:
                        continue
                    command = (
                        ".".join(parsed.tool_name.split(".")[1:])
                        if "." in parsed.tool_name
                        else parsed.tool_name
                    )
                    payload = {
                        "command": command,
                        "tool_name": parsed.tool_name,
                        "skill_name": parsed.skill_name,
                        "description": parsed.description,
                        "routing_keywords": list(parsed.routing_keywords),
                        "file_path": parsed.file_path,
                        "input_schema": dict(parsed.input_schema),
                        "schema": parsed.schema_version,
                    }
                    results.append(
                        SearchResult(
                            score=score,
                            payload=payload,
                            id=parsed.tool_name,
                        )
                    )
                return results
            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []
        if self._memory_index is not None:
            try:
                results = self._memory_index.search(query, self._embedding_service, limit=limit)
                if threshold > 0:
                    results = [r for r in results if r.score >= threshold]
                return results
            except Exception as e:
                logger.error(f"In-memory search failed: {e}")
                return []
        return []

    async def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        count = self._indexed_count
        if self._store is not None:
            with suppress(Exception):
                count = await self._store.count("skills")
        elif self._memory_index is not None:
            count = len(self._memory_index)

        return {
            "entries_indexed": count,
            "is_ready": self.is_ready,
            "storage_path": self._storage_path,
        }


__all__ = ["InMemoryIndex", "IndexedEntry", "IndexedSkill", "SkillIndexer"]
