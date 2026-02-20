"""
omni.foundation.embedding - Unified Embedding Service

Embeddings via LiteLLM only (Ollama, Xinference, or other backends). No in-process
model loading; run the model in Ollama or Xinference and point LiteLLM at it.

Configuration (packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml):
- embedding.provider: "ollama" | "xinference" | "litellm" (LiteLLM), "client" (HTTP), "fallback", "" (auto)
- embedding.litellm_model: e.g. "ollama/nomic-embed-text", "xinference/<uid>" (Xinference deploys Qwen etc.)
- embedding.litellm_api_base: e.g. "http://127.0.0.1:11434" (Ollama), "http://127.0.0.1:9997/v1" (Xinference)
- embedding.dimension: must match model (768 nomic, 1024 Qwen3-Embedding-0.6B)
"""

from __future__ import annotations

import os
import time
from contextvars import ContextVar
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import structlog

from omni.foundation.config.settings import get_setting

logger = structlog.get_logger(__name__)

# Context override so skill execution can use MCP-first embedding (set by agent via skill hooks).
_embedding_override: ContextVar[Any | None] = ContextVar("embedding_override", default=None)


class EmbeddingOverrideProtocol(Protocol):
    """Protocol for embedding override (e.g. MCP-first wrapper). Used during skill execution."""

    def embed(self, text: str) -> list[list[float]]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


def get_embedding_override() -> EmbeddingOverrideProtocol | None:
    """Return the current embedding override, if any (used by skill execution path)."""
    return _embedding_override.get()


def set_embedding_override(provider: EmbeddingOverrideProtocol | None) -> None:
    """Set the embedding override for the current context (e.g. MCP-first when running skills from CLI)."""
    _embedding_override.set(provider)


class EmbeddingUnavailableError(Exception):
    """Raised when embedding HTTP service is unavailable and fallback is disabled."""


class EmbeddingPortInUseError(Exception):
    """Raised when embedding port is in use by a non-embedding service. User must change port."""


class EmbeddingService:
    """Singleton embedding service. Uses LiteLLM (Ollama/Xinference) for local models; no in-process load."""

    _instance: "EmbeddingService | None" = None
    _dimension: int = 1024
    _backend: str = "fallback"
    _initialized: bool = False
    _client_mode: bool = False
    _client_url: str | None = None
    _embed_cache_key: str | None = None
    _embed_cache_value: list[list[float]] | None = None
    _litellm_model: str | None = None
    _litellm_api_base: str | None = None
    _client_retried: bool = False
    _litellm_circuit_open_until: float = 0.0
    _litellm_last_error: str | None = None

    @staticmethod
    def _default_litellm_api_base(provider: str) -> str | None:
        if provider == "ollama":
            ollama_host = (os.environ.get("OLLAMA_HOST") or "").strip()
            if ollama_host:
                if "://" not in ollama_host:
                    ollama_host = f"http://{ollama_host}"
                return ollama_host.rstrip("/")
            return "http://127.0.0.1:11434"
        if provider == "xinference":
            return "http://127.0.0.1:9997/v1"
        return None

    @staticmethod
    def _normalize_loopback_api_base(
        api_base: str | None,
        *,
        is_ollama: bool,
    ) -> str | None:
        """Normalize local loopback hostnames to reduce localhost/IPv6 ambiguity."""
        if not api_base or not is_ollama:
            return api_base
        raw = api_base if "://" in api_base else f"http://{api_base}"
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        if host not in {"localhost", "0.0.0.0", "::"}:
            return api_base
        port = parsed.port or 11434
        netloc = f"127.0.0.1:{port}"
        normalized = urlunsplit(
            (parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment)
        )
        return normalized

    @staticmethod
    def _loopback_alias_candidates(
        api_base: str | None,
        *,
        is_ollama: bool,
    ) -> list[str | None]:
        if not api_base:
            return [None]
        if not is_ollama:
            return [api_base]
        raw = api_base if "://" in api_base else f"http://{api_base}"
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        port = parsed.port or 11434
        path = parsed.path
        query = parsed.query
        fragment = parsed.fragment
        scheme = parsed.scheme or "http"
        candidates: list[str | None] = [api_base]
        if host == "localhost":
            alt = urlunsplit((scheme, f"127.0.0.1:{port}", path, query, fragment))
            if alt not in candidates:
                candidates.append(alt)
        elif host == "127.0.0.1":
            alt = urlunsplit((scheme, f"localhost:{port}", path, query, fragment))
            if alt not in candidates:
                candidates.append(alt)
        return candidates

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
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

    def _verify_embedding_service_works(self, url: str, timeout: float = 5.0) -> bool:
        """Verify embedding service actually returns vectors (real client connectivity test).

        Health check alone is insufficient: /health may pass while /embed/single fails
        (e.g. wrong service on port, model not loaded). Only use client mode if we get
        a real embedding back.
        """
        import json
        import urllib.error
        import urllib.request

        try:
            body = json.dumps({"text": "_probe"}).encode("utf-8")
            req = urllib.request.Request(
                f"{url}/embed/single",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    return False
                payload = response.read().decode("utf-8")
                data = json.loads(payload) if payload else {}
                vector = data.get("vector", [])
                if not isinstance(vector, list) or len(vector) < 1:
                    return False
                return all(isinstance(x, (int, float)) for x in vector[:10])
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError):
            return False

    def initialize(self) -> None:
        """Initialize embedding service: LiteLLM, HTTP client, or fallback. No in-process model."""
        if self._initialized:
            return

        provider = (get_setting("embedding.provider") or "").lower()
        http_port = int(get_setting("embedding.http_port"))
        http_url = get_setting("embedding.client_url") or f"http://127.0.0.1:{http_port}"

        # LiteLLM backend
        if provider in ("ollama", "xinference", "litellm"):
            self._backend = "litellm"
            self._litellm_model = get_setting("embedding.litellm_model") or (
                "ollama/nomic-embed-text"
                if provider == "ollama"
                else "xinference/bge-base-en"
                if provider == "xinference"
                else str(get_setting("embedding.model") or "ollama/nomic-embed-text")
            )
            raw_api_base = get_setting(
                "embedding.litellm_api_base"
            ) or self._default_litellm_api_base(provider)
            self._litellm_api_base = self._normalize_loopback_api_base(
                raw_api_base,
                is_ollama=provider == "ollama" or str(self._litellm_model).startswith("ollama/"),
            )
            self._dimension = int(get_setting("embedding.dimension"))
            self._initialized = True
            logger.info(
                "Embedding: LiteLLM backend",
                model=self._litellm_model,
                api_base=self._litellm_api_base,
            )
            return

        if provider == "client":
            client_url = get_setting("embedding.client_url") or http_url
            if self._check_http_server_healthy(
                client_url, timeout=2.0
            ) and self._verify_embedding_service_works(client_url, timeout=5.0):
                self._client_mode = True
                self._client_url = client_url
                self._backend = "http"
                self._dimension = int(get_setting("embedding.dimension"))
                self._initialized = True
                logger.info("Embedding: client mode", client_url=self._client_url)
            else:
                if os.environ.get("OMNI_EMBEDDING_CLIENT_ONLY") == "1":
                    self._backend = "unavailable"
                    self._dimension = int(get_setting("embedding.dimension"))
                    self._initialized = True
                    logger.warning(
                        "Embedding: client_url unreachable; client-only, embedding unavailable."
                    )
                else:
                    raise EmbeddingUnavailableError(
                        f"embedding.client_url unreachable: {client_url}. "
                        "Start an embedding server (e.g. Ollama) or set embedding.provider=ollama/fallback."
                    )
            return

        if provider == "fallback":
            self._backend = "fallback"
            self._dimension = int(get_setting("embedding.dimension"))
            self._initialized = True
            logger.info("Embedding: fallback mode")
            return

        # Auto: try HTTP server on default port, else fallback
        if self._is_port_in_use(http_port):
            if self._check_http_server_healthy(http_url) and self._verify_embedding_service_works(
                http_url, timeout=5.0
            ):
                self._client_mode = True
                self._client_url = http_url
                self._backend = "http"
                self._dimension = int(get_setting("embedding.dimension"))
                self._initialized = True
                logger.info("Embedding: auto client mode", server_url=self._client_url)
            else:
                raise EmbeddingPortInUseError(
                    f"Port {http_port} is in use but not a working embedding service. "
                    "Change embedding.http_port or set embedding.provider=ollama/fallback."
                )
        else:
            # No server on port: use fallback so route test/reindex work without Ollama
            self._backend = "fallback"
            self._dimension = int(get_setting("embedding.dimension"))
            self._initialized = True
            logger.info(
                "Embedding: auto fallback (no server on port); set provider=ollama for LiteLLM"
            )

    def _retry_client_once(self) -> None:
        """When backend is unavailable and provider is client, try once to connect to client_url.

        Allows the embedding server to start after MCP (e.g. sidecar on 3302); first embed
        will retry and use client mode if the server is now reachable.
        """
        if self._backend != "unavailable" or self._client_retried:
            return
        provider = (get_setting("embedding.provider") or "").lower()
        if provider != "client":
            return
        self._client_retried = True
        http_port = int(get_setting("embedding.http_port"))
        client_url = get_setting("embedding.client_url") or f"http://127.0.0.1:{http_port}"
        if self._check_http_server_healthy(
            client_url, timeout=2.0
        ) and self._verify_embedding_service_works(client_url, timeout=5.0):
            self._client_mode = True
            self._client_url = client_url
            self._backend = "http"
            self._dimension = int(get_setting("embedding.dimension"))
            logger.info(
                "Embedding: client mode (reconnected on first embed)", client_url=self._client_url
            )

    def start_model_loading(self) -> None:
        """No-op: embeddings via LiteLLM (Ollama/Xinference), no in-process model."""

    def reset_litellm_circuit(self) -> None:
        """Clear transient LiteLLM circuit state after upstream recovery."""
        self._litellm_circuit_open_until = 0.0
        self._litellm_last_error = None

    def _auto_detect_and_init(self) -> None:
        """Auto-detect HTTP embedding server or use config (client-only when MCP already running).

        When provider is "client", trust config and skip health check so first
        recall does not pay an extra GET /health round-trip (MCP backend already
        has the model loaded). This path is client-only: no server startup, no
        local model load, no locks — just HTTP client to the existing MCP service.
        Otherwise one GET /health with short timeout, then client mode.
        """
        if self._initialized:
            return

        provider = (get_setting("embedding.provider") or "").lower()
        http_port = int(get_setting("embedding.http_port"))
        http_url = get_setting("embedding.client_url") or f"http://127.0.0.1:{http_port}"

        if provider in ("ollama", "xinference", "litellm"):
            self._backend = "litellm"
            self._litellm_model = get_setting("embedding.litellm_model") or (
                "ollama/nomic-embed-text"
                if provider == "ollama"
                else "xinference/bge-base-en"
                if provider == "xinference"
                else str(get_setting("embedding.model") or "ollama/nomic-embed-text")
            )
            raw_api_base = get_setting(
                "embedding.litellm_api_base"
            ) or self._default_litellm_api_base(provider)
            self._litellm_api_base = self._normalize_loopback_api_base(
                raw_api_base,
                is_ollama=provider == "ollama" or str(self._litellm_model).startswith("ollama/"),
            )
            self._dimension = int(get_setting("embedding.dimension"))
            self._initialized = True
            logger.info(
                "Embedding: LiteLLM backend (no in-process model)",
                model=self._litellm_model,
                api_base=self._litellm_api_base,
            )
            return

        if provider == "client":
            if self._check_http_server_healthy(
                http_url, timeout=2.0
            ) and self._verify_embedding_service_works(http_url, timeout=5.0):
                self._client_mode = True
                self._client_url = http_url
                self._backend = "http"
                self._dimension = int(get_setting("embedding.dimension"))
                self._initialized = True
                logger.info(
                    "✓ Embedding: client mode (health + embed verified)", url=self._client_url
                )
            else:
                if os.environ.get("OMNI_EMBEDDING_CLIENT_ONLY") == "1":
                    self._backend = "unavailable"
                    self._dimension = int(get_setting("embedding.dimension"))
                    self._initialized = True
                    logger.warning(
                        "Embedding: client_url unreachable; client-only mode, embedding unavailable.",
                        url=http_url,
                    )
                else:
                    logger.warning(
                        "Embedding: client_url unreachable or embed test failed; will use initialize() path.",
                        url=http_url,
                    )
                    self.initialize()
            return

        if self._check_http_server_healthy(
            http_url, timeout=1.0
        ) and self._verify_embedding_service_works(http_url, timeout=5.0):
            self._client_mode = True
            self._client_url = http_url
            self._backend = "http"
            self._dimension = int(get_setting("embedding.dimension"))
            self._initialized = True
            logger.info(
                "✓ Embedding: verified working server, using client mode",
                server_url=self._client_url,
            )
        else:
            if os.environ.get("OMNI_EMBEDDING_CLIENT_ONLY") == "1":
                self._backend = "unavailable"
                self._dimension = int(get_setting("embedding.dimension"))
                self._initialized = True
                logger.warning(
                    "Embedding: no server reachable; client-only mode, embedding unavailable."
                )
            else:
                self.initialize()

    def embed(self, text: str) -> list[list[float]]:
        """Generate embedding for text."""
        override = get_embedding_override()
        if override is not None:
            return override.embed(text)

        if not self._initialized:
            self._auto_detect_and_init()

        # Single-slot cache for repeated same query (e.g. route test retries)
        if self._embed_cache_key is not None and self._embed_cache_key == text:
            if self._embed_cache_value is not None:
                return self._embed_cache_value

        if self._backend == "unavailable":
            self._retry_client_once()
            if self._backend == "unavailable":
                _url = (
                    get_setting("embedding.client_url")
                    or f"http://127.0.0.1:{int(get_setting('embedding.http_port') or 18501)}"
                )
                raise EmbeddingUnavailableError(
                    f"Embedding unavailable (client-only mode). Run an embedding server at {_url} "
                    "(GET /health, POST /embed/single) or set embedding.provider=ollama."
                )
        if self._backend == "litellm":
            out = self._embed_litellm([text])
        elif self._client_mode:
            out = self._embed_http([text])
        else:
            out = self._embed_fallback([text])

        self._embed_cache_key = text
        self._embed_cache_value = out
        return out

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
        """Generate embeddings via HTTP client. Raises EmbeddingUnavailableError on failure."""
        from omni.foundation.embedding_client import get_embedding_client

        try:
            client = get_embedding_client(self._client_url)
            return client.sync_embed_batch(texts)
        except Exception as exc:
            raise EmbeddingUnavailableError(
                f"Embedding HTTP service unavailable at {self._client_url}: {exc}"
            ) from exc

    def _embed_litellm(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via LiteLLM (Ollama, Xinference, or other backends). No in-process model."""
        import litellm

        if self._litellm_model is None:
            raise EmbeddingUnavailableError(
                "LiteLLM embedding not configured (embedding.litellm_model missing)."
            )
        now = time.monotonic()
        if self._litellm_circuit_open_until > now:
            remaining = self._litellm_circuit_open_until - now
            last_error = self._litellm_last_error or "unknown"
            raise EmbeddingUnavailableError(
                "LiteLLM embedding temporarily unavailable "
                f"(circuit_open_remaining_secs={remaining:.1f}, model={self._litellm_model}, "
                f"api_base={self._litellm_api_base}, last_error={last_error})"
            )
        timeout: float = float(get_setting("embedding.timeout") or 60)
        retry_attempts = max(1, int(get_setting("embedding.litellm_connect_retries") or 2))
        retry_backoff_ms = max(0, int(get_setting("embedding.litellm_retry_backoff_ms") or 250))
        circuit_open_secs = max(
            1.0, float(get_setting("embedding.litellm_circuit_open_secs") or 5.0)
        )
        provider = str(get_setting("embedding.provider") or "").lower()
        is_ollama = provider == "ollama" or str(self._litellm_model).startswith("ollama/")
        api_base_candidates = self._loopback_alias_candidates(
            self._litellm_api_base,
            is_ollama=is_ollama,
        )
        base_kwargs: dict = {"model": self._litellm_model, "input": texts, "timeout": timeout}

        def _is_transient_litellm_error(exc: Exception) -> bool:
            message = str(exc).lower()
            transient_markers = (
                "connection refused",
                "server disconnected without sending a response",
                "apiconnectionerror",
                "connecterror",
                "failed to connect",
                "remoteprotocolerror",
                "temporarily unavailable",
                "read timeout",
                "connect timeout",
                "connection reset",
                "broken pipe",
            )
            return any(marker in message for marker in transient_markers)

        response = None
        last_error: Exception | None = None
        current_api_base: str | None = self._litellm_api_base
        for attempt in range(1, retry_attempts + 1):
            current_api_base = api_base_candidates[(attempt - 1) % len(api_base_candidates)]
            kwargs = dict(base_kwargs)
            if current_api_base:
                kwargs["api_base"] = current_api_base
            try:
                response = litellm.embedding(**kwargs)
                if current_api_base:
                    self._litellm_api_base = current_api_base
                self._litellm_circuit_open_until = 0.0
                self._litellm_last_error = None
                break
            except Exception as exc:
                last_error = exc
                transient = _is_transient_litellm_error(exc)
                logger.warning(
                    "embedding_litellm_request_failed",
                    model=self._litellm_model,
                    api_base=current_api_base,
                    configured_api_base=self._litellm_api_base,
                    attempt=attempt,
                    retries=retry_attempts,
                    transient=transient,
                    error=str(exc),
                )
                if not transient or attempt >= retry_attempts:
                    break
                if retry_backoff_ms > 0:
                    sleep_seconds = min(
                        (retry_backoff_ms / 1000.0) * (2 ** (attempt - 1)),
                        2.0,
                    )
                    time.sleep(sleep_seconds)

        if response is None and last_error is not None:
            error_message = str(last_error)
            transient = _is_transient_litellm_error(last_error)
            if transient:
                self._litellm_circuit_open_until = time.monotonic() + circuit_open_secs
                self._litellm_last_error = error_message
                raise EmbeddingUnavailableError(
                    "LiteLLM embedding endpoint unavailable "
                    f"(model={self._litellm_model}, api_base={self._litellm_api_base}, "
                    f"retries={retry_attempts}, circuit_open_secs={circuit_open_secs:.0f}, "
                    f"cause={error_message})"
                ) from last_error
            raise EmbeddingUnavailableError(
                f"LiteLLM embedding failed (model={self._litellm_model}, api_base={self._litellm_api_base}): {error_message}"
            ) from last_error

        # OpenAI-style: response.data[i].embedding (items may be objects or dicts)
        def _vec(d: Any) -> list[float]:
            if isinstance(d, dict):
                return list(d["embedding"])
            return list(getattr(d, "embedding", d))

        if hasattr(response, "data"):
            return [_vec(d) for d in response.data]
        if isinstance(response, dict) and "data" in response:
            return [_vec(d) for d in response["data"]]
        raise EmbeddingUnavailableError(f"LiteLLM returned unexpected shape: {type(response)}")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        override = get_embedding_override()
        if override is not None:
            return override.embed_batch(texts)

        # Auto-detect MCP server if not already initialized
        if not self._initialized:
            self._auto_detect_and_init()

        if self._backend == "unavailable":
            self._retry_client_once()
            if self._backend == "unavailable":
                _url = (
                    get_setting("embedding.client_url")
                    or f"http://127.0.0.1:{int(get_setting('embedding.http_port') or 18501)}"
                )
                raise EmbeddingUnavailableError(
                    f"Embedding unavailable (client-only mode). Run an embedding server at {_url} "
                    "(GET /health, POST /embed/single) or set embedding.provider=ollama."
                )
        if self._backend == "litellm":
            return self._embed_litellm(texts)
        if self._client_mode:
            return self._embed_http(texts)
        return self._embed_fallback(texts)

    def embed_force_local(self, texts: list[str]) -> list[list[float]]:
        """Embed without HTTP client: use LiteLLM or fallback (e.g. route test)."""
        if not texts:
            return []
        if not self._initialized:
            self._auto_detect_and_init()
        if self._backend == "litellm":
            return self._embed_litellm(texts)
        return self._embed_fallback(texts)

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
        """True when initialized. No in-process model."""
        return self._initialized

    @property
    def is_loading(self) -> bool:
        """Always False (no in-process model)."""
        return False


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
    "EmbeddingOverrideProtocol",
    "EmbeddingService",
    "EmbeddingUnavailableError",
    "EmbeddingPortInUseError",
    "get_embedding_override",
    "get_embedding_service",
    "set_embedding_override",
    "embed_text",
    "embed_batch",
    "get_dimension",
]
