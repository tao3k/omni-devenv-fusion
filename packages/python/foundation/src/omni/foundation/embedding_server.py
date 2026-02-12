"""
omni.foundation.embedding.server - Embedding HTTP Server

Provides HTTP API for sharing embedding model across multiple MCP processes.
Only the main process loads the model; other processes connect via HTTP.

Configuration (settings.yaml):
- embedding.http_port: Port for HTTP server (default: 18501)
- embedding.mode: "server" (main process) or "client" (connect to server)
"""

from __future__ import annotations

import logging

import structlog
from aiohttp import web

from omni.foundation.config.settings import get_setting

logger = structlog.get_logger(__name__)


class EmbeddingHTTPServer:
    """HTTP server exposing embedding operations.

    Run this in the main MCP process that loads the embedding model.
    Other MCP processes connect as clients to get embeddings.
    """

    def __init__(self, port: int | None = None):
        """Initialize HTTP server.

        Args:
            port: HTTP server port (default: from settings.yaml or 18501)
        """
        self.port = port or get_setting("embedding.http_port", 18501)
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

    async def _setup_routes(self) -> None:
        """Setup HTTP routes."""

        async def embed_batch(request: web.Request) -> web.Response:
            """Generate embeddings for multiple texts."""
            try:
                data = await request.json()
                texts = data.get("texts", [])
                if not texts:
                    return web.json_response({"error": "texts required"}, status=400)

                from omni.foundation.services.embedding import get_embedding_service

                embed_service = get_embedding_service()
                vectors = embed_service.embed_batch(texts)

                return web.json_response(
                    {
                        "vectors": vectors,
                        "count": len(vectors),
                        "dimension": len(vectors[0]) if vectors else 0,
                    }
                )
            except Exception as e:
                logger.error(f"HTTP embed_batch failed: {e}")
                return web.json_response({"error": str(e)}, status=500)

        async def embed_single(request: web.Request) -> web.Response:
            """Generate embedding for single text."""
            try:
                data = await request.json()
                text = data.get("text", "")
                if not text:
                    return web.json_response({"error": "text required"}, status=400)

                from omni.foundation.services.embedding import get_embedding_service

                embed_service = get_embedding_service()
                vectors = embed_service.embed(text)

                return web.json_response(
                    {
                        "vector": vectors[0] if vectors else [],
                        "dimension": len(vectors[0]) if vectors else 0,
                    }
                )
            except Exception as e:
                logger.error(f"HTTP embed_single failed: {e}")
                return web.json_response({"error": str(e)}, status=500)

        async def health(request: web.Request) -> web.Response:
            """Health check endpoint."""
            return web.json_response(
                {
                    "status": "ok",
                    "port": self.port,
                    "running": self._running,
                }
            )

        async def stats(request: web.Request) -> web.Response:
            """Get embedding service stats."""
            try:
                from omni.foundation.services.embedding import get_embedding_service

                embed_service = get_embedding_service()
                return web.json_response(
                    {
                        "backend": embed_service.backend,
                        "dimension": embed_service.dimension,
                        "is_loaded": embed_service.is_loaded,
                        "model_loaded": embed_service._model is not None,
                    }
                )
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        self._app = web.Application()
        self._app.router.add_post("/embed/batch", embed_batch)
        self._app.router.add_post("/embed/single", embed_single)
        self._app.router.add_get("/health", health)
        self._app.router.add_get("/stats", stats)

    async def start(self) -> None:
        """Start the HTTP server."""
        if self._running:
            logger.warning("Embedding HTTP server already running")
            return

        await self._setup_routes()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await self._site.start()

        self._running = True
        logger.info(f"Embedding HTTP server started on port {self.port}")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            self._running = False
            logger.info("Embedding HTTP server stopped")


# Singleton server instance
_server: EmbeddingHTTPServer | None = None


def get_embedding_server() -> EmbeddingHTTPServer:
    """Get the singleton EmbeddingHTTPServer instance."""
    global _server
    if _server is None:
        _server = EmbeddingHTTPServer()
    return _server


async def start_embedding_server(port: int | None = None) -> EmbeddingHTTPServer:
    """Start the embedding HTTP server."""
    server = get_embedding_server()
    if port:
        server.port = port
    await server.start()
    return server


async def stop_embedding_server() -> None:
    """Stop the embedding HTTP server."""
    global _server
    if _server:
        await _server.stop()
        _server = None


__all__ = [
    "EmbeddingHTTPServer",
    "get_embedding_server",
    "start_embedding_server",
    "stop_embedding_server",
]
