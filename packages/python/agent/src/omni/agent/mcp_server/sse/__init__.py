"""
agent/mcp_server/sse.py - SSE Transport for Claude Code CLI

Uses MCP SDK's StreamableHTTPServerTransport for standard MCP protocol.
Enhanced with session management and security features.

Performance:
- orjson for 10-50x faster JSON serialization
- Zero-copy where possible
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

import orjson
import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from omni.agent.mcp_server.observability import MCPRequestObservability
from .embedding_http import (
    _embedding_overloaded_response,
    _embedding_timeout_response,
    _embedding_unavailable_response,
    _resolve_embed_http_limits,
)
from .runtime import _missing_fast_runtime_modules, _select_uvicorn_runtime
from .session import MCPSessionManager

if TYPE_CHECKING:
    from starlette.requests import Request

logger = logging.getLogger("omni.agent.mcp_server.sse")


# Global session manager
_session_manager = MCPSessionManager()
_EMBED_RECOVERY_MIN_INTERVAL_SECS = 2.0
_embed_recovery_lock = asyncio.Lock()
_embed_recovery_next_attempt_at = 0.0


def _recover_embedding_backend_blocking() -> bool:
    from omni.agent.ollama_lifecycle import (
        ensure_ollama_for_embedding,
        get_embedding_ollama_config,
        is_ollama_backed_embedding,
        is_ollama_listening,
        parse_ollama_api_base,
    )

    cfg = get_embedding_ollama_config()
    if not is_ollama_backed_embedding(cfg["provider"], cfg["litellm_model"]):
        return False

    ensure_ollama_for_embedding()
    host, port = parse_ollama_api_base(cfg["api_base"])
    return is_ollama_listening(host, port, timeout=1.0)


async def _attempt_embedding_backend_recovery(reason: str) -> bool:
    global _embed_recovery_next_attempt_at

    now = time.monotonic()
    if now < _embed_recovery_next_attempt_at:
        return False

    async with _embed_recovery_lock:
        now = time.monotonic()
        if now < _embed_recovery_next_attempt_at:
            return False
        _embed_recovery_next_attempt_at = now + _EMBED_RECOVERY_MIN_INTERVAL_SECS

        try:
            recovered = bool(await run_in_threadpool(_recover_embedding_backend_blocking))
        except Exception as exc:
            logger.warning("Embedding auto-heal failed: %s", exc)
            return False

        if not recovered:
            logger.warning(
                "Embedding auto-heal attempted, upstream still unavailable. reason=%s", reason
            )
            return False

        try:
            from omni.foundation.services.embedding import get_embedding_service

            get_embedding_service().reset_litellm_circuit()
        except Exception as exc:
            logger.debug("Embedding circuit reset skipped: %s", exc)

        logger.warning("Embedding auto-heal succeeded (upstream recovered).")
        return True


def create_sse_app(
    handler: Any,
    host: str = "127.0.0.1",
    port: int = 3000,
    enable_cors: bool = True,
    session_timeout: float = 300.0,
) -> Starlette:
    """Create SSE Starlette application with MCP SDK StreamableHTTP transport.

    Args:
        handler: MCP request handler (AgentMCPHandler)
        host: Host to bind to
        port: Port to listen on
        enable_cors: Enable CORS middleware
        session_timeout: Session timeout in seconds

    Returns:
        Starlette application
    """
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    from mcp.server.transport_security import TransportSecuritySettings

    # Create transport with security settings
    security_settings = TransportSecuritySettings(
        allowed_hosts=["*"],  # Allow all hosts
        allowed_origins=["*"],  # Allow all origins
    )
    _ = StreamableHTTPServerTransport(
        mcp_session_id=None,
        security_settings=security_settings,
    )
    request_observability = MCPRequestObservability(
        logger=logger,
        log_interval_secs=20.0,
        latency_window_size=1024,
    )
    embed_request_timeout_s, embed_queue_wait_timeout_s, embed_max_concurrency = (
        _resolve_embed_http_limits()
    )
    embed_semaphore = asyncio.Semaphore(embed_max_concurrency)

    class _EmbedQueueTimeoutError(RuntimeError):
        pass

    class _EmbedCallTimeoutError(RuntimeError):
        pass

    async def _run_embed_call(func: Any, *args: Any) -> Any:
        try:
            await asyncio.wait_for(embed_semaphore.acquire(), timeout=embed_queue_wait_timeout_s)
        except TimeoutError as exc:
            raise _EmbedQueueTimeoutError from exc
        try:
            return await asyncio.wait_for(
                run_in_threadpool(func, *args),
                timeout=embed_request_timeout_s,
            )
        except TimeoutError as exc:
            raise _EmbedCallTimeoutError from exc
        finally:
            embed_semaphore.release()

    async def handle_mcp(request: Request) -> Response:
        """Handle MCP HTTP requests with robust error handling."""
        # Initialize default values for error cases
        method = ""
        req_id = None
        endpoint = f"mcp:{request.url.path}"
        started_at = request_observability.start(endpoint)
        observed_ok = False
        observed_status = 500

        # Extract session ID from client headers.
        session_id_header = request.headers.get("mcp-session-id")
        session_id = session_id_header or str(uuid.uuid4())

        def _finalize(response: Response, *, ok: bool) -> Response:
            nonlocal observed_ok, observed_status
            observed_ok = ok
            observed_status = response.status_code
            return response

        try:
            # Streamable HTTP session termination (client -> server).
            # Be permissive: treat missing/unknown session IDs as already closed.
            if request.method == "DELETE":
                if session_id_header:
                    await _session_manager.remove_session(session_id_header)
                    return _finalize(
                        Response(
                            content=b"",
                            status_code=204,
                            headers={"MCP-Session-Id": session_id_header},
                        ),
                        ok=True,
                    )
                return _finalize(Response(content=b"", status_code=204), ok=True)

            # Read the request body
            body = await request.body()
            if not body:
                if request.method == "GET":
                    from omni.foundation.api.agent_schema import build_server_info

                    return _finalize(
                        JSONResponse(
                            build_server_info(
                                message=(
                                    "MCP uses POST with JSON-RPC body. "
                                    "Use /health for health checks."
                                ),
                            )
                        ),
                        ok=True,
                    )
                return _finalize(
                    JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32600, "message": "Invalid Request: Empty body"},
                        },
                        status_code=400,
                    ),
                    ok=False,
                )

            try:
                data = orjson.loads(body)
            except orjson.JSONDecodeError as e:
                return _finalize(
                    JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": f"Parse error: {e}"},
                        },
                        status_code=400,
                    ),
                    ok=False,
                )

            # Validate JSON-RPC version
            if data.get("jsonrpc") != "2.0":
                return _finalize(
                    JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "error": {"code": -32600, "message": "Invalid JSON-RPC version"},
                        },
                        status_code=400,
                    ),
                    ok=False,
                )

            method = data.get("method", "")
            params = data.get("params", {})
            req_id = data.get("id")

            # Validate protocol version for initialize
            if method == "initialize":
                client_version = params.get("protocolVersion", "")
                # MCP protocol version check
                if client_version and not _is_supported_protocol_version(client_version):
                    logger.warning(f"Unsupported protocol version: {client_version}")

            # Handle the request using the provided handler
            request_dict = {
                "method": method,
                "params": params,
                "id": req_id,
                "jsonrpc": "2.0",
                "_session_id": session_id,
            }

            # Add timeout for request handling
            response = await asyncio.wait_for(
                handler.handle_request(request_dict),
                timeout=session_timeout,
            )

            # Notifications (no id): Streamable HTTP expects 202 Accepted, no body
            if req_id is None:
                return _finalize(
                    Response(
                        content=b"",
                        status_code=202,
                        headers={"MCP-Session-Id": session_id},
                    ),
                    ok=True,
                )

            # Return the response for requests
            response_data = {"jsonrpc": "2.0", "id": req_id}
            has_error = False
            if isinstance(response, dict):
                if "result" in response:
                    response_data["result"] = response["result"]
                elif "error" in response:
                    response_data["error"] = response["error"]
                    has_error = True

            # Use orjson for faster serialization (10-50x faster than stdlib json)
            response_bytes = orjson.dumps(response_data)

            # Add session header for tracking
            return _finalize(
                Response(
                    content=response_bytes,
                    media_type="application/json",
                    headers={"MCP-Session-Id": session_id},
                ),
                ok=not has_error,
            )

        except TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            return _finalize(
                JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": "Request timeout"},
                    },
                    status_code=504,
                    headers={"MCP-Session-Id": session_id},
                ),
                ok=False,
            )

        except Exception as e:
            logger.error(f"Error handling MCP request: {e}", exc_info=True)
            return _finalize(
                JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": f"Internal error: {e!s}"},
                    },
                    status_code=500,
                    headers={"MCP-Session-Id": session_id},
                ),
                ok=False,
            )
        finally:
            request_observability.finish(
                endpoint,
                started_at,
                ok=observed_ok,
                status_code=observed_status,
            )

    async def handle_get(request: Request) -> JSONResponse:
        """Handle GET requests - return server info."""
        return JSONResponse(
            {
                "name": "omni-agent",
                "version": "2.0.0",
                "protocolVersion": "2024-11-05",
            }
        )

    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        ready = bool(getattr(handler, "is_ready", False))
        initializing = bool(getattr(handler, "is_initializing", False))
        return JSONResponse(
            {
                "status": "healthy",
                "active_sessions": _session_manager.active_sessions,
                "ready": ready,
                "initializing": initializing,
                "observability": request_observability.health_summary(),
            }
        )

    # OAuth endpoints (required by Claude Code for authentication)
    async def oauth_discovery(request: Request) -> JSONResponse:
        """OAuth discovery endpoint."""
        return JSONResponse(
            {
                "issuer": f"http://{host}:{port}",
                "authorization_endpoint": f"http://{host}:{port}/authorize",
                "token_endpoint": f"http://{host}:{port}/token",
                "response_types_supported": ["none"],
                "grant_types_supported": ["client_credentials"],
                "scopes_supported": ["read", "write"],
            }
        )

    async def oauth_register(request: Request) -> JSONResponse:
        """OAuth register endpoint."""
        return JSONResponse({"client_id": "omni-agent"})

    async def embed_batch(request: Request) -> JSONResponse:
        """Embedding HTTP client endpoint: POST /embed/batch for embedding_client compatibility."""
        endpoint = f"http:{request.url.path}"
        started_at = request_observability.start(endpoint)
        observed_ok = False
        observed_status = 500

        def _finalize(response: JSONResponse, *, ok: bool) -> JSONResponse:
            nonlocal observed_ok, observed_status
            observed_ok = ok
            observed_status = response.status_code
            return response

        try:
            body = await request.json()
            texts = body.get("texts", [])
            if not texts:
                return _finalize(JSONResponse({"vectors": []}), ok=True)
            from omni.foundation.services.embedding import (
                EmbeddingUnavailableError,
                get_embedding_service,
            )

            embed_svc = get_embedding_service()
            try:
                vectors = await _run_embed_call(embed_svc.embed_batch, texts)
                return _finalize(JSONResponse({"vectors": vectors}), ok=True)
            except _EmbedQueueTimeoutError:
                logger.warning(
                    "embed_batch overloaded: queue wait timeout exceeded (wait_timeout_s=%.3f)",
                    embed_queue_wait_timeout_s,
                )
                return _finalize(
                    _embedding_overloaded_response(
                        batch=True,
                        wait_timeout_s=embed_queue_wait_timeout_s,
                    ),
                    ok=False,
                )
            except _EmbedCallTimeoutError:
                logger.warning("embed_batch timed out (timeout_s=%.3f)", embed_request_timeout_s)
                return _finalize(
                    _embedding_timeout_response(
                        batch=True,
                        timeout_s=embed_request_timeout_s,
                    ),
                    ok=False,
                )
            except EmbeddingUnavailableError as error:
                recovered = await _attempt_embedding_backend_recovery(str(error))
                if recovered:
                    try:
                        vectors = await _run_embed_call(embed_svc.embed_batch, texts)
                        return _finalize(JSONResponse({"vectors": vectors}), ok=True)
                    except _EmbedQueueTimeoutError:
                        logger.warning(
                            "embed_batch overloaded after recovery attempt (wait_timeout_s=%.3f)",
                            embed_queue_wait_timeout_s,
                        )
                        return _finalize(
                            _embedding_overloaded_response(
                                batch=True,
                                wait_timeout_s=embed_queue_wait_timeout_s,
                            ),
                            ok=False,
                        )
                    except _EmbedCallTimeoutError:
                        logger.warning(
                            "embed_batch timed out after recovery attempt (timeout_s=%.3f)",
                            embed_request_timeout_s,
                        )
                        return _finalize(
                            _embedding_timeout_response(
                                batch=True,
                                timeout_s=embed_request_timeout_s,
                            ),
                            ok=False,
                        )
                    except EmbeddingUnavailableError as retry_error:
                        error = retry_error
                logger.warning("embed_batch unavailable: %s", error)
                return _finalize(_embedding_unavailable_response(error, batch=True), ok=False)
        except Exception as e:
            logger.exception("embed_batch failed")
            return _finalize(
                JSONResponse(
                    {"error": str(e), "vectors": []},
                    status_code=500,
                ),
                ok=False,
            )
        finally:
            request_observability.finish(
                endpoint,
                started_at,
                ok=observed_ok,
                status_code=observed_status,
            )

    async def embed_single(request: Request) -> JSONResponse:
        """Embedding HTTP client endpoint: POST /embed/single for embedding_client compatibility."""
        endpoint = f"http:{request.url.path}"
        started_at = request_observability.start(endpoint)
        observed_ok = False
        observed_status = 500

        def _finalize(response: JSONResponse, *, ok: bool) -> JSONResponse:
            nonlocal observed_ok, observed_status
            observed_ok = ok
            observed_status = response.status_code
            return response

        try:
            body = await request.json()
            text = body.get("text", "")
            if not text:
                return _finalize(JSONResponse({"vector": []}), ok=True)
            from omni.foundation.services.embedding import (
                EmbeddingUnavailableError,
                get_embedding_service,
            )

            embed_svc = get_embedding_service()
            try:
                vectors = await _run_embed_call(embed_svc.embed, text)
                vector = vectors[0] if vectors else []
                return _finalize(JSONResponse({"vector": vector}), ok=True)
            except _EmbedQueueTimeoutError:
                logger.warning(
                    "embed_single overloaded: queue wait timeout exceeded (wait_timeout_s=%.3f)",
                    embed_queue_wait_timeout_s,
                )
                return _finalize(
                    _embedding_overloaded_response(
                        batch=False,
                        wait_timeout_s=embed_queue_wait_timeout_s,
                    ),
                    ok=False,
                )
            except _EmbedCallTimeoutError:
                logger.warning("embed_single timed out (timeout_s=%.3f)", embed_request_timeout_s)
                return _finalize(
                    _embedding_timeout_response(
                        batch=False,
                        timeout_s=embed_request_timeout_s,
                    ),
                    ok=False,
                )
            except EmbeddingUnavailableError as error:
                recovered = await _attempt_embedding_backend_recovery(str(error))
                if recovered:
                    try:
                        vectors = await _run_embed_call(embed_svc.embed, text)
                        vector = vectors[0] if vectors else []
                        return _finalize(JSONResponse({"vector": vector}), ok=True)
                    except _EmbedQueueTimeoutError:
                        logger.warning(
                            "embed_single overloaded after recovery attempt (wait_timeout_s=%.3f)",
                            embed_queue_wait_timeout_s,
                        )
                        return _finalize(
                            _embedding_overloaded_response(
                                batch=False,
                                wait_timeout_s=embed_queue_wait_timeout_s,
                            ),
                            ok=False,
                        )
                    except _EmbedCallTimeoutError:
                        logger.warning(
                            "embed_single timed out after recovery attempt (timeout_s=%.3f)",
                            embed_request_timeout_s,
                        )
                        return _finalize(
                            _embedding_timeout_response(
                                batch=False,
                                timeout_s=embed_request_timeout_s,
                            ),
                            ok=False,
                        )
                    except EmbeddingUnavailableError as retry_error:
                        error = retry_error
                logger.warning("embed_single unavailable: %s", error)
                return _finalize(_embedding_unavailable_response(error, batch=False), ok=False)
        except Exception as e:
            logger.exception("embed_single failed")
            return _finalize(
                JSONResponse(
                    {"error": str(e), "vector": []},
                    status_code=500,
                ),
                ok=False,
            )
        finally:
            request_observability.finish(
                endpoint,
                started_at,
                ok=observed_ok,
                status_code=observed_status,
            )

    from omni.agent.mcp_server.inference_http import handle_chat_completions

    # Build routes
    routes = [
        Route("/sse", handle_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/messages/", handle_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/", handle_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/health", health),
        Route("/embed", embed_batch, methods=["POST"]),
        Route("/embed/batch", embed_batch, methods=["POST"]),
        Route("/embed/single", embed_single, methods=["POST"]),
        Route("/v1/chat/completions", handle_chat_completions, methods=["POST"]),
        Route("/.well-known/oauth-authorization-server", oauth_discovery),
        Route("/.well-known/openid-configuration", oauth_discovery),
        Route("/register", oauth_register, methods=["POST"]),
        Route("/.well-known/oauth-protected-resource", oauth_discovery),
    ]

    # Add CORS middleware if enabled
    middleware = []
    if enable_cors:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

    return Starlette(routes=routes, middleware=middleware)


def _is_supported_protocol_version(version: str) -> bool:
    """Check if protocol version is supported."""
    supported = ["2024-11-05", "2024-09-01", "2024-06-14"]
    return version in supported


async def run_sse(
    handler: Any,
    host: str = "127.0.0.1",
    port: int = 3000,
    enable_cors: bool = True,
) -> None:
    """Run SSE server.

    Args:
        handler: MCP request handler
        host: Host to bind to
        port: Port to listen on
        enable_cors: Enable CORS middleware
    """
    try:
        from omni.foundation.config import get_config_paths

        tool_timeout = get_config_paths().get_mcp_timeout(None)
        # SSE wraps entire request; must be >= tool timeout + buffer for response serialization
        session_timeout = float(tool_timeout) + 30 if tool_timeout and tool_timeout > 0 else 300.0
    except Exception:
        session_timeout = 1830.0  # 1800 + 30 buffer when config unavailable
    app = create_sse_app(handler, host, port, enable_cors, session_timeout=session_timeout)
    loop_impl, http_impl = _select_uvicorn_runtime()
    missing_fast_runtime = _missing_fast_runtime_modules()
    if missing_fast_runtime:
        logger.warning(
            "SSE runtime fallback loop=%s http=%s (missing optional modules: %s). "
            "Run `uv sync` to install workspace runtime dependencies.",
            loop_impl,
            http_impl,
            ", ".join(missing_fast_runtime),
        )
    logger.info(
        "Starting SSE runtime with uvicorn loop=%s http=%s",
        loop_impl,
        http_impl,
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        loop=loop_impl,
        http=http_impl,
    )
    server = uvicorn.Server(config)
    await server.serve()


__all__ = ["create_sse_app", "run_sse"]
