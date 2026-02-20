"""
omni.foundation.embedding.client - Embedding HTTP Client

Client for connecting to embedding HTTP server.
Used by lightweight MCP processes that don't load the embedding model.
"""

from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.request

import structlog
import aiohttp

from omni.foundation.config.settings import get_setting

logger = structlog.get_logger(__name__)


class EmbeddingClient:
    """HTTP client for remote embedding service."""

    def __init__(self, base_url: str | None = None):
        """Initialize the client.

        Args:
            base_url: Base URL of embedding HTTP server (default: from settings or localhost:18501)
        """
        self.base_url = base_url or get_setting("embedding.client_url")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def health_check(self) -> dict[str, Any]:
        """Check embedding server health with detailed diagnostics."""
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Embedding server healthy", url=self.base_url, status=data)
                    return {"status": "healthy", "server_url": self.base_url, **data}
                else:
                    error = await response.text()
                    logger.warning(
                        "Embedding server unhealthy",
                        url=self.base_url,
                        status=response.status,
                        error=error,
                    )
                    return {
                        "status": "unhealthy",
                        "server_url": self.base_url,
                        "error": error,
                        "code": response.status,
                    }
        except aiohttp.ClientError as e:
            logger.warning("Embedding server connection failed", url=self.base_url, error=str(e))
            return {"status": "unreachable", "server_url": self.base_url, "error": str(e)}
        except Exception as e:
            logger.error("Embedding health check error", url=self.base_url, error=str(e))
            return {"status": "error", "server_url": self.base_url, "error": str(e)}

    async def embed_batch(
        self, texts: list[str], timeout_seconds: float | None = None
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts via HTTP.

        Args:
            texts: Texts to embed.
            timeout_seconds: Request timeout in seconds (default from session; use 5–10 for recall).
        """
        session = await self._get_session()
        total = float(timeout_seconds) if timeout_seconds is not None else 60
        try:
            async with session.post(
                f"{self.base_url}/embed/batch",
                json={"texts": texts},
                timeout=aiohttp.ClientTimeout(total=total),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"Embedding server error: {error}")
                data = await response.json()
                return data.get("vectors", [])
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to connect to embedding server: {e}")

    async def embed(self, text: str) -> list[list[float]]:
        """Generate embedding for single text via HTTP."""
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/embed/single",
                json={"text": text},
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"Embedding server error: {error}")
                data = await response.json()
                return [data.get("vector", [])]
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to connect to embedding server: {e}")

    async def stats(self) -> dict[str, Any]:
        """Get embedding server stats."""
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/stats") as response:
                return await response.json()
        except aiohttp.ClientError as e:
            return {"status": "error", "error": str(e)}

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # Sync wrappers for use in non-async context
    def _sync_request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a synchronous JSON POST request."""
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Use shorter timeout when used from recall (avoids thread blocking 60s; recall layer has its own wait_for)
        _timeout = int(get_setting("knowledge.recall_embed_timeout_seconds", 5)) + 5
        _timeout = min(max(_timeout, 5), 60)
        try:
            with urllib.request.urlopen(req, timeout=_timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to embedding server: {e}") from e

    def sync_embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Synchronous batch embedding (client-only; used when MCP embedding service is already running)."""
        data = self._sync_request_json("/embed/batch", {"texts": texts})
        return data.get("vectors", [])

    def sync_embed(self, text: str) -> list[list[float]]:
        """Synchronous single-text embedding without asyncio bridging."""
        data = self._sync_request_json("/embed/single", {"text": text})
        return [data.get("vector", [])]


# Singleton client instance
_client: EmbeddingClient | None = None


def get_embedding_client(base_url: str | None = None) -> EmbeddingClient:
    """Get the singleton EmbeddingClient instance."""
    global _client
    if _client is None:
        _client = EmbeddingClient(base_url)
    return _client


async def close_embedding_client() -> None:
    """Close the singleton client."""
    global _client
    if _client:
        await _client.close()
        _client = None


__all__ = [
    "EmbeddingClient",
    "get_embedding_client",
    "close_embedding_client",
]
