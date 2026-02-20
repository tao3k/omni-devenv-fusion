"""
MCP embedding client for CLI commands.

When the user runs `omni mcp --port 3002` in the background, route test (and other
CLI flows) can use the already-warm embedding in that process instead of calling
Ollama directly, making the first embed much faster.

Supports:
- SSE server: POST to /messages/ (e.g. omni mcp --transport sse --port 3002)
- Stdio embedding HTTP server: POST to /message (legacy sidecar on 3001)
- MCP fast path: POST to /embed/batch on MCP SSE port (3002/3000)
- Dedicated embedding HTTP server: POST to /embed/batch on port 18501
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# Timeout for probe (detect whether MCP responds); keep short when no server is up.
PROBE_TIMEOUT_S = 3.0
# Timeout for actual embed requests.
REQUEST_TIMEOUT_S = 30.0

EMBEDDING_HTTP_PORT = 18501
_DEFAULT_MCP_PATHS = ("/messages/", "/message")
_MCP_HTTP_EMBED_PATHS = ("/embed", "/embed/batch")
_SHARED_HTTP_CLIENT = None
_SHARED_HTTP_CLIENT_LOCK = threading.Lock()
logger = logging.getLogger("omni.agent.cli.mcp_embed")


def _get_shared_http_client():
    """Get or create a process-level shared AsyncClient for local embedding calls."""
    global _SHARED_HTTP_CLIENT
    try:
        import httpx
    except Exception:
        return None

    with _SHARED_HTTP_CLIENT_LOCK:
        if _SHARED_HTTP_CLIENT is None or getattr(_SHARED_HTTP_CLIENT, "is_closed", False):
            _SHARED_HTTP_CLIENT = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)
        return _SHARED_HTTP_CLIENT


def _get_candidate_ports() -> list[int]:
    """Ports to try for MCP embedding, in order. Prefer config then common defaults."""
    try:
        from omni.foundation.config.settings import get_setting

        preferred = get_setting("mcp.preferred_embed_port")
        if preferred is not None:
            p = (
                int(preferred)
                if isinstance(preferred, (int, float))
                else int(str(preferred).strip())
            )
            if 0 < p < 65536:
                return [p]
    except Exception:
        pass
    return [3002, 3001, 3000]


def _mcp_paths_for_port(port: int) -> tuple[str, ...]:
    """Return MCP JSON-RPC HTTP paths in preferred order for a given port."""
    if int(port) == 3001:
        return ("/message", "/messages/")
    # Modern SSE MCP servers expose /messages/, /mcp and /.
    return ("/messages/", "/mcp", "/")


async def embed_via_mcp(
    texts: list[str],
    port: int,
    path: str = "/message",
    request_timeout_s: float = REQUEST_TIMEOUT_S,
) -> list[list[float]] | None:
    """Get embeddings via MCP server (SSE uses /messages/, stdio uses /message).

    Returns None if the server is unavailable or the response is invalid.
    """
    url = f"http://127.0.0.1:{port}{path}"
    try:
        client = _get_shared_http_client()
        if client is None:
            return None

        request = {
            "jsonrpc": "2.0",
            "id": "mcp-embed",
            "method": "tools/call",
            "params": {
                "name": "embedding.embed_texts",
                "arguments": {"texts": texts},
            },
        }
        response = await client.post(
            url,
            json=request,
            headers={"Content-Type": "application/json"},
            timeout=request_timeout_s,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("result"):
            content = result["result"].get("content", [])
            if content and isinstance(content, list):
                text_content = content[0].get("text", "")
                if text_content:
                    data = json.loads(text_content)
                    if data.get("success"):
                        return data.get("vectors")
        logger.debug(
            "MCP embed tool call returned no vectors",
            extra={"port": port, "path": path, "status_code": response.status_code},
        )
        return None
    except Exception as exc:
        logger.debug(
            "MCP embed tool call failed",
            extra={"port": port, "path": path, "error": str(exc), "url": url},
        )
        return None


async def embed_via_mcp_http(
    texts: list[str],
    port: int,
    request_timeout_s: float = REQUEST_TIMEOUT_S,
) -> list[list[float]] | None:
    """Get embeddings via MCP SSE direct HTTP endpoint (/embed or /embed/batch)."""
    for path in _MCP_HTTP_EMBED_PATHS:
        url = f"http://127.0.0.1:{port}{path}"
        try:
            client = _get_shared_http_client()
            if client is None:
                return None
            response = await client.post(
                url,
                json={"texts": texts},
                timeout=request_timeout_s,
            )
            if response.status_code == 200:
                data = response.json()
                vectors = data.get("vectors")
                if isinstance(vectors, list):
                    logger.debug(
                        "MCP direct embed endpoint selected",
                        extra={"port": port, "path": path, "status_code": response.status_code},
                    )
                    return vectors
            else:
                logger.debug(
                    "MCP direct embed endpoint not ready",
                    extra={"port": port, "path": path, "status_code": response.status_code},
                )
        except Exception as exc:
            logger.debug(
                "MCP direct embed endpoint failed",
                extra={"port": port, "path": path, "error": str(exc), "url": url},
            )
    return None


async def embed_via_http(
    texts: list[str],
    port: int = EMBEDDING_HTTP_PORT,
    request_timeout_s: float = REQUEST_TIMEOUT_S,
) -> list[list[float]] | None:
    """Get embeddings via dedicated embedding HTTP server (/embed or /embed/batch)."""
    for path in _MCP_HTTP_EMBED_PATHS:
        url = f"http://127.0.0.1:{port}{path}"
        try:
            client = _get_shared_http_client()
            if client is None:
                return None
            response = await client.post(
                url,
                json={"texts": texts},
                timeout=request_timeout_s,
            )
            if response.status_code == 200:
                data = response.json()
                vectors = data.get("vectors")
                if isinstance(vectors, list):
                    logger.debug(
                        "Embedding HTTP endpoint selected",
                        extra={"port": port, "path": path, "status_code": response.status_code},
                    )
                    return vectors
            else:
                logger.debug(
                    "Embedding HTTP endpoint unavailable",
                    extra={"port": port, "path": path, "status_code": response.status_code},
                )
        except Exception as exc:
            logger.debug(
                "Embedding HTTP endpoint failed",
                extra={"port": port, "path": path, "error": str(exc), "url": url},
            )
    return None


async def detect_embedding_http_port() -> int:
    """Return embedding HTTP server port (18501) if it is up and healthy, else 0."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        if sock.connect_ex(("127.0.0.1", EMBEDDING_HTTP_PORT)) != 0:
            return 0
    except Exception:
        return 0
    finally:
        sock.close()

    try:
        client = _get_shared_http_client()
        if client is None:
            return 0
        response = await client.get(f"http://127.0.0.1:{EMBEDDING_HTTP_PORT}/health", timeout=2.0)
        if response.status_code == 200:
            return EMBEDDING_HTTP_PORT
    except Exception:
        pass
    return 0


async def probe_mcp_embed_port(port: int) -> bool:
    """Return True if MCP on this port responds to embedding.embed_texts (tries /messages/ then /message)."""
    vectors = await embed_via_mcp_http(
        ["[DETECT]"],
        port=port,
        request_timeout_s=PROBE_TIMEOUT_S,
    )
    if vectors is not None:
        return True

    for path in _mcp_paths_for_port(port):
        vectors = await embed_via_mcp(
            ["[DETECT]"],
            port=port,
            path=path,
            request_timeout_s=PROBE_TIMEOUT_S,
        )
        if vectors is not None:
            return True
    return False


async def detect_mcp_port(candidate_ports: list[int] | None = None) -> int:
    """Detect a working MCP/embedding port.

    Tries dedicated embedding HTTP server (18501) first, then each candidate port
    (default: configured mcp.preferred_embed_port only when set, otherwise 3002/3001/3000).
    Returns the first port that responds, or 0.
    """
    port = await detect_embedding_http_port()
    if port > 0:
        return port

    candidates = candidate_ports if candidate_ports is not None else _get_candidate_ports()
    for p in candidates:
        if await probe_mcp_embed_port(p):
            return p
    return 0


def make_mcp_embed_func(port: int) -> Callable[[list[str]], Awaitable[list[list[float]]]]:
    """Return an async embed function that uses MCP or embedding HTTP on the given port, with local fallback."""

    async def _embed(texts: list[str]) -> list[list[float]]:
        if port == EMBEDDING_HTTP_PORT:
            vectors = await embed_via_http(texts, port)
            if vectors is not None:
                return vectors
        else:
            vectors = await embed_via_mcp_http(
                texts,
                port=port,
                request_timeout_s=REQUEST_TIMEOUT_S,
            )
            if vectors is not None:
                return vectors

            for path in _mcp_paths_for_port(port):
                vectors = await embed_via_mcp(
                    texts,
                    port,
                    path=path,
                    request_timeout_s=REQUEST_TIMEOUT_S,
                )
                if vectors is not None:
                    return vectors
        from omni.foundation.services.embedding import get_embedding_service

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: get_embedding_service().embed_batch(texts))

    return _embed
