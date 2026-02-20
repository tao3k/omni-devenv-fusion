"""HTTP webhook for gateway: POST /message with session_id + message, same agent loop."""

from __future__ import annotations

import logging
from typing import Any

import orjson
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from omni.agent.workflows.run_entry import execute_task_with_session

logger = logging.getLogger("omni.agent.gateway.webhook")

# Default session when not provided
DEFAULT_SESSION_ID = "webhook:default"


async def _handle_message(request: Request, kernel: Any) -> Response:
    """Handle POST /message: body { \"message\": \"...\", \"session_id\": \"...\" }."""
    try:
        body = await request.body()
        if not body:
            return JSONResponse(
                {"error": "Empty body"},
                status_code=400,
            )
        data = orjson.loads(body)
    except orjson.JSONDecodeError as e:
        return JSONResponse(
            {"error": f"Invalid JSON: {e}"},
            status_code=400,
        )

    message = data.get("message") or data.get("text") or ""
    session_id = data.get("session_id") or request.headers.get("X-Session-Id") or DEFAULT_SESSION_ID

    if not message or not message.strip():
        return JSONResponse(
            {"error": "message or text required"},
            status_code=400,
        )

    try:
        result = await execute_task_with_session(
            session_id,
            message.strip(),
            kernel=kernel,
            max_steps=20,
            verbose=False,
            use_memory=True,
        )
        out = result.get("output", "")
        return Response(
            content=orjson.dumps(
                {"output": out, "session_id": result.get("session_id", session_id)}
            ),
            media_type="application/json",
        )
    except Exception as e:
        logger.exception("Webhook execute_task_with_session failed")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )


async def _handle_health(_request: Request) -> Response:
    """GET /health for liveness."""
    return JSONResponse({"status": "ok", "service": "omni-gateway-webhook"})


def create_webhook_app(kernel: Any, enable_cors: bool = True) -> Starlette:
    """Create Starlette app for gateway webhook (same loop as stdio gateway).

    Args:
        kernel: Started kernel (from get_kernel()); must be initialized and started.
        enable_cors: Enable CORS middleware.

    Returns:
        Starlette application. Mount at host:port with uvicorn.
    """

    async def message_endpoint(request: Request) -> Response:
        return await _handle_message(request, kernel)

    routes = [
        Route("/message", message_endpoint, methods=["POST"]),
        Route("/health", _handle_health, methods=["GET"]),
    ]
    middleware = (
        [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])]
        if enable_cors
        else []
    )
    return Starlette(routes=routes, middleware=middleware)
