"""
hybrid_search.py - Hybrid Search Engine (Rust-Native Implementation)

This module provides a thin Python shell over Rust's omni-vector search.
All heavy lifting (vector search, keyword rescue, scoring, fusion) is done in Rust.

Rust Benefits:
- Zero serialization overhead (no Python->Rust->Python data copying)
- High-performance L2 distance computation
- Integrated Tantivy BM25 keyword search
- Atomic hybrid scoring (Keyword Rescue pattern)

Architecture:
    User Query
        │
        ▼
    Embedding (Python)
        │
        ▼
    ┌─────────────────────────────────────────┐
    │         Rust omni-vector Search         │
    │  ┌─────────────────┬─────────────────┐  │
    │  │  LanceDB        │   Tantivy       │  │
    │  │  (Vector)       │   (Keyword)     │  │
    │  │  weight=1.0     │   weight=1.5    │  │
    │  └─────────────────┴─────────────────┘  │
    │                    │                    │
    │         Weighted RRF Fusion +          │
    │         Field Boosting                 │
    │  (NAME_TOKEN_BOOST=0.5,               │
    │   EXACT_PHRASE_BOOST=1.5)              │
    └─────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────┐
    │           Python Post-Processing        │
    │  - Contract validation                 │
    │  - Result formatting                   │
    └─────────────────────────────────────────┘
                    │
                    ▼
    List[dict] with: id, score, confidence, skill_name, command, etc.

Usage:
    search = HybridSearch()
    results = await search.search("git commit", limit=5)

    # With threshold filtering
    results = await search.search("find files", limit=10, min_score=0.4)

    # Check confidence
    for r in results:
        if r["confidence"] == "high":
            print(f"Best match: {r['id']} (score={r['score']:.2f})")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from omni.foundation.config.logging import get_logger
from omni.foundation.services.vector_schema import (
    build_tool_router_result,
    parse_tool_search_payload,
)

if TYPE_CHECKING:
    from omni.foundation.bridge.rust_vector import RustVectorStore

logger = get_logger("omni.core.router.hybrid")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)
_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")


def _is_routable_tool_name(value: str) -> bool:
    name = value.strip()
    if not name:
        return False
    if _UUID_RE.match(name):
        return False
    if not _TOOL_ID_RE.match(name):
        return False
    for segment in name.split("."):
        if _UUID_RE.match(segment):
            return False
    return any(ch.isalpha() for ch in name)


class HybridMatch:
    """Represents a match from hybrid search (Rust-native).

    This class is used internally by Rust-to-Python result conversion.
    In practice, results are returned as dicts from `search()` method.

    Attributes:
        id: Tool identifier in "skill.command" format (e.g., "git.commit").
        content: Tool description from indexed content.
        semantic_score: Raw vector similarity score from LanceDB (0.0-1.0).
        keyword_score: BM25 score from Tantivy keyword search.
        combined_score: Final Weighted RRF score after fusion and boosting.
        confidence: Human-readable confidence level ("high", "medium", "low").
        final_score: Display-calibrated score for UI/thresholding.
        metadata: Additional tool metadata (skill_name, file_path, etc.).
    """

    model_config = {"frozen": True}

    id: str
    content: str
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    confidence: str = "unknown"
    final_score: float = 0.0
    metadata: dict[str, Any] = {}


class HybridSearch:
    """Rust-Native Hybrid Search Engine.

    Thin Python shell over Rust omni-vector. All search logic is in Rust:
    - Vector similarity search (LanceDB with normalized vectors)
    - Keyword rescue (Tantivy BM25 for exact/partial matches)
    - Weighted RRF fusion with field boosting

    Rust performs all heavy computation; Python handles:
    - Embedding generation for vector search
    - Canonical payload validation for downstream consumers

    Intent extraction is handled by the discovery node LLM prompt.

    Example:
        ```python
        search = HybridSearch()

        # Basic search
        results = await search.search("find files", limit=5)

        # With threshold filtering
        results = await search.search(
            query="git commit",
            limit=10,
            min_score=0.4  # Only return medium+ confidence results
        )

        # Process results
        for r in results:
            if r["confidence"] == "high":
                print(f"Best: {r['id']} (score={r['score']:.2f})")
        ```

    Attributes:
        _store: Rust vector store instance (LanceDB + Tantivy).
        _embed_service: Lazy-loaded embedding service.

    See Also:
        - omni.core.router.main.OmniRouter: Higher-level router facade
        - omni.core.skills.discovery.SkillDiscoveryService: Tool discovery service
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """Initialize hybrid search with Rust vector store.

        The vector store is cached globally to avoid repeated initialization.
        Embedding service is loaded lazily on first use.
        """
        from omni.foundation.bridge.rust_vector import get_vector_store

        # Use get_vector_store() without path to use the default base path.
        # This ensures consistency with DiscoveryService which also uses the default path.
        # The Rust store will then correctly find skills.lance for the 'skills' table.
        resolved_storage_path = storage_path
        if storage_path and storage_path != ":memory:" and storage_path.endswith(".lance"):
            resolved_storage_path = str(Path(storage_path).parent)
        self._store = get_vector_store(resolved_storage_path)
        # Custom embedding function (set by CLI for MCP server access)
        self._embed_func: Callable[[list[str]], Awaitable[list[list[float]]]] | None = None

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        confidence_profile: dict[str, float] | None = None,
        rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search using Rust omni-vector engine.

        This method orchestrates the full hybrid search pipeline:
        1. Generate query embedding (semantic search)
        2. Normalize query for keyword search pipeline
        3. Call Rust search_tools for vector + keyword fusion
        4. Calibrate confidence levels for downstream consumers

        Args:
            query: Natural language search query (e.g., "find files matching 'pub updated'").
                The query is used both for semantic embedding and keyword matching.
            limit: Maximum number of results to return. Default is 5.
            min_score: Minimum combined score threshold (0.0-1.0). Results below this
                threshold are filtered out. Use 0.4 for "medium+" confidence only.
            rerank: Optional override for Rust metadata-aware rerank stage.
                None uses configured defaults.

        Returns:
            List of result dictionaries, sorted by score descending. Each dict contains:
            - id: Tool identifier (e.g., "git.commit")
            - content: Tool description
            - score: Raw RRF score from Rust (0.0-2.0+)
            - confidence: "high", "medium", or "low"
            - final_score: Display-calibrated score (0.0-1.0)
            - skill_name: Skill name (e.g., "git")
            - command: Command name (e.g., "commit")
            - file_path: Source file path
            - routing_keywords: Indexed routing keywords
            - input_schema: JSON schema for tool parameters
            - payload: Complete metadata for routing

        Example:
            ```python
            results = await search.search("git commit message", limit=3)
            for r in results:
                print(f"{r['id']}: {r['confidence']} (score={r['score']:.2f})")
            # Output:
            # git.commit: high (score=1.00)
            # git.smart_commit: high (score=0.95)
            ```

        Note:
            Query cleaning removes characters that cause Tantivy parse errors:
            quotes, brackets, parentheses, braces. The original query is used
            for embedding generation to preserve semantic meaning.

        See Also:
            - Rust omni-vector hybrid search for underlying algorithm
        """
        # Get query embedding (required for vector search)
        # Use custom embed function if set (e.g., for MCP server access)
        if self._embed_func is not None:
            # Custom embedding function (async)
            vectors = await self._embed_func([query])
            if vectors and len(vectors) > 0:
                query_vector = vectors[0]
            else:
                # Fallback to local embedding
                embed_service = self._get_embed_service()
                query_vector = embed_service.embed(query)[0]
        else:
            # Default: use local embedding service
            embed_service = self._get_embed_service()
            query_vector = embed_service.embed(query)[0]

        # Call Rust search_tools (does vector + keyword rescue + fusion)
        # Use cleaned query for keyword search to avoid Tantivy parse errors
        results = await self._store.search_tools(
            table_name="router",
            query_vector=query_vector,
            query_text=query,
            limit=limit,
            threshold=min_score,
            confidence_profile=confidence_profile,
            rerank=rerank,
        )

        # Format results for Python consumers
        formatted = []
        for raw in results:
            candidate = dict(raw)
            try:
                payload = parse_tool_search_payload(candidate)
            except Exception as exc:
                logger.debug(f"Skipping invalid tool search payload: {exc}")
                continue

            raw_score = payload.score
            confidence = payload.confidence
            final_score = payload.final_score

            # Canonicalize tool_name to "skill.command".
            # Prefer routed canonical name from payload.name when available.
            raw_tool_name = payload.tool_name.strip()
            canonical_name = payload.name.strip()
            if _is_routable_tool_name(canonical_name) and "." in canonical_name:
                full_tool_name = canonical_name
            elif "." not in raw_tool_name and payload.skill_name:
                full_tool_name = f"{payload.skill_name}.{raw_tool_name}"
            else:
                full_tool_name = raw_tool_name
            if not _is_routable_tool_name(full_tool_name):
                logger.debug("Skipping non-routable tool_name: %s", full_tool_name)
                continue
            command = (
                ".".join(full_tool_name.split(".")[1:]) if "." in full_tool_name else full_tool_name
            )
            if not command:
                continue

            router_result = build_tool_router_result(payload, full_tool_name)
            router_result["score"] = raw_score
            router_result["final_score"] = final_score
            router_result["confidence"] = confidence
            formatted.append(router_result)

        logger.debug(f"Hybrid search for '{query}': {len(formatted)} results")
        return formatted

    def _get_embed_service(self) -> Any:
        """Lazily load and return the embedding service.

        The embedding service is loaded on first use to avoid initialization
        overhead during module import. Thread-safe via double-checked locking.

        Returns:
            EmbeddingService: Service for generating query embeddings.

        Raises:
            RuntimeError: If embedding service cannot be initialized.
        """
        if not hasattr(self, "_embed_service"):
            from omni.foundation.services.embedding import get_embedding_service

            self._embed_service = get_embedding_service()
        return self._embed_service

    def set_weights(self, semantic: float, keyword: float) -> None:
        """Set search weights (reserved for future RRF configuration).

        Currently this method is a no-op. The search uses fixed weights
        defined in Rust (SEMANTIC_WEIGHT=1.0, KEYWORD_WEIGHT=1.5).

        This method exists for future extensibility if we want to expose
        weight configuration to Python callers.

        Args:
            semantic: Reserved for semantic search weight (currently ignored).
            keyword: Reserved for keyword search weight (currently ignored).

        Note:
            To modify weights, update the constants in Rust:
            - omni-vector/src/keyword.rs: SEMANTIC_WEIGHT, KEYWORD_WEIGHT
        """
        logger.info(f"Weights requested: semantic={semantic}, keyword={keyword}")
        logger.info("Note: runtime weights are Rust-owned; Python does not override them")

    def get_weights(self) -> tuple[float, float]:
        """Get the current search weights used by Rust.

        These are the fixed weights defined in Rust's omni-vector crate.

        Returns:
            Tuple of (semantic_weight, keyword_weight) = (1.0, 1.5).

        Note:
            The keyword weight is higher because exact keyword matches
            are more reliable indicators of relevance for tool search.
        """
        profile = self._store.get_search_profile()
        return (
            float(profile.get("semantic_weight", 1.0)),
            float(profile.get("keyword_weight", 1.5)),
        )

    def stats(self) -> dict[str, Any]:
        """Get hybrid search engine statistics and configuration.

        Returns a dictionary containing the current search configuration
        and algorithm parameters. Useful for debugging and monitoring.

        Returns:
            Dict with keys:
            - semantic_weight: Weight for vector search (1.0)
            - keyword_weight: Weight for keyword search (1.5)
            - rrf_k: RRF smoothing parameter (10)
            - implementation: Implementation name
            - strategy: Fusion strategy used
            - field_boosting: Token/phrase boost values
        """
        return self._store.get_search_profile()


__all__ = ["HybridSearch", "HybridMatch"]
