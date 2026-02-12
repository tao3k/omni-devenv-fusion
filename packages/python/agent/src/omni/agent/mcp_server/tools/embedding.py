"""
embedding.py - Embedding MCP Tool

Exposes the preloaded embedding service via MCP protocol.
The embedding model is preloaded when MCP server starts for fast queries.

Usage:
    - CLI commands call this tool via MCP to get embeddings
    - Avoids reloading the ~7GB model for each command
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent

logger = logging.getLogger("omni.agent.mcp_server.tools.embedding")


def register_embedding_tools(app: Server) -> None:
    """Register embedding-related MCP tools.

    Args:
        app: MCP Server instance
    """

    @app.call_tool()
    async def embed_texts(arguments: dict) -> list[Any]:
        """Generate embeddings using the preloaded embedding service.

        This tool is used internally by CLI commands that need embeddings
        without reloading the model. The model is preloaded when MCP server starts.

        Args:
            texts: List of text strings to embed

        Returns:
            JSON array of embedding vectors (2560 dimensions for Qwen3-Embedding-4B)
        """
        try:
            texts = arguments.get("texts", [])
            if not texts:
                return [TextContent(type="text", text="Error: 'texts' parameter required")]

            from omni.foundation.services.embedding import get_embedding_service

            embed_service = get_embedding_service()
            vectors = embed_service.embed_batch(texts)

            logger.debug(f"[MCP] Generated {len(vectors)} embeddings (dim={len(vectors[0])})")
            return [TextContent(type="text", text=json.dumps(vectors))]

        except Exception as e:
            logger.error(f"embed_texts failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @app.call_tool()
    async def embed_single(arguments: dict) -> list[Any]:
        """Generate a single embedding for text.

        Convenience wrapper for single text embedding.

        Args:
            text: Text string to embed

        Returns:
            Single embedding vector as JSON array
        """
        try:
            text = arguments.get("text", "")
            if not text:
                return [TextContent(type="text", text="Error: 'text' parameter required")]

            from omni.foundation.services.embedding import get_embedding_service

            embed_service = get_embedding_service()
            vectors = embed_service.embed(text)

            # Return first (and only) embedding
            vector = vectors[0] if vectors else []
            logger.debug(f"[MCP] Generated single embedding (dim={len(vector)})")
            return [TextContent(type="text", text=json.dumps(vector))]

        except Exception as e:
            logger.error(f"embed_single failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    logger.info("📦 Embedding tools registered (embed_texts, embed_single)")


__all__ = ["register_embedding_tools"]
