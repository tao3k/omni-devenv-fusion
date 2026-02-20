"""Common response payload builders shared across skills."""

from __future__ import annotations

from typing import Any


def build_status_message_response(
    *,
    status: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a simple status+message payload with optional extra fields."""
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def build_status_error_response(
    *,
    error: str,
    status: str = "error",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a simple status+error payload with optional extra fields."""
    payload: dict[str, Any] = {
        "status": status,
        "error": str(error),
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def build_success_error_response(
    *,
    error: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a success=False error payload with optional extra fields."""
    payload: dict[str, Any] = {
        "success": False,
        "error": str(error),
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def build_error_response(
    *,
    error: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a generic error payload with optional extra fields."""
    payload: dict[str, Any] = {
        "error": str(error),
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


__all__ = [
    "build_error_response",
    "build_status_error_response",
    "build_status_message_response",
    "build_success_error_response",
]
