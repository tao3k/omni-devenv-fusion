"""
omni.core.skills.registry.holographic
The Holographic Registry: A view into the vector database.

Unlike traditional registries that hold all tools in memory, this registry
is "virtual" - it retrieves tool metadata from LanceDB on-demand (holographic projection).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import structlog

from omni.foundation.services.embedding import EmbeddingService, get_embedding_service

logger = structlog.get_logger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for a tool retrieved from the holographic registry."""

    name: str
    description: str
    module: str
    file_path: str
    args: list[dict[str, Any]]
    return_type: str
    score: float = 0.0

    @classmethod
    def from_record(cls, record: dict[str, Any], score: float = 0.0) -> "ToolMetadata":
        """Create from a database record."""
        metadata = record.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            name=metadata.get("name", ""),
            description=record.get("content", ""),
            module=metadata.get("module", ""),
            file_path=metadata.get("file_path", ""),
            args=metadata.get("args", []),
            return_type=metadata.get("return_type", "Any"),
            score=score,
        )


class HolographicRegistry:
    """Virtual tool registry backed by LanceDB vector store.

    This registry does NOT store tool objects in memory permanently.
    Instead, it projects tool metadata from the vector database on-demand,
    enabling:
    - Memory efficiency: Only metadata for active tools in memory
    - Hot updates: Changes to skills/ directory reflected immediately
    - Hybrid search: Semantic + keyword search via LanceDB

    Usage:
        registry = HolographicRegistry(vector_store, embedding_service)
        tools = await registry.search("file operations")
        tool = await registry.get_tool("file_read")
    """

    def __init__(
        self,
        vector_store: Any,  # PyVectorStore
        embedding_service: EmbeddingService | None = None,
    ):
        """Initialize the holographic registry.

        Args:
            vector_store: Rust PyVectorStore instance for persistence
            embedding_service: Optional EmbeddingService (singleton if not provided)
        """
        self.store = vector_store
        self.embedder = embedding_service or get_embedding_service()
        self.table_name = "skills_registry"

    async def search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.0,
        keywords: list[str] | None = None,
    ) -> list[ToolMetadata]:
        """Find tools using Rust-accelerated Hybrid Search (Vector + BM25).

        This method leverages omni-vector's native RRF (Reciprocal Rank Fusion)
        to combine semantic similarity with keyword matching.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)
            keywords: Optional keywords to boost keyword matching

        Returns:
            List of ToolMetadata sorted by relevance
        """
        try:
            # Step 1: Embed query using Python service
            query_vec = self.embedder.embed(query)
            if not query_vec:
                logger.warning("Failed to embed query")
                return []

            # Step 2: Use Rust Hybrid Search if keywords provided
            if keywords:
                # True hybrid search (Vector + Keyword via RRF)
                results = self.store.search_hybrid(
                    table_name=self.table_name,
                    query=query_vec[0],
                    keywords=keywords,
                    limit=limit,
                )

                # Parse results
                tools: list[ToolMetadata] = []
                for json_str in results:
                    try:
                        record = json.loads(json_str)
                        score = record.get("score", 0.0)
                        tool = ToolMetadata.from_record(record, score)
                        tools.append(tool)
                    except json.JSONDecodeError:
                        continue

                logger.debug(f"Hybrid search found {len(tools)} tools for query: {query}")
                return tools

            # Fallback to vector-only search
            results = self.store.search_tools(
                table_name=self.table_name,
                query_vector=query_vec[0],
                query_text=None,
                limit=limit,
                threshold=threshold,
            )

            # Convert to ToolMetadata
            tools: list[ToolMetadata] = []
            for record in results:
                if hasattr(record, "get"):
                    score = record.get("score", 0.0)
                    tool = ToolMetadata.from_record(dict(record), score)
                    tools.append(tool)

            logger.debug(f"Vector search found {len(tools)} tools for query: {query}")
            return tools

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    async def search_hybrid(
        self,
        query: str,
        keywords: list[str],
        limit: int = 5,
    ) -> list[ToolMetadata]:
        """Hybrid search combining semantic and keyword matching.

        Args:
            query: Natural language search query
            keywords: Keywords to boost in search
            limit: Maximum number of results

        Returns:
            List of ToolMetadata with hybrid scoring
        """
        try:
            # Embed query
            query_vec = self.embedder.embed(query)
            if not query_vec:
                return []

            # Hybrid search via Rust
            results = self.store.search_hybrid(
                table_name=self.table_name,
                query=query_vec[0],
                keywords=keywords,
                limit=limit,
            )

            # Parse results
            tools: list[ToolMetadata] = []
            for json_str in results:
                try:
                    record = json.loads(json_str)
                    score = record.get("score", 0.0)
                    tool = ToolMetadata.from_record(record, score)
                    tools.append(tool)
                except json.JSONDecodeError:
                    continue

            return tools

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    async def get_tool(self, name: str) -> ToolMetadata | None:
        """Exact lookup by tool name.

        Args:
            name: Tool name to find

        Returns:
            ToolMetadata if found, None otherwise
        """
        try:
            # Filtered search via Rust
            results = self.store.search_filtered(
                table_name=self.table_name,
                query=[0.0] * self.embedder.dimension,  # Dummy vector for exact match
                limit=1,
                where_filter=f"metadata.name = '{name}'",
            )

            if not results:
                return None

            # Parse first result
            for json_str in results:
                try:
                    record = json.loads(json_str)
                    metadata = record.get("metadata", {})
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)

                    if metadata.get("name") == name:
                        return ToolMetadata.from_record(record)
                except json.JSONDecodeError:
                    continue

            return None

        except Exception as e:
            logger.error(f"Failed to get tool '{name}': {e}")
            return None

    async def list_tools(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolMetadata]:
        """List tools from the registry with pagination.

        Args:
            limit: Maximum number of results
            offset: Skip first N results

        Returns:
            List of ToolMetadata
        """
        try:
            # Use search with neutral query for listing
            neutral_query = "tool function"
            query_vec = self.embedder.embed(neutral_query)

            if not query_vec:
                return []

            results = self.store.search_tools(
                table_name=self.table_name,
                query_vector=query_vec[0],
                query_text=None,
                limit=limit + offset,
                threshold=0.0,
            )

            tools: list[ToolMetadata] = []
            for i, record in enumerate(results):
                if i < offset:
                    continue
                if hasattr(record, "get"):
                    score = record.get("score", 0.0)
                    tool = ToolMetadata.from_record(dict(record), score)
                    tools.append(tool)

            return tools

        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []

    async def count(self) -> int:
        """Get total number of tools in the registry.

        Returns:
            Count of indexed tools
        """
        try:
            return self.store.count(self.table_name)
        except Exception as e:
            logger.error(f"Failed to count tools: {e}")
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict with registry stats
        """
        return {
            "table_name": self.table_name,
            "tool_count": await self.count(),
            "embedding_backend": self.embedder.backend,
            "embedding_dimension": self.embedder.dimension,
        }


class LazyTool:
    """A lazy-loaded tool that imports its implementation on first access.

    This enables true "holographic" behavior - the actual code is only
    loaded when the tool is invoked, not when searching/discovering.
    """

    def __init__(
        self,
        metadata: ToolMetadata,
        registry: HolographicRegistry,
    ):
        """Initialize lazy tool wrapper.

        Args:
            metadata: Tool metadata from registry
            registry: Registry instance for potential re-fetch
        """
        self.metadata = metadata
        self._registry = registry
        self._implementation: Any = None

    async def load(self) -> Any:
        """Load the actual tool implementation.

        Returns:
            The loaded tool function/class
        """
        if self._implementation is not None:
            return self._implementation

        try:
            # Dynamic import of the module
            import importlib
            from pathlib import Path

            module_path = Path(self.metadata.module)
            if module_path.suffix == "":
                module_path = module_path.with_suffix(".py")

            # Add to path if needed
            if str(module_path.parent) not in __import__("sys").path:
                __import__("sys").path.insert(0, str(module_path.parent))

            # Import module
            module_name = module_path.stem
            module = importlib.import_module(module_name)

            # Get the tool function
            func_name = self.metadata.name
            if hasattr(module, func_name):
                self._implementation = getattr(module, func_name)
                return self._implementation

            logger.warning(f"Function {func_name} not found in {module_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to load tool {self.metadata.name}: {e}")
            return None

    @property
    def name(self) -> str:
        """Tool name."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Tool description (docstring)."""
        return self.metadata.description

    @property
    def args(self) -> list[dict[str, Any]]:
        """Tool argument schema."""
        return self.metadata.args
