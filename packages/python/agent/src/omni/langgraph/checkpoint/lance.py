"""
omni/langgraph/checkpoint/lance.py - LanceDB-based Checkpoint Storage

Provides high-performance checkpoint persistence using LanceDB via Rust bindings:
- Semantic state search (find similar historical states)
- Experience recall (learn from past successful solutions)
- Thread-safe access with in-memory caching

Usage:
    from omni.langgraph.checkpoint.lance import LanceCheckpointer

    checkpointer = LanceCheckpointer()
    checkpointer.put("session_123", state)
    saved = checkpointer.get("session_123")
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.config.dirs import PRJ_CACHE

# Try to import Rust bindings
try:
    import omni_core_rs as _rust

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    _rust = None  # type: ignore


logger = get_logger("omni.langgraph.checkpoint.lance")

# Lazy import for embedding service
_cached_embedder: Any | None = None


def _get_embedder() -> Any | None:
    """Get the embedding service lazily."""
    global _cached_embedder
    if _cached_embedder is None:
        try:
            from omni.foundation.services.embedding import EmbeddingService

            _cached_embedder = EmbeddingService()
        except ImportError:
            _cached_embedder = None
    return _cached_embedder


class LanceCheckpointer:
    """
    LanceDB-based Checkpoint Storage for LangGraph workflows.

    Uses Rust bindings for high-performance LanceDB operations.
    Enables semantic search over checkpoint history.

    Features:
    - Thread-safe access
    - Automatic checkpoint history (parent links)
    - Semantic state search capability
    - Experience recall from historical checkpoints
    """

    def __init__(
        self,
        uri: Path | str | None = None,
        dimension: int = 1536,
    ):
        """
        Initialize the LanceDB checkpointer.

        Args:
            uri: Path to LanceDB directory (auto-generated if not provided)
            dimension: Embedding dimension for semantic search (default: 1536)
        """
        if not RUST_AVAILABLE:
            raise RuntimeError(
                "Rust bindings (omni_core_rs) not available. "
                "Please build the Rust bindings first: just build-rust-dev"
            )

        if uri is None:
            uri = PRJ_CACHE("agent", "checkpoints.lance")

        if isinstance(uri, Path):
            uri = str(uri)

        self._uri = uri
        self._dimension = dimension

        # Create the Rust checkpoint store
        self._inner = _rust.create_checkpoint_store(uri, dimension)
        logger.info("lance_checkpointer_initialized", uri=uri, dimension=dimension)

    def put(
        self,
        thread_id: str,
        state: dict[str, Any],
        checkpoint_id: str | None = None,
        parent_checkpoint_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Save a checkpoint for the given thread.

        Args:
            thread_id: Session/thread identifier
            state: State dictionary to save
            checkpoint_id: Optional checkpoint ID (auto-generated if not provided)
            parent_checkpoint_id: Parent checkpoint ID for history chain
            metadata: Optional metadata dict

        Returns:
            checkpoint_id: The ID of the saved checkpoint
        """
        checkpoint_id = checkpoint_id or str(uuid.uuid4())[:8]
        timestamp = time.time()

        # Serialize state to JSON
        state_json = json.dumps(state, default=str)

        # Prepare metadata - merge user metadata with system fields
        meta = dict(metadata) if metadata else {}
        if parent_checkpoint_id:
            meta["parent_id"] = parent_checkpoint_id

        # Compute embedding from content for semantic search
        embedding = None
        try:
            embedder = _get_embedder()
            if embedder is not None:
                # Extract searchable text from state
                search_text = state.get("current_plan", "") or json.dumps(state)
                if search_text:
                    embedding = embedder.embed(search_text)[0]  # Returns list[list[float]]
        except Exception as e:
            logger.debug("failed_to_compute_embedding_for_checkpoint", error=str(e))

        # Serialize merged metadata
        metadata_json = json.dumps(meta) if meta else None

        # Call Rust binding with embedding
        self._inner.save_checkpoint(
            table_name="checkpoints",
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            content=state_json,
            timestamp=timestamp,
            parent_id=parent_checkpoint_id,
            embedding=embedding,
            metadata=metadata_json,
        )

        logger.debug(
            "checkpoint_saved",
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
        )

        return checkpoint_id

    def get(self, thread_id: str) -> dict[str, Any] | None:
        """
        Get the latest checkpoint for a thread.

        Args:
            thread_id: Session/thread identifier

        Returns:
            State dictionary or None if not found
        """
        result = self._inner.get_latest("checkpoints", thread_id)
        if result:
            return json.loads(result)
        return None

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Get a specific checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID

        Returns:
            State dictionary or None if not found
        """
        result = self._inner.get_by_id("checkpoints", checkpoint_id)
        if result:
            return json.loads(result)
        return None

    def get_history(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get checkpoint history for a thread (newest first).

        Args:
            thread_id: Session/thread identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of state dictionaries
        """
        results = self._inner.get_history("checkpoints", thread_id, limit)
        return [json.loads(r) for r in results]

    def delete(self, thread_id: str) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Session/thread identifier

        Returns:
            Number of checkpoints deleted
        """
        count = self._inner.delete_thread("checkpoints", thread_id)
        logger.info("checkpoints_deleted", thread_id=thread_id, count=count)
        return count

    def count(self, thread_id: str) -> int:
        """
        Count checkpoints for a thread.

        Args:
            thread_id: Session/thread identifier

        Returns:
            Number of checkpoints
        """
        return self._inner.count("checkpoints", thread_id)

    def search_similar(
        self,
        query_vector: list[float],
        thread_id: str | None = None,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar historical checkpoints using vector similarity.

        Uses Rust-accelerated L2 distance computation over LanceDB.

        Args:
            query_vector: Query embedding vector
            thread_id: Optional thread ID to filter results (None = all threads)
            limit: Maximum number of results
            filter_metadata: Optional metadata filter (e.g., {"success": true})

        Returns:
            List of dicts with keys: content, metadata, distance
        """
        import json

        # Convert filter to JSON string
        filter_json = json.dumps(filter_metadata) if filter_metadata else None

        # Call Rust search
        results = self._inner.search(
            "checkpoints",
            query_vector,
            limit,
            thread_id,
            filter_json,
        )

        # Parse results
        parsed = []
        for r in results:
            data = json.loads(r)
            parsed.append(
                {
                    "content": json.loads(data["content"]),
                    "metadata": json.loads(data["metadata"]),
                    "distance": data["distance"],
                }
            )

        logger.debug(
            "semantic_search_completed",
            query_vector_len=len(query_vector),
            thread_id=thread_id,
            results_count=len(parsed),
        )

        return parsed

    @property
    def uri(self) -> str:
        """Get the LanceDB URI."""
        assert self._uri is not None, "URI should never be None after initialization"
        return self._uri
