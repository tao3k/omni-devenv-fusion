"""
omni.foundation.embedding - Unified Embedding Service

Provides text embedding using local sentence-transformers models.
Supports two modes:
1. Local mode: Load model directly (default)
2. Client mode: Connect to remote embedding HTTP server

Auto-detection:
- First MCP: starts HTTP server immediately, loads model after MCP is connected
- Other MCPs: detect port in use, automatically connect as clients

Configuration (settings.yaml):
- embedding.provider: "" (auto), "client", "fallback"
- embedding.model: HuggingFace model name
- embedding.dimension: Vector dimension
- embedding.http_port: HTTP server port (default: 18501)
"""

from __future__ import annotations

import os
import sys
import threading
from errno import EADDRINUSE

# Workaround for Python 3.13 + torch.distributed compatibility issue
if sys.version_info >= (3, 13):
    if "TORCH_DISTRIBUTED_DETECTION" not in os.environ:
        os.environ["TORCH_DISTRIBUTED_DETECTION"] = "1"

from typing import Any

import structlog

from omni.foundation.config.prj import PRJ_DATA
from omni.foundation.config.settings import get_setting

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Singleton service for generating text embeddings.

    Auto-detection behavior:
    - First process: starts HTTP server immediately, loads model after start_model_loading()
    - Other processes: detect server, connect as client
    """

    _instance: "EmbeddingService | None" = None
    _model: Any = None
    _dimension: int = 1024
    _truncate_dim: int | None = None  # MRL dimension truncation
    _backend: str = "local"
    _initialized: bool = False
    _client_mode: bool = False
    _client_url: str | None = None
    _http_server_started: bool = False
    _model_loading: bool = False
    _model_loaded: bool = False
    _port_conflict_logged: bool = False
    _load_lock: threading.Lock
    _embed_cache_key: str | None = None
    _embed_cache_value: list[list[float]] | None = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_lock = threading.Lock()
        return cls._instance

    def _is_port_in_use(self, port: int, timeout: float = 0.5) -> bool:
        """Check if a port is already in use."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (socket.timeout, ConnectionRefusedError):
                return False
            except Exception:
                return False

    def _check_http_server_healthy(self, url: str, timeout: float = 1.0) -> bool:
        """Synchronously check if HTTP server is healthy (single request, short timeout)."""
        import json
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(f"{url}/health", timeout=timeout) as response:
                if response.status != 200:
                    return False
                payload = response.read().decode("utf-8")
                data = json.loads(payload) if payload else {}
                status = str(data.get("status", "")).lower()
                return status in {"healthy", "ok"}
        except (urllib.error.URLError, TimeoutError, ValueError):
            return False

    def _is_address_in_use_error(self, exc: Exception) -> bool:
        """Return True when exception indicates HTTP port is already bound."""
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in {
            EADDRINUSE,
            48,  # macOS
            98,  # Linux
            10048,  # Windows
        }:
            return True
        return "address already in use" in str(exc).lower()

    def initialize(self) -> None:
        """Initialize embedding service with auto-detection.

        Flow:
        1. Check explicit provider override (client/fallback/local)
        2. Auto-detect: Check if HTTP port is in use
        3. Health check: Verify server is responsive
        4. Connect or start server accordingly
        """
        if self._initialized:
            return

        provider = get_setting("embedding.provider", "").lower()
        http_port = get_setting("embedding.http_port", 18501)
        http_url = f"http://127.0.0.1:{http_port}"

        # Handle explicit overrides
        if provider == "client":
            self._client_mode = True
            self._client_url = get_setting("embedding.client_url", http_url)
            self._backend = "http"
            self._dimension = get_setting("embedding.dimension", 1024)
            self._initialized = True
            logger.info("Embedding: force client mode", client_url=self._client_url)
            return

        if provider == "fallback":
            self._backend = "fallback"
            self._dimension = get_setting("embedding.dimension", 1024)
            self._initialized = True
            logger.info("Embedding: force fallback mode")
            return

        port_in_use = self._is_port_in_use(http_port)
        logger.info("Embedding: auto-detecting", port=http_port, port_in_use=port_in_use)

        if port_in_use:
            # Port is in use - perform health check to verify server is responsive
            server_healthy = self._check_http_server_healthy(http_url)

            if server_healthy:
                # Server is healthy, connect as client
                self._client_mode = True
                self._client_url = http_url
                self._backend = "http"
                self._dimension = get_setting("embedding.dimension", 1024)
                self._initialized = True
                logger.info(
                    "✓ Embedding: auto-detected healthy HTTP server, using client mode",
                    server_url=self._client_url,
                )
            else:
                # Port in use but server not healthy - start our own
                logger.info("Embedding: port in use but server unhealthy, retrying HTTP startup")
                self._start_http_server_immediate(http_port)
        else:
            # No server running, start HTTP server immediately
            logger.info("Embedding: no existing server, starting HTTP server...")
            self._start_http_server_immediate(http_port)

    def _start_http_server_immediate(self, http_port: int) -> None:
        """Start HTTP server immediately (no model loading yet)."""
        self._initialized = True
        self._http_server_started = True

        def _run_server():
            """Run HTTP server in background thread."""
            from omni.foundation.embedding_server import EmbeddingHTTPServer
            from omni.foundation.utils.asyncio import run_async_blocking

            async def _main():
                server = EmbeddingHTTPServer(port=http_port)
                await server.start()
                # HTTP server is running, now wait for model loading signal
                # Keep server running forever
                import asyncio

                while True:
                    await asyncio.sleep(3600)

            try:
                run_async_blocking(_main())
            except Exception as e:
                if self._is_address_in_use_error(e):
                    # Benign race: another process bound the port between detection and bind.
                    if not self._port_conflict_logged:
                        logger.info(
                            "Embedding HTTP server already running; switching to client mode",
                            port=http_port,
                        )
                        self._port_conflict_logged = True
                    self._client_mode = True
                    self._client_url = f"http://127.0.0.1:{http_port}"
                    self._backend = "http"
                    self._dimension = get_setting("embedding.dimension", 1024)
                    self._http_server_started = False
                else:
                    logger.warning(f"Embedding HTTP server error: {e}")

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()
        logger.info(f"Embedding HTTP server started on port {http_port}")

    def start_model_loading(self) -> None:
        """Start loading the model in background.

        Call this after MCP connection is fully established.
        This triggers model loading without blocking the MCP server.
        """
        # Skip if in client mode (using HTTP server)
        if self._client_mode:
            logger.debug("Embedding: skipping model load in client mode")
            return

        # Use lock to prevent race conditions
        with self._load_lock:
            if self._model_loaded or self._model_loading:
                return

            self._model_loading = True
            logger.info("Embedding: starting model loading in background...")

        def _load_model_bg():
            """Load model in background thread."""
            try:
                self._load_local_model()
                logger.info("Embedding: model loading complete")
            except Exception as e:
                logger.warning(f"Embedding model loading error: {e}")
                with self._load_lock:
                    self._model_loading = False

        thread = threading.Thread(target=_load_model_bg, daemon=True)
        thread.start()

    def _load_local_model(self) -> None:
        """Load the sentence-transformers model.

        Thread-safe with proper locking to prevent concurrent loads.
        """
        # Fast path: already loaded
        if self._model_loaded:
            return

        # Acquire lock to prevent concurrent loading
        with self._load_lock:
            # Double-check after acquiring lock
            if self._model_loaded:
                return

            # Mark as loading
            self._model_loading = True

            # Set HuggingFace cache
            self._cache_dir = str(PRJ_DATA("models"))
            os.environ["HF_HOME"] = self._cache_dir
            os.environ["HF_DATASETS_CACHE"] = str(PRJ_DATA("datasets"))
            os.makedirs(self._cache_dir, exist_ok=True)

            model_name = get_setting("embedding.model", "Qwen/Qwen3-Embedding-0.6B")

            # [FIX] Memory optimization settings from config
            device_setting = get_setting("embedding.device", "auto")
            dtype_setting = get_setting("embedding.torch_dtype", "float16")
            quantize = get_setting("embedding.quantize", None)

            logger.info(
                "Loading embedding model",
                model=model_name,
                cache_dir=self._cache_dir,
                device_setting=device_setting,
                dtype_setting=dtype_setting,
                quantize=quantize or "none",
            )

            try:
                import torch
                from sentence_transformers import SentenceTransformer

                # Resolve device: "auto" detects MPS on Apple Silicon
                if device_setting == "auto":
                    device = "mps" if torch.backends.mps.is_available() else "cpu"
                else:
                    device = device_setting

                # Resolve dtype: FP16 requires MPS, otherwise FP32
                if dtype_setting == "float16" and device == "mps":
                    dtype = torch.float16
                else:
                    dtype = torch.float32

                # Build model kwargs with optional quantization
                model_kwargs: dict[str, Any] = {"dtype": dtype}
                if quantize == "int8":
                    model_kwargs["load_in_8bit"] = True
                elif quantize == "int4":
                    model_kwargs["load_in_4bit"] = True

                # MRL dimension truncation - Note: Qwen3-Embedding doesn't support
                # truncate_dim in model init, so we apply it in encode() instead
                truncate_dim = get_setting("embedding.truncate_dim", None)
                if truncate_dim:
                    self._truncate_dim = truncate_dim

                self._model = SentenceTransformer(
                    model_name,
                    device=device,
                    model_kwargs=model_kwargs,
                )
                self._backend = "local"
                # Use truncate_dim if set, otherwise use model's native dimension
                if truncate_dim:
                    self._dimension = truncate_dim
                    self._truncate_dim = truncate_dim
                else:
                    self._dimension = self._model.get_sentence_embedding_dimension() or 1024
                self._model_loaded = True
                logger.info(
                    "Embedding model loaded",
                    model=model_name,
                    dimension=self._dimension,
                    truncate_dim=truncate_dim,
                    device=device,
                    dtype=str(dtype),
                    quantize=quantize or "none",
                )

            except Exception as e:
                logger.error(f"Failed to load embedding model {model_name}: {e}")
                self._backend = "fallback"
                self._dimension = get_setting("embedding.dimension", 1024)
                self._model_loaded = True
            finally:
                self._model_loading = False

    def _auto_detect_and_init(self) -> None:
        """Auto-detect HTTP embedding server with a single health check (fast path).

        One GET /health with short timeout; no separate port check.
        """
        if self._initialized:
            return

        http_port = get_setting("embedding.http_port", 18501)
        http_url = f"http://127.0.0.1:{http_port}"

        if self._check_http_server_healthy(http_url, timeout=1.0):
            self._client_mode = True
            self._client_url = http_url
            self._backend = "http"
            self._dimension = get_setting("embedding.dimension", 1024)
            self._initialized = True
            logger.info(
                "✓ Embedding: auto-detected healthy MCP server, using client mode",
                server_url=self._client_url,
            )
        else:
            self.initialize()

    def embed(self, text: str) -> list[list[float]]:
        """Generate embedding for text."""
        if not self._initialized:
            self._auto_detect_and_init()

        # Single-slot cache for repeated same query (e.g. route test retries)
        if self._embed_cache_key is not None and self._embed_cache_key == text:
            if self._embed_cache_value is not None:
                return self._embed_cache_value

        if self._client_mode:
            out = self._embed_http_with_fallback([text])
        else:
            if not self._model_loaded:
                self._load_local_model()
            out = self._embed_local([text])

        self._embed_cache_key = text
        self._embed_cache_value = out
        return out

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        if self._backend != "local" or self._model is None:
            return self._embed_fallback(texts)

        embeddings = self._model.encode(texts, normalize_embeddings=True)

        # Apply MRL dimension truncation if configured
        if self._truncate_dim is not None:
            embeddings = embeddings[:, : self._truncate_dim]

        return embeddings.tolist()

    def _embed_fallback(self, texts: list[str]) -> list[list[float]]:
        """Generate hash-based pseudo-embeddings."""
        import hashlib

        result = []
        dim = self._dimension

        for text in texts:
            hash_val = hashlib.sha256(text.encode()).hexdigest()
            vector = [
                float(int(hash_val[i : i + 8], 16) % 1000) / 1000.0
                for i in range(0, min(len(hash_val), dim * 8), 8)
            ]
            while len(vector) < dim:
                vector.append(0.0)
            result.append(vector[:dim])
        return result

    def _embed_http(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via HTTP client."""
        from omni.foundation.embedding_client import get_embedding_client

        client = get_embedding_client(self._client_url)
        return client.sync_embed_batch(texts)

    def _embed_http_with_fallback(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via HTTP, with graceful fallback on failure."""
        try:
            return self._embed_http(texts)
        except Exception as exc:
            logger.warning(
                "Embedding HTTP unavailable; switching to fallback embedding",
                error=str(exc),
                client_url=self._client_url,
            )
            self._client_mode = False
            self._backend = "fallback"
            self._dimension = get_setting("embedding.dimension", self._dimension or 1024)
            return self._embed_fallback(texts)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Auto-detect MCP server if not already initialized
        if not self._initialized:
            self._auto_detect_and_init()

        if self._client_mode:
            return self._embed_http_with_fallback(texts)

        # Load model if needed (thread-safe with lock)
        if not self._model_loaded:
            self._load_local_model()
        return self._embed_local(texts)

    def embed_force_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using only the local model (no HTTP/MCP client).

        Use this when dimension must match the vector index (e.g. route test with
        --local after `omni sync`). Bypasses auto-detected MCP/HTTP to avoid
        dimension mismatch (client may return a different dimension than the index).
        """
        if not texts:
            return []
        saved_client = self._client_mode
        saved_initialized = self._initialized
        try:
            self._client_mode = False
            if not self._initialized:
                self._initialized = True
                self._backend = "fallback"
                self._dimension = get_setting("embedding.dimension", 1024)
            if not self._model_loaded:
                self._load_local_model()
            return self._embed_local(texts)
        finally:
            self._client_mode = saved_client
            self._initialized = saved_initialized

    @property
    def backend(self) -> str:
        """Return the embedding backend."""
        return self._backend

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model_loaded

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._model_loading


# Singleton accessor
_service: "EmbeddingService | None" = None


def get_embedding_service() -> EmbeddingService:
    """Get the singleton EmbeddingService instance."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


# Convenience functions
def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text."""
    return get_embedding_service().embed(text)[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    return get_embedding_service().embed_batch(texts)


def get_dimension() -> int:
    """Get the current embedding dimension."""
    return get_embedding_service().dimension


__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "embed_text",
    "embed_batch",
    "get_dimension",
]
