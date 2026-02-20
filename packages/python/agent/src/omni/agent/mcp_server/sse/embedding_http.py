"""Embedding HTTP endpoint helpers for MCP SSE transport."""

from __future__ import annotations

from starlette.responses import JSONResponse

_DEFAULT_EMBED_REQUEST_TIMEOUT_S = 20.0
_DEFAULT_EMBED_QUEUE_WAIT_TIMEOUT_S = 1.0
_DEFAULT_EMBED_MAX_CONCURRENCY = 24


def _embedding_unavailable_response(error: Exception, *, batch: bool) -> JSONResponse:
    payload = {
        "code": "embedding_unavailable",
        "error": str(error),
        "hint": (
            "MCP embedding endpoint is up, but upstream embedding backend is unavailable. "
            "Check Ollama at embedding.litellm_api_base (default http://127.0.0.1:11434)."
        ),
    }
    if batch:
        payload["vectors"] = []
    else:
        payload["vector"] = []
    return JSONResponse(payload, status_code=503)


def _embedding_overloaded_response(*, batch: bool, wait_timeout_s: float) -> JSONResponse:
    payload = {
        "code": "embedding_overloaded",
        "error": "Embedding queue saturated; request rejected fast.",
        "hint": (
            "Reduce concurrent embedding traffic or increase "
            "mcp.embed_max_concurrency / mcp.embed_queue_wait_timeout_secs."
        ),
        "queue_wait_timeout_secs": round(wait_timeout_s, 3),
    }
    if batch:
        payload["vectors"] = []
    else:
        payload["vector"] = []
    return JSONResponse(payload, status_code=503)


def _embedding_timeout_response(*, batch: bool, timeout_s: float) -> JSONResponse:
    payload = {
        "code": "embedding_timeout",
        "error": "Embedding call exceeded per-request timeout.",
        "hint": (
            "Upstream embedding backend may be slow or stalled. "
            "Check Ollama health and mcp.embed_request_timeout_secs."
        ),
        "timeout_secs": round(timeout_s, 3),
    }
    if batch:
        payload["vectors"] = []
    else:
        payload["vector"] = []
    return JSONResponse(payload, status_code=503)


def _coerce_positive_float(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    if parsed <= 0:
        return float(default)
    return parsed


def _coerce_positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    if parsed <= 0:
        return int(default)
    return parsed


def _resolve_embed_http_limits() -> tuple[float, float, int]:
    """Resolve embed endpoint runtime limits from settings with safe defaults."""
    request_timeout = _DEFAULT_EMBED_REQUEST_TIMEOUT_S
    queue_wait_timeout = _DEFAULT_EMBED_QUEUE_WAIT_TIMEOUT_S
    max_concurrency = _DEFAULT_EMBED_MAX_CONCURRENCY
    try:
        from omni.foundation.config.settings import get_setting

        request_timeout = _coerce_positive_float(
            get_setting("mcp.embed_request_timeout_secs", request_timeout),
            default=_DEFAULT_EMBED_REQUEST_TIMEOUT_S,
        )
        queue_wait_timeout = _coerce_positive_float(
            get_setting("mcp.embed_queue_wait_timeout_secs", queue_wait_timeout),
            default=_DEFAULT_EMBED_QUEUE_WAIT_TIMEOUT_S,
        )
        max_concurrency = _coerce_positive_int(
            get_setting("mcp.embed_max_concurrency", max_concurrency),
            default=_DEFAULT_EMBED_MAX_CONCURRENCY,
        )
    except Exception:
        pass
    return request_timeout, queue_wait_timeout, max_concurrency
